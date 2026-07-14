"""
诊断脚本 — 分别测试 PDF 解析和 DeepSeek API 连通性

用法：
  cd backend
  python test_diagnose.py 你的简历.pdf
"""

import sys
import asyncio
import httpx
from pathlib import Path

# 确保能 import 项目模块
sys.path.insert(0, str(Path(__file__).parent))

from config import settings
from pdf_parser import parse_pdf, PDFParseError
from text_processor import clean_resume_text
from info_extractor import extract_by_ai, extract_by_rules

DEEPSEEK_CHAT_URL = f"{settings.ai_api_base_url}/chat/completions"


async def test_api_connection():
    """测试 DeepSeek API 是否能连通"""
    print("=" * 60)
    print("🔌 测试 1: DeepSeek API 连通性")
    print(f"   URL: {DEEPSEEK_CHAT_URL}")
    print(f"   Model: {settings.ai_model}")
    print(f"   Key: {settings.ai_api_key[:12]}...")
    print()

    payload = {
        "model": settings.ai_model,
        "messages": [
            {"role": "user", "content": "你好，请回复'API连通正常'"},
        ],
        "max_tokens": 50,
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                DEEPSEEK_CHAT_URL,
                headers={
                    "Authorization": f"Bearer {settings.ai_api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
        print(f"   HTTP 状态: {resp.status_code}")

        if resp.is_success:
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            print(f"   ✅ API 连通正常！响应: {content[:200]}")
        else:
            print(f"   ❌ API 返回错误: {resp.text[:500]}")
    except Exception as e:
        print(f"   ❌ 连接失败: {e}")


def test_pdf_parsing(filepath: str):
    """测试 PDF 解析是否能提取文本"""
    print()
    print("=" * 60)
    print("📄 测试 2: PDF 文本解析")
    print(f"   文件: {filepath}")

    try:
        with open(filepath, "rb") as f:
            file_bytes = f.read()
        print(f"   文件大小: {len(file_bytes)} bytes")

        raw_text = parse_pdf(file_bytes, Path(filepath).name)
        cleaned = clean_resume_text(raw_text)

        print(f"   提取文本长度: {len(cleaned)} 字符")
        print(f"   文本预览（前 500 字符）:")
        print(f"   ---")
        print(cleaned[:500])
        print(f"   ---")
        print(f"   ✅ PDF 解析成功")
    except PDFParseError as e:
        print(f"   ❌ PDF 解析失败: {e}")
    except Exception as e:
        print(f"   ❌ 读取文件失败: {e}")


async def test_ai_extraction(filepath: str):
    """测试完整 AI 提取流程"""
    print()
    print("=" * 60)
    print("🤖 测试 3: AI 信息提取")

    try:
        with open(filepath, "rb") as f:
            file_bytes = f.read()

        raw_text = parse_pdf(file_bytes, Path(filepath).name)
        cleaned = clean_resume_text(raw_text)
        print(f"   输入文本长度: {len(cleaned)} 字符")

        print("   正在调用 AI 提取...")
        resume_info = await extract_by_ai(cleaned)
        print(f"   ✅ AI 提取完成！")
        print(f"   姓名: {resume_info.basic_info.name}")
        print(f"   电话: {resume_info.basic_info.phone}")
        print(f"   邮箱: {resume_info.basic_info.email}")
        print(f"   学历: {resume_info.background_info.education.degree}")
        print(f"   院校: {resume_info.background_info.education.school}")
        print(f"   专业: {resume_info.background_info.education.major}")
        print(f"   工作年限: {resume_info.background_info.work_years}")
        print(f"   技能: {resume_info.background_info.skills}")
        print(f"   求职意向: {resume_info.job_intent.position}")
        print(f"   项目经历数: {len(resume_info.background_info.project_experiences)}")
    except Exception as e:
        print(f"   ❌ AI 提取失败: {e}")
        print("   回退规则提取测试:")
        resume_info = extract_by_rules(cleaned)
        print(f"   规则提取 → 姓名: '{resume_info.basic_info.name}', 电话: '{resume_info.basic_info.phone}', 邮箱: '{resume_info.basic_info.email}'")


async def main():
    print("🔧 AI 简历分析系统 - 诊断工具")
    print(f"   配置来源: {settings.model_config.get('env_file', 'N/A')}")
    print()

    # 测试 API 连接
    await test_api_connection()

    # 如果有传入 PDF 文件，则进一步测试
    if len(sys.argv) > 1:
        filepath = sys.argv[1]
        if not Path(filepath).exists():
            print(f"\n❌ 文件不存在: {filepath}")
            return

        test_pdf_parsing(filepath)
        await test_ai_extraction(filepath)
    else:
        print("\n💡 提示：传入 PDF 文件路径可进一步测试解析和提取")
        print(f"   用法: python {Path(__file__).name} 简历.pdf")


if __name__ == "__main__":
    asyncio.run(main())
