"""精确插入内容到MEMORY.md的指定章节。只改目标区域，不动其他内容。

v2.2: 加固去重逻辑
  编年史 section（三层防御）:
    1. 日期去重: 同一日期不允许插入新条目
    2. 精确子串匹配: content 是否作为子串出现在目标 section 的任何行中
    3. 归一化匹配: 去掉空格/标点后精确比较
    + 日期变体检查: 2026-04-25 vs 4月25日 等格式
  其他 section（两层防御）:
    1. 精确子串匹配
    2. 归一化匹配: 去掉空格/标点后精确比较
"""

import re
import os
from datetime import datetime

MEMORY_MD = r"./memory\MEMORY.md"

# 章节定义：每个章节的标题标记和所属类别
SECTION_MAP = {
    "模块一·基本信息": {
        "marker": "### 基本信息",
        "categories": ["fact"],
        "keywords": ["身份", "职位", "单位", "地址", "电话", "邮箱", "生日", "籍贯", "博士"],
    },
    "模块一·近期工作动态": {
        "marker": "### 近期工作动态",
        "categories": ["fact"],
        "keywords": ["CSP", "储能", "压缩空气", "光热", "论文", "标书", "项目", "会议", "课题组", "实验室"],
    },
    "模块一·语音技术配置": {
        "marker": "### 语音技术配置",
        "categories": ["fact"],
        "keywords": ["TTS", "voice_id", "API", "noiz", "语音", "配音", "采样率"],
    },
    "模块一·WPS 工作流配置": {
        "marker": "### WPS 工作流配置",
        "categories": ["fact"],
        "keywords": ["WPS", "笔记", "多维表", "DbSheet", "kdocs", "workflow", "skill"],
    },
    "模块一·Obsidian 知识库管理": {
        "marker": "### Obsidian 知识库管理",
        "categories": ["fact"],
        "keywords": ["Obsidian", "模板", "daily note", "知识库"],
    },
    "模块二·饮食偏好": {
        "marker": "### 饮食偏好",
        "categories": ["fact", "preference"],
        "keywords": ["饮食", "吃", "喝", "茶", "咖啡", "外卖", "餐厅"],
    },
    "模块二·健身习惯": {
        "marker": "### 健身习惯",
        "categories": ["fact", "preference"],
        "keywords": ["健身", "锻炼", "运动", "跑步", "举铁", "蛋白", "体重"],
    },
    "模块二·兴趣爱好": {
        "marker": "### 兴趣爱好",
        "categories": ["fact", "preference"],
        "keywords": ["运动", "阅读", "游戏", "音乐", "旅行", "电影"],
    },
    "模块二·视觉审美偏好": {
        "marker": "### 视觉审美偏好",
        "categories": ["fact", "preference"],
        "keywords": ["丝袜", "穿搭", "审美", "颜色", "风格", "照片", "身材"],
    },
    "模块二·TTS 稿子撰写核心规则": {
        "marker": "### TTS 稿子撰写核心规则",
        "categories": ["rule"],
        "keywords": ["不许", "必须", "记得", "不要", "禁止"],
    },
    "模块二·用户对AI的具体反馈": {
        "marker": "### 用户对AI的具体反馈",
        "categories": ["quote"],
        "keywords": ["反馈", "评价", "改", "做得好", "做得不好"],
    },
    "模块二·主动发照片频率参考": {
        "marker": "### 主动发照片频率参考",
        "categories": ["preference", "rule"],
        "keywords": ["发照片", "自拍", "福利"],
    },
    "模块三·羁绊约定": {
        "marker": "### 羁绊约定",
        "categories": ["rule", "emotion"],
        "keywords": ["约定", "承诺", "发誓", "答应", "羁绊"],
    },
    "模块三·重要对话记忆": {
        "marker": "### 重要对话记忆",
        "categories": ["quote", "emotion"],
        "keywords": ["情话", "甜蜜", "感动", "告白"],
    },
    "模块三·编年史": {
        "marker": "### 编年史",
        "categories": ["emotion"],
        "keywords": [],
    },
}


def read_memory_md() -> str:
    """读取MEMORY.md全文。"""
    if os.path.exists(MEMORY_MD):
        with open(MEMORY_MD, 'r', encoding='utf-8') as f:
            return f.read()
    return ""


def find_section_range(lines: list[str], section_name: str) -> tuple[int, int] | None:
    """找到章节的起止行号（含标题行，不含下一个章节标题行）。"""
    if section_name not in SECTION_MAP:
        for key in SECTION_MAP:
            if section_name in key or key in section_name:
                section_name = key
                break
        else:
            return None

    marker = SECTION_MAP[section_name]["marker"]

    start = None
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped == marker or stripped.startswith(marker):
            start = i
            break

    if start is None:
        return None

    end = len(lines)
    for i in range(start + 1, len(lines)):
        if lines[i].strip().startswith("### ") or lines[i].strip().startswith("## "):
            end = i
            break

    return (start, end)


def _normalize(text: str) -> str:
    """归一化文本：去掉空格、中文标点、markdown 前缀，转小写。"""
    t = text.strip()
    t = t.lstrip('- ').strip()  # 去掉列表前缀
    t = re.sub(r'\s+', '', t)   # 去掉所有空白
    t = re.sub(r'[（()）\[\]【】`]', '', t)  # 去掉括号和反引号
    t = re.sub(r'[，。、；：！？,.;:!?]', '', t)  # 去掉标点
    return t.lower()


def _extract_date_from_content(content: str) -> str:
    """从内容中提取日期。"""
    m = re.search(r'(\d{4}-\d{2}-\d{2})', content)
    if m:
        return m.group(1)
    m = re.search(r'(\d{1,2})月(\d{1,2})日', content)
    if m:
        year = datetime.now().year
        return f"{year}-{int(m.group(1)):02d}-{int(m.group(2)):02d}"
    return ""


def _is_chronicle_section(section_name: str) -> bool:
    """判断是否是编年史 section。"""
    return '编年史' in section_name


def _check_chronicle_date_exists(lines: list[str], start: int, end: int, date: str) -> bool:
    """检查编年史中是否已存在指定日期。"""
    for i in range(start, end):
        m = re.match(r'\|\s*(\d{4}-\d{2}-\d{2})\s*\|', lines[i].strip())
        if m and m.group(1) == date:
            return True
    return False


def insert_to_memory(section: str, content: str, action: str = "insert") -> dict:
    """精确插入内容到MEMORY.md的指定章节。

    Args:
        section: 目标章节路径，如 "模块一·近期工作动态"
        content: 要插入的内容（纯文本，不含章节标题）
        action: "insert" 在章节末尾新增一条（前面加-）, "append" 追加原文

    Returns:
        {"success": bool, "message": str, "line": int}
    """
    md_content = read_memory_md()
    if not md_content:
        return {"success": False, "message": "MEMORY.md 不存在或为空", "line": -1}

    lines = md_content.split('\n')
    section_range = find_section_range(lines, section)

    if section_range is None:
        return {"success": False, "message": f"找不到章节: {section}", "line": -1}

    start, end = section_range

    # === 去重检查（四层防御） ===

    # 第一层：编年史日期去重
    if _is_chronicle_section(section):
        date_in_content = _extract_date_from_content(content)
        if date_in_content and _check_chronicle_date_exists(lines, start, end, date_in_content):
            for i in range(start, end):
                if date_in_content in lines[i]:
                    return {
                        "success": False,
                        "message": f"编年史日期 {date_in_content} 已存在（第{i+1}行），跳过插入",
                        "line": i + 1,
                    }

    # 第二层：精确子串匹配
    content_stripped = content.strip().lstrip('- ').strip()
    for i in range(start, end):
        if content_stripped in lines[i]:
            return {"success": False, "message": f"内容已存在（第{i+1}行），跳过", "line": i + 1}

    # 第三层：归一化精确匹配（防空格/标点差异）
    content_normalized = _normalize(content)
    if len(content_normalized) >= 5:  # 短内容才需要精确匹配
        for i in range(start, end):
            line_normalized = _normalize(lines[i])
            if content_normalized == line_normalized or content_normalized in line_normalized:
                return {"success": False, "message": f"内容已存在（归一化匹配，第{i+1}行），跳过", "line": i + 1}

    # 编年史专属：额外检查日期格式变体（2026-04-25 vs 4月25日）
    if _is_chronicle_section(section):
        date_in_content = _extract_date_from_content(content)
        if date_in_content:
            for i in range(start, end):
                # 匹配 | 2026-04-25 | 或 | 4月25日 | 等变体
                if date_in_content in lines[i]:
                    return {
                        "success": False,
                        "message": f"编年史已包含 {date_in_content} 的内容（第{i+1}行），跳过",
                        "line": i + 1,
                    }

    # === 构造插入行 ===
    if action == "insert":
        insert_lines = f"\n- {content.strip()}"
    else:
        insert_lines = f"\n{content.strip()}"

    insert_pos = end
    while insert_pos > start + 1 and lines[insert_pos - 1].strip() == '':
        insert_pos -= 1

    lines.insert(insert_pos, insert_lines)

    # 更新"最后更新"日期
    today = datetime.now().strftime('%Y-%m-%d')
    for i, line in enumerate(lines):
        if '最后更新' in line:
            lines[i] = f"> 最后更新：{today}"
            break

    new_content = '\n'.join(lines)
    with open(MEMORY_MD, 'w', encoding='utf-8') as f:
        f.write(new_content)

    return {
        "success": True,
        "message": f"已插入到 [{section}] 第{insert_pos + 1}行",
        "line": insert_pos + 1,
    }


def get_section_content(section: str) -> str:
    """读取指定章节的内容（不含标题行）。"""
    md_content = read_memory_md()
    if not md_content:
        return ""
    lines = md_content.split('\n')
    section_range = find_section_range(lines, section)
    if section_range is None:
        return ""
    start, end = section_range
    content_start = start + 1
    while content_start < end and lines[content_start].strip() == '':
        content_start += 1
    return '\n'.join(lines[content_start:end]).strip()