"""
文本清洗与结构化处理

对 PDF 提取后的原始文本进行清洗、分段、规范化，为 AI 提取做准备。
"""

from __future__ import annotations

import re

from config import settings


def clean_resume_text(raw_text: str) -> str:
    """
    清洗简历文本，去除冗余字符并规范化格式。

    处理步骤：
    1. 去除控制字符（保留换行）
    2. 合并连续空行
    3. 规范化标点与空格
    4. 截断过长文本（保留前 8000 字符供 AI 分析）

    Args:
        raw_text: PDF 解析后的原始文本

    Returns:
        清洗后的规范文本
    """
    if not raw_text:
        return ""

    text = raw_text

    # 1. 去除 ANSI 控制字符和零宽字符
    text = re.sub(r"\x1b\[[0-9;]*[a-zA-Z]", "", text)
    text = re.sub(r"[​‌‍‎‏﻿]", "", text)

    # 2. 统一换行为 \n
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # 3. 合并 3 个以上连续换行为双换行（段落分隔）
    text = re.sub(r"\n{3,}", "\n\n", text)

    # 4. 去除行内的制表符替换为空格
    text = text.replace("\t", " ")

    # 5. 合并多个空格为一个
    text = re.sub(r" {2,}", " ", text)

    # 6. 去除纯空白行首尾
    lines = [line.strip() for line in text.split("\n")]
    text = "\n".join(line for line in lines if line)

    # 7. 规范化标点符号
    text = text.replace("：", ":")

    # 8. 限制长度（AI 模型有 token 限制）
    if len(text) > settings.text_max_chars:
        text = text[:settings.text_max_chars] + "\n\n[文本过长，已截断...]"

    return text.strip()


def extract_sections(text: str) -> dict[str, str]:
    """
    尝试将简历文本按常见标题分段。

    识别的分段标题包括：
    基本信息、求职意向、教育背景、工作经历、项目经历、技能、自我评价等。

    Args:
        text: 清洗后的简历文本

    Returns:
        分段字典，key 为段落标题，value 为段落内容
    """
    sections: dict[str, str] = {}

    # 常见简历段落标题模式
    section_patterns = [
        (r"(?:基本信息|个人信息|个人资料)", "基本信息"),
        (r"(?:求职意[向願]|期望职位|求职目标|应聘岗位)", "求职意向"),
        (r"(?:教育背景|教育经历|学历|学习经历)", "教育背景"),
        (r"(?:工作经历|工作经验|工作履历|从业经历)", "工作经历"),
        (r"(?:项目经历|项目经验|项目简介)", "项目经历"),
        (r"(?:专业技能|技能特长|技术栈|技能)", "技能"),
        (r"(?:自我评价|个人评价|自我介绍|关于我)", "自我评价"),
        (r"(?:实习经历|实习经验)", "实习经历"),
        (r"(?:证书|资格证书|获奖)", "证书与获奖"),
    ]

    lines = text.split("\n")
    current_section = "其他"
    sections[current_section] = ""

    for line in lines:
        matched = False
        for pattern, section_name in section_patterns:
            if re.search(pattern, line):
                current_section = section_name
                if section_name not in sections:
                    sections[section_name] = ""
                matched = True
                break
        if not matched:
            sections[current_section] += line + "\n"

    return {k: v.strip() for k, v in sections.items() if v.strip()}
