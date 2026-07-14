"""
AI 信息提取模块

调用 LLM API 从简历文本中提取结构化的关键信息。
同时提供基于正则的 fallback 方案，确保在无 API 时也能工作。
"""

from __future__ import annotations

import json
import logging
import re

import httpx

from config import settings
from models import BasicInfo, JobIntent, Education, ProjectExperience, BackgroundInfo, ResumeInfo

logger = logging.getLogger("resume-api")

# ─── Prompt 模板 ───

EXTRACTION_SYSTEM_PROMPT = """你是一个专业的简历解析器。请从以下简历文本中提取关键信息，以 JSON 格式返回。

返回格式必须严格遵循以下 JSON Schema（缺失字段用空字符串或空数组）：
{
  "name": "姓名",
  "phone": "电话号码",
  "email": "电子邮箱",
  "address": "地址/城市",
  "position": "期望职位/求职意向",
  "salary": "期望薪资",
  "work_years": "工作年限（如'3年'）",
  "degree": "最高学历（如'本科'、'硕士'）",
  "school": "毕业院校",
  "major": "专业",
  "skills": ["技能1", "技能2"],
  "project_experiences": [
    {"name": "项目名", "description": "项目描述", "role": "角色"}
  ]
}

注意：
1. 只返回 JSON，不要包含任何额外说明文字
2. 严格从简历文本中提取，不要编造信息
3. 如果某项信息未找到，请使用空字符串 "" 或空数组 []"""


async def extract_by_ai(text: str, sections: dict[str, str] | None = None) -> ResumeInfo:
    """
    使用 AI 模型提取简历关键信息。

    Args:
        text: 清洗后的简历文本
        sections: 可选的预分段文本，用于提高提取精度

    Returns:
        结构化的简历信息

    Raises:
        httpx.HTTPError: API 调用失败时抛出，由调用方 fallback 处理
    """
    api_url = f"{settings.ai_api_base_url}/chat/completions"
    logger.info(f"正在调用 AI 提取信息 | URL: {api_url} | Model: {settings.ai_model}")

    # 构建用户消息：优先使用分段文本
    if sections and len(sections) > 1:
        user_content = "以下简历已按段落拆分，请从中提取信息：\n\n"
        for sec_name, sec_text in sections.items():
            user_content += f"【{sec_name}】\n{sec_text}\n\n"
    else:
        user_content = text

    async with httpx.AsyncClient(timeout=settings.ai_request_timeout) as client:
        response = await client.post(
            api_url,
            headers={
                "Authorization": f"Bearer {settings.ai_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": settings.ai_model,
                "messages": [
                    {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
                    {"role": "user", "content": user_content},
                ],
                "temperature": 0.1,
                "max_tokens": 8000,
            },
        )

        if not response.is_success:
            error_body = response.text[:500]
            logger.error(f"AI API 返回错误 [{response.status_code}]: {error_body}")
            response.raise_for_status()

        data = response.json()
        message = data["choices"][0]["message"]
        # 推理模型（如 deepseek-reasoner）可能把内容放在 reasoning_content，content 为空时取它
        content = message.get("content", "") or message.get("reasoning_content", "")
        logger.info(f"AI 原始响应长度: {len(content)} 字符")

    # 解析 AI 返回的 JSON（兼容 markdown code block）
    parsed = _parse_ai_json(content)
    if not parsed:
        logger.warning(f"AI 返回内容无法解析为 JSON，原始内容前 300 字符:\n{content[:300]}")
    return _build_resume_info(parsed)


def extract_by_rules(text: str) -> ResumeInfo:
    """
    基于正则表达式的规则提取（fallback 方案）。

    当 AI API 不可用时使用，能提取基本信息中的姓名、电话、邮箱等。
    """
    parsed: dict = {}

    # 邮箱
    email_match = re.search(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", text)
    parsed["email"] = email_match.group(0) if email_match else ""

    # 手机号（中国大陆）
    phone_match = re.search(r"(?:(?:\+?86)?[-\s]?)?1[3-9]\d{9}", text)
    parsed["phone"] = phone_match.group(0) if phone_match else ""

    # 尝试提取姓名（通常在简历开头）
    lines = text.strip().split("\n")
    first_line = lines[0].strip() if lines else ""
    # 简单判断：首行短文本（<10字）且不含特殊关键词
    if first_line and len(first_line) <= 10 and not re.search(r"简历|resume|cv|个人", first_line, re.I):
        # 去除标点
        name_candidate = re.sub(r"[^一-龥a-zA-Z·•\s]", "", first_line).strip()
        if 2 <= len(name_candidate) <= 8:
            parsed["name"] = name_candidate
        else:
            parsed["name"] = ""
    else:
        parsed["name"] = ""

    # 地址（简单匹配）
    addr_match = re.search(r"(?:地址|现居|所在地)[：:]\s*(.+?)(?:\n|$)", text)
    if not addr_match:
        # 尝试匹配城市名
        addr_match = re.search(r"((?:北京|上海|广州|深圳|杭州|成都|武汉|南京|天津|重庆|苏州|西安|长沙|郑州|东莞|青岛|"
                               r"沈阳|宁波|昆明|大连|厦门|合肥|佛山|福州|哈尔滨|济南|温州|长春|石家庄|"
                               r"常州|泉州|南宁|贵阳|南昌|太原|烟台|嘉兴|南通|金华|珠海|惠州|徐州|"
                               r"海口|乌鲁木齐|兰州|中山|呼和浩特|银川|西宁|拉萨)(?:市|区|县)?)", text)
    parsed["address"] = addr_match.group(1) if addr_match else ""

    # 期望职位
    pos_match = re.search(r"(?:求职意[向願]|期望职位|应聘岗位|求职目标|意向岗位)[：:]\s*(.+?)(?:\n|，|。|$)", text)
    if not pos_match:
        pos_match = re.search(r"((?:Python|Java|前端|后端|全栈|算法|大数据|AI|测试|运维|产品|UI|UX)\s*(?:开发)?\s*(?:工程师|实习生|专员|经理))", text)
    parsed["position"] = pos_match.group(1).strip() if pos_match else ""

    # 期望薪资
    sal_match = re.search(r"(?:期望薪资|薪资要求|期望月薪)[：:]\s*(.+?)(?:\n|，|。|$)", text)
    parsed["salary"] = sal_match.group(1).strip() if sal_match else ""

    # 毕业院校
    sch_match = re.search(r"(?:毕业院校|学校|院校)[：:]\s*(.+?)(?:\n|，|。|$)", text)
    if not sch_match:
        sch_match = re.search(r"((?:[一-鿿]{2,6})(?:大学|学院))", text)
    parsed["school"] = sch_match.group(1).strip() if sch_match else ""

    # 专业
    maj_match = re.search(r"(?:专业|主修|所学专业)[：:]\s*(.+?)(?:\n|，|。|$)", text)
    parsed["major"] = maj_match.group(1).strip() if maj_match else ""

    # 学历
    degree_match = re.search(r"(博士|硕士|本科|大专|专科|高中|中专|MBA|EMBA)", text)
    parsed["degree"] = degree_match.group(1) if degree_match else ""

    # 工作年限
    years_match = re.search(r"(\d+)\s*年(?:以上)?(?:工作)?(?:经验|经历)", text)
    parsed["work_years"] = f"{years_match.group(1)}年" if years_match else ""

    # 技能（常见技术关键词）
    skill_keywords = [
        "Python", "Java", "JavaScript", "TypeScript", "Go", "Rust", "C++", "C#",
        "React", "Vue", "Angular", "Node.js", "Django", "Flask", "FastAPI", "Spring",
        "MySQL", "PostgreSQL", "MongoDB", "Redis", "Docker", "Kubernetes", "AWS",
        "Linux", "Git", "TensorFlow", "PyTorch", "机器学习", "深度学习", "数据分析",
        "产品设计", "项目管理", "UI设计", "Figma", "Photoshop",
    ]
    found_skills = []
    for skill in skill_keywords:
        if skill.lower() in text.lower():
            found_skills.append(skill)
    parsed["skills"] = found_skills

    parsed.setdefault("project_experiences", [])

    return _build_resume_info(parsed)


# ─── 辅助函数 ───

def _parse_ai_json(content: str) -> dict:
    """从 AI 响应中解析 JSON，兼容 markdown code block。"""
    # 尝试移除 markdown code block 标记
    content = content.strip()
    if content.startswith("```"):
        # 移除 ```json 和结尾 ```
        content = re.sub(r"^```(?:json)?\s*", "", content)
        content = re.sub(r"\s*```$", "", content)

    try:
        return json.loads(content)
    except json.JSONDecodeError:
        # 尝试用正则提取 JSON 对象
        match = re.search(r"\{[\s\S]*\}", content)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
        return {}


def _build_resume_info(parsed: dict) -> ResumeInfo:
    """将解析后的字典构建为 ResumeInfo 模型。"""

    # 项目经历
    projects = []
    for proj in parsed.get("project_experiences", []) or []:
        if isinstance(proj, dict):
            projects.append(ProjectExperience(
                name=proj.get("name", ""),
                description=proj.get("description", ""),
                role=proj.get("role", ""),
            ))

    return ResumeInfo(
        basic_info=BasicInfo(
            name=parsed.get("name", ""),
            phone=parsed.get("phone", ""),
            email=parsed.get("email", ""),
            address=parsed.get("address", ""),
        ),
        job_intent=JobIntent(
            position=parsed.get("position", ""),
            salary=parsed.get("salary", ""),
        ),
        background_info=BackgroundInfo(
            work_years=parsed.get("work_years", ""),
            education=Education(
                degree=parsed.get("degree", ""),
                school=parsed.get("school", ""),
                major=parsed.get("major", ""),
            ),
            skills=parsed.get("skills", []) or [],
            project_experiences=projects,
        ),
        raw_text="",
    )
