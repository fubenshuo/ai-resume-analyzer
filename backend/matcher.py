"""
简历评分与匹配模块

将解析后的简历信息与岗位描述（JD）进行匹配，计算技能匹配率、经验相关性等指标。
支持基于规则的匹配和 AI 增强匹配两种模式。
"""

from __future__ import annotations

import json
import logging
import re

import httpx

from config import settings
from models import ResumeInfo, MatchResult, MatchDetail

logger = logging.getLogger("resume-api")

# ─── 技术关键词库（可按行业扩展）───

TECH_SKILLS = {
    # 编程语言
    "Python", "Java", "JavaScript", "TypeScript", "Go", "Golang", "Rust", "C++", "CPP",
    "C#", "CSharp", "PHP", "Ruby", "Swift", "Kotlin", "Scala", "R", "MATLAB", "Shell",
    # 前端
    "React", "Vue", "Vue.js", "Angular", "Next.js", "Nuxt", "Svelte", "jQuery",
    "HTML", "HTML5", "CSS", "CSS3", "Sass", "Less", "Webpack", "Vite", "Babel",
    "小程序", "微信小程序", "React Native", "Flutter", "Electron",
    # 后端
    "Node.js", "Node", "Express", "Koa", "NestJS", "Django", "Flask", "FastAPI",
    "Spring", "SpringBoot", "Spring Cloud", "MyBatis", "Hibernate", "Gin", "Beego",
    "GraphQL", "RESTful", "gRPC", "微服务", "Microservices",
    # 数据库
    "MySQL", "PostgreSQL", "MongoDB", "Redis", "Elasticsearch", "Oracle", "SQL Server",
    "SQLite", "Cassandra", "Neo4j", "HBase", "TiDB", "ClickHouse",
    # 云计算 & DevOps
    "AWS", "阿里云", "Aliyun", "腾讯云", "Azure", "GCP", "Docker", "Kubernetes", "K8s",
    "Jenkins", "CI/CD", "Git", "GitLab", "GitHub", "Terraform", "Ansible", "Nginx",
    "Linux", "Shell脚本",
    # 数据 & AI
    "Hadoop", "Spark", "Flink", "Kafka", "RabbitMQ", "数据仓库", "数据湖",
    "TensorFlow", "PyTorch", "Keras", "机器学习", "深度学习", "NLP", "CV", "计算机视觉",
    "数据分析", "数据挖掘", "Pandas", "NumPy", "Scikit-learn", "XGBoost",
    # 产品 & 设计
    "Axure", "Figma", "Sketch", "Adobe XD", "Photoshop", "Illustrator",
    "产品设计", "用户研究", "交互设计", "UI设计", "UX设计",
    # 通用技能
    "项目管理", "敏捷开发", "Scrum", "JIRA", "Confluence", "团队管理",
    "英语", "日语", "沟通能力", "数据分析", "商业分析",
}


async def match_with_ai(resume: ResumeInfo, jd_text: str) -> MatchResult:
    """
    使用 AI 模型进行智能匹配评分。

    Args:
        resume: 简历解析结果
        jd_text: 岗位描述文本

    Returns:
        匹配结果
    """
    # 构建简历摘要
    resume_summary = _build_resume_summary(resume)

    system_prompt = """你是一个专业的招聘匹配分析专家。请根据岗位描述和候选人简历，进行匹配分析。

返回严格的 JSON 格式（不要包含任何额外说明）：
{
  "skill_match_rate": 0.0-1.0之间的浮点数（技能匹配比例）,
  "experience_relevance": 0.0-1.0之间的浮点数（工作经验相关度）,
  "education_match": 0.0-1.0之间的浮点数（学历匹配度）,
  "overall_score": 0-100之间的整数（综合评分）,
  "matched_keywords": ["匹配的关键词1", "匹配的关键词2"],
  "missing_keywords": ["缺失的关键词1", "缺失的关键词2"],
  "analysis": "综合分析文本，100字以内，说明匹配程度和建议"
}"""

    user_prompt = f"""## 岗位描述
{jd_text}

## 候选人简历信息
{resume_summary}

请分析匹配度并返回 JSON。"""

    try:
        async with httpx.AsyncClient(timeout=settings.ai_request_timeout) as client:
            response = await client.post(
                f"{settings.ai_api_base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.ai_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": settings.ai_model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": 0.1,
                    "max_tokens": 8000,
                },
            )
            if not response.is_success:
                error_body = response.text[:500]
                logger.error(f"匹配 AI API 返回错误 [{response.status_code}]: {error_body}")
                response.raise_for_status()

            data = response.json()
            message = data["choices"][0]["message"]
            content = message.get("content", "") or message.get("reasoning_content", "")

        parsed = _parse_match_json(content)
        if not parsed or not parsed.get("overall_score"):
            raise ValueError("AI 匹配结果解析为空，需回退到规则匹配")

        logger.info(f"AI 匹配原始响应长度: {len(content)} 字符")
        return _build_match_result(parsed)

    except Exception:
        # 异常向上抛给 main.py，由调用方统一 fallback 并记录 match_method
        raise


def match_by_rules(resume: ResumeInfo, jd_text: str) -> MatchResult:
    """
    基于规则的关键词匹配评分。

    评分维度：
    1. 技能匹配率 = 匹配技能数 / JD 要求技能数
    2. 经验相关性 = 工作年限与 JD 要求的匹配程度
    3. 学历匹配度 = 学历是否满足 JD 最低要求

    Args:
        resume: 简历解析结果
        jd_text: 岗位描述文本

    Returns:
        匹配结果
    """
    # 1. 提取 JD 中的技能关键词
    jd_skills = _extract_keywords(jd_text)
    resume_skills = set(s.lower() for s in resume.background_info.skills)

    # 匹配的技能
    matched = [kw for kw in jd_skills if kw.lower() in resume_skills or
               any(kw.lower() in rs for rs in resume_skills)]
    missing = [kw for kw in jd_skills if kw.lower() not in resume_skills and
               not any(kw.lower() in rs for rs in resume_skills)]

    # 技能匹配率
    skill_match_rate = len(matched) / len(jd_skills) if jd_skills else 0.0

    # 2. 工作经验相关性
    resume_years = _parse_work_years(resume.background_info.work_years)
    jd_years = _parse_work_years_from_text(jd_text)
    if jd_years > 0:
        experience_relevance = min(resume_years / jd_years, 1.0) if resume_years > 0 else 0.0
    else:
        # JD 未明确要求工作年限时，有经验则视为匹配
        experience_relevance = 0.6 if resume_years > 0 else 0.3

    # 3. 学历匹配度
    education_match = _calculate_education_match(resume, jd_text)

    # 4. 职位匹配度
    position_match = _calculate_position_match(resume, jd_text)

    # 5. 综合评分
    overall_score = round(
        skill_match_rate * 40 +       # 技能权重 40%
        experience_relevance * 20 +   # 经验权重 20%
        education_match * 20 +        # 学历权重 20%
        position_match * 20           # 职位权重 20%
    )

    return MatchResult(
        matched_keywords=matched,
        missing_keywords=missing,
        match_detail=MatchDetail(
            skill_match_rate=round(skill_match_rate, 2),
            experience_relevance=round(experience_relevance, 2),
            education_match=round(education_match, 2),
            overall_score=overall_score,
        ),
        ai_analysis=f"技能匹配 {len(matched)}/{len(jd_skills)} 项"
                    f"{'，经验匹配' if experience_relevance > 0.5 else '，经验不足'}。",
    )


# ─── 辅助函数 ───

def _extract_keywords(text: str) -> list[str]:
    """从文本中提取技术关键词（词边界匹配，避免 Java 误匹配 JavaScript）。"""
    found = []
    text_lower = text.lower()
    for skill in TECH_SKILLS:
        pattern = re.compile(r'\b' + re.escape(skill.lower()) + r'\b', re.IGNORECASE)
        if pattern.search(text):
            found.append(skill)
    return found


def _parse_work_years(work_years_str: str) -> float:
    """解析工作年限字符串为浮点数。"""
    match = re.search(r"(\d+\.?\d*)", work_years_str)
    return float(match.group(1)) if match else 0.0


def _parse_work_years_from_text(text: str) -> float:
    """从 JD 文本中提取要求的工作年限。"""
    patterns = [
        r"(\d+)\s*年(?:以上)?(?:相关)?(?:工作)?(?:经验|经历)",
        r"(?:工作经验|工作年限)[：:]\s*(\d+)\s*年",
        r"(\d+)[-–]\d+\s*年(?:工作)?(?:经验|经历)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return float(match.group(1))
    return 0.0


def _calculate_education_match(resume: ResumeInfo, jd_text: str) -> float:
    """计算学历匹配度。"""
    jd_lower = jd_text.lower()
    degree_hierarchy = {
        "博士": 5, "硕士": 4, "MBA": 4, "EMBA": 4,
        "本科": 3, "学士": 3, "大专": 2, "专科": 2,
        "高中": 1, "中专": 1,
    }

    resume_degree = resume.background_info.education.degree
    resume_level = degree_hierarchy.get(resume_degree, 0)  # 未识别学历时默认为 0 而非高估

    # 查找 JD 要求的最低学历
    jd_level = 1  # 默认无学历要求
    for deg, level in degree_hierarchy.items():
        if deg in jd_lower:
            jd_level = max(jd_level, level)

    if jd_level <= 1:
        return 0.8  # JD 无明确学历要求
    return min(resume_level / jd_level, 1.0)


def _calculate_position_match(resume: ResumeInfo, jd_text: str) -> float:
    """计算职位匹配度：简历期望职位与 JD 岗位名称的相似度。"""
    resume_position = resume.job_intent.position
    if not resume_position:
        return 0.5  # 无期望职位信息时给中性分

    # 从 JD 中提取岗位名称
    jd_position = ""
    jd_match = re.search(r"(?:岗位名称|职位名称|招聘岗位|招聘职位)[：:]\s*(.+?)(?:\n|，|。|$)", jd_text)
    if jd_match:
        jd_position = jd_match.group(1).strip()
    else:
        # 尝试匹配常见职位词
        jd_match = re.search(r"((?:Python|Java|前端|后端|全栈|算法|大数据|AI|测试|运维|产品|UI|UX)\s*(?:开发)?\s*(?:工程师|实习生|专员|经理|总监|架构师))", jd_text)
        if jd_match:
            jd_position = jd_match.group(1)

    if not jd_position:
        return 0.7  # JD 中未找到明确岗位名称

    # 分词比较
    resume_words = set(re.findall(r"[\w]+", resume_position.lower()))
    jd_words = set(re.findall(r"[\w]+", jd_position.lower()))

    if not resume_words or not jd_words:
        return 0.5

    overlap = len(resume_words & jd_words)
    union = len(resume_words | jd_words)

    # Jaccard 相似度
    jaccard = overlap / union if union > 0 else 0.0

    # 核心职位词直接匹配加分
    core_positions = {"python", "java", "前端", "后端", "全栈", "算法", "测试", "运维", "产品", "实习生", "工程师"}
    resume_core = resume_words & core_positions
    jd_core = jd_words & core_positions

    if resume_core and jd_core and resume_core == jd_core:
        return min(jaccard + 0.3, 1.0)  # 核心职位完全匹配

    return jaccard


def _parse_match_json(content: str) -> dict:
    """解析 AI 返回的匹配 JSON。"""
    content = content.strip()
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?\s*", "", content)
        content = re.sub(r"\s*```$", "", content)
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", content)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
        return {}


def _build_match_result(parsed: dict) -> MatchResult:
    """从解析字典构建 MatchResult。"""
    return MatchResult(
        matched_keywords=parsed.get("matched_keywords", []),
        missing_keywords=parsed.get("missing_keywords", []),
        match_detail=MatchDetail(
            skill_match_rate=float(parsed.get("skill_match_rate", 0)),
            experience_relevance=float(parsed.get("experience_relevance", 0)),
            education_match=float(parsed.get("education_match", 0)),
            overall_score=float(parsed.get("overall_score", 0)),
        ),
        ai_analysis=parsed.get("analysis", ""),
    )


def _build_resume_summary(resume: ResumeInfo) -> str:
    """构建简历文本摘要，供 AI 匹配使用。结构化字段为空时自动兜底使用原始文本。"""
    parts = []

    bi = resume.basic_info
    if bi.name:
        parts.append(f"姓名: {bi.name}")
    if bi.email:
        parts.append(f"邮箱: {bi.email}")
    if bi.phone:
        parts.append(f"电话: {bi.phone}")

    ji = resume.job_intent
    if ji.position:
        parts.append(f"求职意向: {ji.position}")
    if ji.salary:
        parts.append(f"期望薪资: {ji.salary}")

    bg = resume.background_info
    if bg.work_years:
        parts.append(f"工作年限: {bg.work_years}")

    edu = bg.education
    edu_parts = []
    if edu.degree:
        edu_parts.append(edu.degree)
    if edu.school:
        edu_parts.append(edu.school)
    if edu.major:
        edu_parts.append(edu.major)
    if edu_parts:
        parts.append(f"教育背景: {' / '.join(edu_parts)}")

    if bg.skills:
        parts.append(f"技能: {', '.join(bg.skills)}")

    if bg.project_experiences:
        proj_texts = []
        for p in bg.project_experiences[:3]:
            proj_texts.append(f"• {p.name}: {p.description[:200]}")
        parts.append(f"项目经历:\n" + "\n".join(proj_texts))

    # 兜底：如果结构化字段提取不完整，附上简历原始文本供 AI 参考
    structured_text = "\n".join(parts)
    if len(structured_text) < 100 and resume.raw_text:
        parts.append(f"\n--- 简历原始文本（结构化提取不完整，以下为全文）---\n{resume.raw_text[:3000]}")

    return "\n".join(parts)
