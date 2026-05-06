"""记忆沉淀 Layer 3 (Nudge)：每周一次的深度整理。

V4 架构中的 Layer 3 职责（与 dreaming Layer 1/2 互补）：
  - dreaming（每天）：碎片提炼 -> 时间验证 -> 自动沉淀 confirmed 碎片到 MEMORY.md
  - 本 skill（每周）：skill 候选审阅 + archived 碎片清理 + MEMORY.md 精简整理

不负责：碎片分批 LLM 分析和自动沉淀（那是 dreaming Phase 3 的活）。
"""

import json
import os
import re
import sqlite3
from datetime import datetime

MEMORY_DIR = r"./memory"
DB_PATH = os.path.join(MEMORY_DIR, "knowledge", "dreams.db")
MEMORY_MD = os.path.join(MEMORY_DIR, "MEMORY.md")
STATE_FILE = os.path.join(MEMORY_DIR, "dreaming_state.json")
SKILL_CANDIDATES_FILE = os.path.join(MEMORY_DIR, "skill_candidates.json")


class Consolidator:
    """Layer 3 Nudge：每周记忆沉淀整理器。"""

    def __init__(self, memory_dir: str = None):
        global MEMORY_DIR, DB_PATH, MEMORY_MD, STATE_FILE, SKILL_CANDIDATES_FILE
        if memory_dir:
            MEMORY_DIR = memory_dir
            DB_PATH = os.path.join(MEMORY_DIR, "knowledge", "dreams.db")
            MEMORY_MD = os.path.join(MEMORY_DIR, "MEMORY.md")
            STATE_FILE = os.path.join(MEMORY_DIR, "dreaming_state.json")
            SKILL_CANDIDATES_FILE = os.path.join(MEMORY_DIR, "skill_candidates.json")

    # ========== 1. Skill 候选审阅 ==========

    def get_skill_candidates(self) -> list[dict]:
        """读取 dreaming Phase 3.5 标记的 skill 候选列表。

        Returns:
            [{"theme": str, "content": str, "count": int, "reason": str}, ...]
            如果文件不存在或为空，返回空列表。
        """
        if not os.path.exists(SKILL_CANDIDATES_FILE):
            return []

        try:
            with open(SKILL_CANDIDATES_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("candidates", [])
        except (json.JSONDecodeError, KeyError):
            return []

    def clear_skill_candidates(self):
        """处理完 skill 候选后清空文件。"""
        if os.path.exists(SKILL_CANDIDATES_FILE):
            os.remove(SKILL_CANDIDATES_FILE)
            return True
        return False

    def build_skill_candidate_prompt(self, candidates: list[dict], memory_content: str) -> str:
        """为 Agent 构建 skill 候选审阅的 prompt。

        Args:
            candidates: skill 候选列表
            memory_content: 当前 MEMORY.md 内容

        Returns:
            供 Agent 执行的 prompt 文本
        """
        if not candidates:
            return ""

        lines = []
        for i, c in enumerate(candidates, 1):
            lines.append(f"{i}. [主题: {c.get('theme', '?')}] {c.get('content', '')[:100]}")
            lines.append(f"   出现次数: {c.get('count', '?')} | 检测原因: {c.get('reason', '?')}")
        candidates_text = "\n".join(lines)

        return f"""以下是 dreaming 自动检测到的 skill 候选项，请逐一审阅：

## skill 候选列表（共 {len(candidates)} 项）
{candidates_text}

## 当前 MEMORY.md（参考）
{memory_content}

## 审阅规则
对每个候选项，判断以下之一：
1. **固化到 MEMORY.md**：反复出现的偏好/规则/工作流，值得长期记忆
   -> 调用 memory_writer.insert_to_memory(section="目标章节", content="内容", action="insert")
2. **创建新 skill**：反复出现的操作模式，应该固化为自动化 skill
   -> 记录待创建的 skill 描述，后续手动处理
3. **暂不处理**：出现频次不够或价值不确定
   -> 跳过，等下次沉淀时再评估

注意：
- 不要修改 MEMORY.md 中已有的内容
- 如果候选内容已在 MEMORY.md 中存在，跳过
- 审阅完成后调用 clear_skill_candidates() 清空候选文件"""

    # ========== 2. Archived 碎片清理 ==========

    def get_archived_fragments(self, days: int = 30) -> list[dict]:
        """获取已归档的碎片列表，供 Agent 判断是否需要从 MEMORY.md 中移除。

        Args:
            days: 归档天数阈值（默认 30 天前归档的）

        Returns:
            [{"id": int, "date": str, "category": str, "content": str, "archived_days": int}, ...]
        """
        if not os.path.exists(DB_PATH):
            return []

        conn = sqlite3.connect(DB_PATH)
        try:
            cutoff = (datetime.now() - __import__('datetime').timedelta(days=days)).strftime('%Y-%m-%d')
            rows = conn.execute(
                "SELECT id, date, category, content FROM dreams "
                "WHERE status = 'archived' AND last_seen <= ? "
                "ORDER BY last_seen ASC",
                (cutoff,)
            ).fetchall()
            result = []
            for r in rows:
                result.append({
                    "id": r[0], "date": r[1], "category": r[2],
                    "content": r[3], "archived_days": days,
                })
            return result
        finally:
            conn.close()

    def get_archived_stats(self) -> dict:
        """获取 dreams.db 中各状态的碎片统计。"""
        if not os.path.exists(DB_PATH):
            return {"total": 0, "candidate": 0, "confirmed": 0, "archived": 0}

        conn = sqlite3.connect(DB_PATH)
        try:
            stats = {}
            total = 0
            for row in conn.execute("SELECT status, COUNT(*) FROM dreams GROUP BY status"):
                stats[row[0]] = row[1]
                total += row[1]
            stats["total"] = total
            return stats
        finally:
            conn.close()

    # ========== 3. MEMORY.md 精简整理 ==========

    def read_memory_md(self) -> str:
        """读取当前 MEMORY.md 内容。"""
        if os.path.exists(MEMORY_MD):
            with open(MEMORY_MD, 'r', encoding='utf-8') as f:
                return f.read()
        return ""

    def get_memory_stats(self) -> dict:
        """获取 MEMORY.md 的统计信息。"""
        content = self.read_memory_md()
        chars = len(content)
        tokens = int(chars * 1.5)
        return {
            "chars": chars,
            "estimated_tokens": tokens,
            "lines": content.count('\n') + 1 if content else 0,
        }

    # ========== 4. 编年史去重检测与合并 ==========

    def check_chronicle_duplicates(self) -> dict:
        """检测编年史表格中的重复日期条目。

        Returns:
            {
                "has_duplicates": bool,
                "duplicate_dates": [{"date": str, "rows": [int, ...], "contents": [str, ...]}],
                "all_dates": [str],  # 编年史中所有日期（升序）
            }
        """
        content = self.read_memory_md()
        if not content:
            return {"has_duplicates": False, "duplicate_dates": [], "all_dates": []}

        lines = content.split('\n')

        # 找编年史章节范围
        chronicle_start = None
        chronicle_end = len(lines)
        for i, line in enumerate(lines):
            stripped = line.strip()
            if chronicle_start is None and '编年史' in stripped and '###' in stripped:
                chronicle_start = i
            elif chronicle_start is not None and (stripped.startswith('### ') or stripped.startswith('## ')):
                chronicle_end = i
                break

        if chronicle_start is None:
            return {"has_duplicates": False, "duplicate_dates": [], "all_dates": []}

        # 提取编年史表格中的日期
        date_rows = {}  # date -> [(line_number, content), ...]
        date_order = []

        for i in range(chronicle_start, chronicle_end):
            m = re.match(r'\|\s*(\d{4}-\d{2}-\d{2})\s*\|', lines[i].strip())
            if m:
                date = m.group(1)
                # 提取事件描述（第二列）
                parts = [p.strip() for p in lines[i].strip().split('|')]
                event_text = parts[2] if len(parts) > 2 else ""
                if date not in date_rows:
                    date_rows[date] = []
                    date_order.append(date)
                date_rows[date].append({"line": i + 1, "content": event_text})

        # 找出重复日期
        duplicates = []
        for date in date_order:
            rows = date_rows[date]
            if len(rows) > 1:
                duplicates.append({
                    "date": date,
                    "rows": [r["line"] for r in rows],
                    "contents": [r["content"] for r in rows],
                })

        return {
            "has_duplicates": len(duplicates) > 0,
            "duplicate_dates": duplicates,
            "all_dates": date_order,
        }

    def merge_chronicle_duplicates(self, keep_strategy: str = "longest") -> dict:
        """合并编年史中的重复日期条目。

        同一日期的多个条目会被合并为一个：保留信息最丰富的版本，
        并将其他版本中的独特信息合并进来。

        Args:
            keep_strategy: "longest" 保留最长版本，"newest" 保留最后出现的

        Returns:
            {"merged_count": int, "details": [{"date": str, "kept": str, "removed": [str]}]}
        """
        content = self.read_memory_md()
        if not content:
            return {"merged_count": 0, "details": []}

        lines = content.split('\n')
        dup_check = self.check_chronicle_duplicates()

        if not dup_check["has_duplicates"]:
            return {"merged_count": 0, "details": []}

        details = []
        lines_to_remove = set()

        for dupe in dup_check["duplicate_dates"]:
            date = dupe["date"]
            all_contents = dupe["contents"]

            if keep_strategy == "longest":
                # 保留最长版本（信息最丰富）
                kept_idx = max(range(len(all_contents)), key=lambda i: len(all_contents[i]))
            else:
                # 保留最后出现的
                kept_idx = len(all_contents) - 1

            kept_content = all_contents[kept_idx]

            # 从其他版本中提取独有信息片段（分号分隔的事件）
            all_events = set()
            for c in all_contents:
                for event in re.split(r'[；;]', c):
                    event = event.strip()
                    if event and event not in kept_content:
                        all_events.add(event)

            # 如果有独有信息，追加到保留版本
            if all_events:
                extra = '；'.join(sorted(all_events))
                merged_content = kept_content.rstrip() + '；' + extra
            else:
                merged_content = kept_content

            # 构造合并后的行
            merged_line = f"| {date} | {merged_content} |"

            # 标记要删除的行（除保留的那行外），并更新保留行
            row_indices = dupe["rows"]  # 1-based
            kept_line_no = row_indices[kept_idx]

            for idx, row_no in enumerate(row_indices):
                if idx == kept_idx:
                    # 更新保留行内容
                    lines[row_no - 1] = merged_line
                else:
                    # 标记删除
                    lines_to_remove.add(row_no - 1)

            removed = [all_contents[i] for i in range(len(all_contents)) if i != kept_idx]
            details.append({
                "date": date,
                "kept": merged_content,
                "removed": removed,
                "removed_lines": [row_indices[i] for i in range(len(row_indices)) if i != kept_idx],
            })

        # 删除标记行（从后往前删避免索引偏移）
        for line_idx in sorted(lines_to_remove, reverse=True):
            lines.pop(line_idx)

        # 写回文件
        new_content = '\n'.join(lines)
        with open(MEMORY_MD, 'w', encoding='utf-8') as f:
            f.write(new_content)

        return {
            "merged_count": len(details),
            "details": details,
        }

    # ========== 5. 通用去重检测 ==========

    def check_all_duplicates(self) -> dict:
        """扫描 MEMORY.md 全文检测潜在重复内容。

        逐 section 检测，返回每个 section 中疑似重复的条目。

        Returns:
            {
                "sections_with_duplicates": [
                    {
                        "section": str,
                        "line_numbers": [int, ...],
                        "contents": [str, ...],
                    }
                ]
            }
        """
        content = self.read_memory_md()
        if not content:
            return {"sections_with_duplicates": []}

        lines = content.split('\n')
        current_section = "(header)"
        section_lines = {}  # section_name -> [(line_no, content), ...]
        section_order = []

        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith('### '):
                section_name = stripped.lstrip('#').strip()
                current_section = section_name
                if current_section not in section_lines:
                    section_lines[current_section] = []
                    section_order.append(current_section)
                continue
            if stripped.startswith('## '):
                current_section = "(module_header)"
                continue

            # 跳过空行、表格分隔行、引用行
            if not stripped or stripped.startswith('|') and set(stripped.replace('|', '').replace('-', '').replace(' ', '')) == set():
                continue
            if stripped.startswith('>'):
                continue

            # 只关注内容行（以 - 开头的条目 或 表格数据行）
            if stripped.startswith('- ') or (stripped.startswith('|') and not stripped.startswith('|--') and not stripped.startswith('| --')):
                if current_section not in section_lines:
                    section_lines[current_section] = []
                    section_order.append(current_section)
                section_lines[current_section].append((i + 1, stripped))

        # 逐 section 检测重复
        results = []
        for sec_name in section_order:
            entries = section_lines[sec_name]
            if len(entries) < 2:
                continue

            # 按内容前40字分组
            groups = {}
            for line_no, content_text in entries:
                # 标准化：去掉日期后缀、去空格
                normalized = re.sub(r'[（(]\d{4}-\d{2}-\d{2}[）)]', '', content_text)
                normalized = re.sub(r'[（(]\d{4}-\d{2}-\d{2}\s*自动沉淀[）)]', '', normalized)
                normalized = normalized.strip().lower()
                # 取前40字作为指纹
                fingerprint = normalized[:40]
                if fingerprint not in groups:
                    groups[fingerprint] = []
                groups[fingerprint].append((line_no, content_text))

            # 找出有重复指纹的组
            for fingerprint, group in groups.items():
                if len(group) > 1:
                    # 进一步验证：如果内容前30字相同，认为是重复
                    for a_idx in range(len(group)):
                        for b_idx in range(a_idx + 1, len(group)):
                            a_text = re.sub(r'[（(][^)）]*[）)]', '', group[a_idx][1]).strip()
                            b_text = re.sub(r'[（(][^)）]*[）)]', '', group[b_idx][1]).strip()
                            if a_text[:30] == b_text[:30]:
                                results.append({
                                    "section": sec_name,
                                    "line_numbers": [group[a_idx][0], group[b_idx][0]],
                                    "contents": [group[a_idx][1], group[b_idx][1]],
                                })
                                break

        return {"sections_with_duplicates": results}

    # ========== 6. 状态管理 ==========

    def save_consolidation_state(self) -> str:
        """更新 dreaming_state.json 的 last_memory_update 字段。"""
        today = datetime.now().strftime('%Y-%m-%d')

        state = {}
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE, 'r', encoding='utf-8') as f:
                    state = json.load(f)
            except (json.JSONDecodeError, KeyError):
                pass

        state["last_memory_update"] = today
        state["last_consolidation_run"] = datetime.now().isoformat()

        os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
        with open(STATE_FILE, 'w', encoding='utf-8') as f:
            json.dump(state, f, ensure_ascii=False, indent=2)

        return today

    def get_last_consolidation_date(self) -> str:
        """获取上次沉淀日期。"""
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE, 'r', encoding='utf-8') as f:
                    state = json.load(f)
                return state.get("last_memory_update", "")
            except (json.JSONDecodeError, KeyError):
                pass
        return ""
