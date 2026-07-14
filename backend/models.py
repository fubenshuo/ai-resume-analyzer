"""
Pydantic 数据模型定义

包含请求/响应模型、简历信息模型和匹配结果模型。
"""

from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field


# ─── 简历关键信息 ───

class BasicInfo(BaseModel):
    """基本信息（必选）"""
    name: str = Field(default="", description="姓名")
    phone: str = Field(default="", description="电话号码")
    email: str = Field(default="", description="电子邮箱")
    address: str = Field(default="", description="地址")


class JobIntent(BaseModel):
    """求职意向（加分项）"""
    position: str = Field(default="", description="期望职位")
    salary: str = Field(default="", description="期望薪资")


class Education(BaseModel):
    """教育背景"""
    degree: str = Field(default="", description="最高学历")
    school: str = Field(default="", description="毕业院校")
    major: str = Field(default="", description="专业")


class ProjectExperience(BaseModel):
    """项目经历"""
    name: str = Field(default="", description="项目名称")
    description: str = Field(default="", description="项目描述")
    role: str = Field(default="", description="担任角色")


class BackgroundInfo(BaseModel):
    """背景信息（加分项）"""
    work_years: str = Field(default="", description="工作年限")
    education: Education = Field(default_factory=Education)
    skills: list[str] = Field(default_factory=list, description="技能列表")
    project_experiences: list[ProjectExperience] = Field(default_factory=list)


class ResumeInfo(BaseModel):
    """完整的简历解析结果"""
    basic_info: BasicInfo = Field(default_factory=BasicInfo)
    job_intent: JobIntent = Field(default_factory=JobIntent)
    background_info: BackgroundInfo = Field(default_factory=BackgroundInfo)
    raw_text: str = Field(default="", description="清洗后的原始文本")


# ─── 匹配结果 ───

class MatchDetail(BaseModel):
    """匹配详情"""
    skill_match_rate: float = Field(default=0.0, ge=0.0, le=1.0, description="技能匹配率")
    experience_relevance: float = Field(default=0.0, ge=0.0, le=1.0, description="工作经验相关性")
    education_match: float = Field(default=0.0, ge=0.0, le=1.0, description="学历匹配度")
    overall_score: float = Field(default=0.0, ge=0.0, le=100.0, description="综合匹配度评分")


class MatchResult(BaseModel):
    """完整的匹配结果"""
    matched_keywords: list[str] = Field(default_factory=list, description="匹配的关键词")
    missing_keywords: list[str] = Field(default_factory=list, description="缺失的关键词")
    match_detail: MatchDetail = Field(default_factory=MatchDetail)
    ai_analysis: str = Field(default="", description="AI 综合分析")


# ─── API 请求 / 响应 ───

class AnalyzeRequest(BaseModel):
    """分析请求——上传简历后，传入 JD 描述进行匹配"""
    job_description: str = Field(..., min_length=1, max_length=10000, description="岗位需求描述")


class AnalyzeResponse(BaseModel):
    """分析接口完整响应"""
    resume_id: str = Field(..., description="简历唯一标识")
    status: str = Field(..., description="处理状态")
    extraction_method: str = Field(default="rule", description="提取方式: ai / rule")
    match_method: str = Field(default="rule", description="匹配方式: ai / rule")
    cached: bool = Field(default=False, description="是否命中缓存")
    resume_info: ResumeInfo = Field(default_factory=ResumeInfo)
    match_result: Optional[MatchResult] = Field(default=None)


class UploadResponse(BaseModel):
    """上传接口响应"""
    resume_id: str = Field(..., description="简历唯一标识")
    filename: str = Field(..., description="原始文件名")
    text_preview: str = Field(default="", description="解析文本预览（前200字）")


class ErrorResponse(BaseModel):
    """统一错误响应"""
    detail: str = Field(..., description="错误详情")
    error_code: str = Field(default="UNKNOWN", description="错误码")
