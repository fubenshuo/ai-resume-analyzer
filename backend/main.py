"""
FastAPI 主应用

AI 赋能的智能简历分析系统后端 API 服务。

API 端点：
  POST /api/upload          — 上传 PDF 简历，返回解析文本
  POST /api/analyze/{id}    — 对已上传简历进行信息提取 + JD 匹配评分
  GET  /api/result/{id}     — 获取历史分析结果（带缓存）
  GET  /api/health          — 健康检查

运行方式：
  cd backend && python main.py
  uvicorn main:app --host 0.0.0.0 --port 8000 --reload
"""

from __future__ import annotations

import uuid
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import settings
from models import UploadResponse, AnalyzeRequest, AnalyzeResponse, ErrorResponse
from pdf_parser import parse_pdf, PDFParseError
from text_processor import clean_resume_text, extract_sections
from info_extractor import extract_by_ai, extract_by_rules
from matcher import match_with_ai, match_by_rules
from cache import cache

# ─── 日志 ───

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("resume-api")

# ─── 临时文件存储（内存字典） ───
# 在 Serverless 环境中，建议使用 OSS/数据库代替
_uploaded_files: dict[str, dict] = {}


# ─── 应用生命周期 ───

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用启动/关闭回调"""
    logger.info(f"简历分析系统启动 | AI 模型: {settings.ai_model} | 缓存: {settings.cache_type}")
    yield
    logger.info("简历分析系统关闭")


app = FastAPI(
    title="AI 赋能的智能简历分析系统",
    description="上传 PDF 简历，AI 自动提取关键信息并进行岗位匹配评分",
    version="1.0.0",
    lifespan=lifespan,
)

# ─── CORS ───

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应限制来源
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── 异常处理 ───

@app.exception_handler(PDFParseError)
async def handle_pdf_error(request, exc: PDFParseError):
    return JSONResponse(
        status_code=400,
        content=ErrorResponse(detail=str(exc), error_code="PDF_PARSE_ERROR").model_dump(),
    )


@app.exception_handler(Exception)
async def handle_generic_error(request, exc: Exception):
    logger.exception("未处理的异常")
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            detail=f"服务内部错误: {str(exc)}",
            error_code="INTERNAL_ERROR",
        ).model_dump(),
    )


# ─── API 端点 ───

@app.post(
    "/api/upload",
    response_model=UploadResponse,
    summary="上传 PDF 简历",
    description="接收单个 PDF 文件，解析文本内容并返回简历 ID 和文本预览。",
)
async def upload_resume(file: UploadFile = File(...)):
    # 验证文件类型
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="仅支持 PDF 格式的文件")

    # 读取文件内容
    file_bytes = await file.read()

    # 验证文件大小
    max_size = settings.max_upload_size_mb * 1024 * 1024
    if len(file_bytes) > max_size:
        raise HTTPException(
            status_code=400,
            detail=f"文件大小超过限制（最大 {settings.max_upload_size_mb}MB）",
        )

    # 解析 PDF
    raw_text = parse_pdf(file_bytes, file.filename)
    cleaned_text = clean_resume_text(raw_text)

    # 生成唯一 ID
    resume_id = uuid.uuid4().hex[:12]

    # 存储已解析文本（内存存储）
    _uploaded_files[resume_id] = {
        "filename": file.filename,
        "cleaned_text": cleaned_text,
        "last_result": None,  # 缓存最近一次分析结果
    }

    logger.info(f"简历已上传: id={resume_id}, filename={file.filename}")

    return UploadResponse(
        resume_id=resume_id,
        filename=file.filename or "unknown.pdf",
        text_preview=cleaned_text[:200] + ("..." if len(cleaned_text) > 200 else ""),
    )


@app.post(
    "/api/analyze/{resume_id}",
    response_model=AnalyzeResponse,
    summary="分析简历并匹配 JD",
    description="对已上传的简历进行 AI 信息提取，并与岗位描述进行匹配评分。",
)
async def analyze_resume(resume_id: str, request: AnalyzeRequest):
    # 查找已上传的简历
    file_record = _uploaded_files.get(resume_id)
    if not file_record:
        raise HTTPException(status_code=404, detail="简历未找到，请先上传")

    cleaned_text = file_record["cleaned_text"]

    # 检查缓存
    cache_key = cache.make_key("resume:analysis", cache.content_hash(cleaned_text + request.job_description))
    cached_result = cache.get(cache_key)
    if cached_result:
        logger.info(f"缓存命中: {cache_key}")
        # 复制一份避免污染缓存中的原始数据
        result_copy = dict(cached_result)
        result_copy["resume_id"] = resume_id
        result_copy["cached"] = True
        return AnalyzeResponse(**result_copy)

    # ─── 文本分段（提高 AI 提取精度）───
    sections = extract_sections(cleaned_text)

    # ─── 信息提取 ───
    extraction_method = "ai"
    try:
        resume_info = await extract_by_ai(cleaned_text, sections)
        logger.info(f"AI 信息提取完成: {resume_info.basic_info.name}")
    except Exception as e:
        logger.warning(f"AI 提取失败，回退到规则提取: {e}")
        resume_info = extract_by_rules(cleaned_text)
        extraction_method = "rule"

    # 设置原始文本
    resume_info.raw_text = cleaned_text

    # ─── JD 匹配评分 ───
    match_method = "ai"
    try:
        match_result = await match_with_ai(resume_info, request.job_description)
        logger.info(f"AI 匹配完成: 综合评分 {match_result.match_detail.overall_score}")
    except Exception as e:
        logger.warning(f"AI 匹配失败，回退到规则匹配: {e}")
        match_result = match_by_rules(resume_info, request.job_description)
        match_method = "rule"

    # 构建响应
    result = AnalyzeResponse(
        resume_id=resume_id,
        status="completed",
        extraction_method=extraction_method,
        match_method=match_method,
        cached=False,
        resume_info=resume_info,
        match_result=match_result,
    )

    # 写入缓存 + 记录最近一次结果
    result_dict = result.model_dump()
    cache.set(cache_key, result_dict)
    _uploaded_files[resume_id]["last_result"] = result_dict

    return result


@app.get(
    "/api/result/{resume_id}",
    response_model=AnalyzeResponse,
    summary="获取最近分析结果",
    description="根据简历 ID 获取最近一次分析结果。",
)
async def get_result(resume_id: str):
    file_record = _uploaded_files.get(resume_id)
    if not file_record:
        raise HTTPException(status_code=404, detail="简历未找到，请先上传")

    last_result = file_record.get("last_result")
    if not last_result:
        raise HTTPException(
            status_code=404,
            detail="该简历尚未进行分析，请先调用 POST /api/analyze/{resume_id}",
        )

    logger.info(f"返回历史分析结果: {resume_id}")
    return last_result


@app.get("/api/health", summary="健康检查")
async def health_check():
    return {
        "status": "healthy",
        "service": "AI 简历分析系统",
        "version": "1.0.0",
        "ai_model": settings.ai_model,
        "cache_type": settings.cache_type,
    }


# ─── 启动入口 ───

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=True,
    )
