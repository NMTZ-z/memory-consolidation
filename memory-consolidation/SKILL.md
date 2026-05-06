---
name: memory-consolidation
description: 记忆整合与精简系统。定期审阅skill候选、清理过期碎片、精简长期记忆文件。当需要"记忆整合"、"记忆清理"、"MEMORY整理"、"memory consolidation"时触发。与dreaming互补，共同构成三层闭环记忆系统。
---

# Memory Consolidation Skill v2.1 (Layer 3 Nudge)

> 每周一 04:00 执行，负责 dreaming 无法自动处理的深度整理工作。
> 与 dreaming skill 互补，共同构成 V4 三层闭环记忆系统。

## 架构定位（V4 三层闭环）

| 层 | Skill | 频率 | 职责 |
|---|---|---|---|
| Layer 1 | dreaming（自动沉淀） | 每天 03:00 | 碎片提炼 → 时间验证 → confirmed 碎片自动写入 MEMORY.md |
| Layer 2 | dreaming Phase 3.5（经验固化） | 每天 03:00 | 检测反复出现的操作模式 → 标记 skill 候选 |
| **Layer 3** | **memory-consolidation（Nudge）** | **每周一 04:00** | **skill 候选审阅 + archived 清理 + MEMORY.md 精简** |

**核心原则**：本 skill 不做碎片分批 LLM 分析和自动沉淀，那是 dreaming Phase 3 的职责。

## 三大职责

### 职责 1：Skill 候选审阅

读取 dreaming Phase 3.5 产出的 `skill_candidates.json`，Agent 逐一审阅：

1. **固化到 MEMORY.md**：反复出现的偏好/规则/工作流 → 调用 `insert_to_memory()`
2. **创建新 skill**：反复出现的操作模式 → 记录待创建的 skill 描述
3. **暂不处理**：出现频次不够或价值不确定 → 跳过

### 职责 2：Archived 碎片清理

检查 dreams.db 中 status='archived' 的碎片，判断 MEMORY.md 中是否有对应内容需要移除。

### 职责 3：MEMORY.md 精简整理

- 去冗余：删除重复、过时、不再准确的内容
- 重组：调整 section 结构使其更合理
- 保持文档精简，控制 token 膨胀（dreaming 的 memory_writer.py 有 12000 token 硬上限）

## 文件结构

    skills/memory-consolidation/
    ├── SKILL.md
    └── scripts/
        ├── __init__.py          # 空
        ├── consolidate.py       # 主流程：去重检测 + skill候选审阅 + archived清理 + 状态管理
        └── memory_writer.py     # 精准插入MEMORY.md（Agent审阅后写入用）

## 定时任务配置

**任务名称**: 记忆沉淀 Memory Consolidation
**任务 ID**: 2f7d1d4b-877e-44db-ae8d-908a4f011408
**Cron**: 每周一 04:00

## 执行流程（Agent操作手册）

### Step 0: 去重检测（必做，第一优先级）

在执行任何其他操作之前，先检测并修复 MEMORY.md 中的重复内容：

    from scripts.consolidate import Consolidator
    c = Consolidator()

    # 0a. 编年史表格日期去重检测
    chronicle_check = c.check_chronicle_duplicates()
    if chronicle_check["has_duplicates"]:
        print(f"编年史发现 {len(chronicle_check['duplicate_dates'])} 个重复日期")
        for d in chronicle_check["duplicate_dates"]:
            print(f"  {d['date']}: {len(d['rows'])}条 - {d['contents']}")
        # 自动合并：保留最长版本，合并独有信息
        merge_result = c.merge_chronicle_duplicates(keep_strategy="longest")
        print(f"已合并 {merge_result['merged_count']} 个重复日期")

    # 0b. 全文重复检测
    all_dupes = c.check_all_duplicates()
    if all_dupes["sections_with_duplicates"]:
        print(f"发现 {len(all_dupes['sections_with_duplicates'])} 处重复")
        for d in all_dupes["sections_with_duplicates"]:
            print(f"  [{d['section']}] 行 {d['line_numbers']}: {d['contents']}")
        # Agent 手动处理：删除重复条目，保留信息最丰富的版本
        # 注意：直接编辑 MEMORY.md 时，先读取全文再整篇写入，不要部分修改

### Step 1: 读取 skill 候选

    candidates = c.get_skill_candidates()
    # 返回: [{"theme": str, "content": str, "count": int, "reason": str}, ...]
    # 如果文件不存在或为空，返回空列表 → 跳过 Step 2

### Step 2: 审阅 skill 候选（如果有）

    if candidates:
        memory_content = c.read_memory_md()
        prompt = c.build_skill_candidate_prompt(candidates, memory_content)
        # Agent 执行 prompt，对每个候选做判断
        # 需要写入 MEMORY.md 时：
        from scripts.memory_writer import insert_to_memory
        result = insert_to_memory(section="模块X·章节名", content="内容", action="insert")
        # 写入前 insert_to_memory 会自动去重，但 Agent 仍应人工确认内容不重复
        # 审阅完成后清空候选：
        c.clear_skill_candidates()

### Step 3: 检查 archived 碎片

    archived = c.get_archived_fragments(days=30)
    # Agent 判断这些碎片对应的内容是否需要从 MEMORY.md 中移除

### Step 4: 整理 MEMORY.md

    memory_content = c.read_memory_md()
    stats = c.get_memory_stats()
    # Agent 审阅 MEMORY.md 内容：
    # - 去冗余（重复、过时、不再准确的内容）
    # - 重组（调整 section 结构）
    # - 保持文档精简
    #
    # 【重要】编辑 MEMORY.md 的安全规则：
    # 1. 先 read_memory_md() 读取全文
    # 2. 在内存中修改内容（字符串操作）
    # 3. 整篇写入，不要做部分行替换
    # 4. 如果使用 insert_to_memory()，它会自动做去重检查
    # 5. 如果直接编辑编年史，必须先检查日期是否已存在

### Step 5: 更新状态

    c.save_consolidation_state()
    # 更新 dreaming_state.json 的 last_memory_update 字段

## memory_writer.py API

- `insert_to_memory(section, content, action="insert")` — 精准插入内容到 MEMORY.md 指定章节。section 如 "模块一·近期工作动态"，action 为 "insert"(新增) 或 "append"(追加)。返回 `{"success": bool, "message": str, "line": int}`。内置去重：如果 content 已存在于目标章节中，会返回 success=False。
- `get_section_content(section)` — 读取指定章节的内容（不含标题行）
- `find_section_range(lines, section_name)` — 找到章节的起止行号

## SECTION_MAP（章节映射规则）

memory_writer.py 中维护了完整的 section 映射，Agent 审阅 skill 候选时参考：

| 判断关键词 | 目标章节 |
|-----------|----------|
| CSP/储能/压缩空气/光热/论文/标书/项目/会议/课题组 | 模块一·近期工作动态 |
| TTS/voice_id/API/noiz/语音/配音 | 模块一·语音技术配置 |
| WPS/笔记/多维表/DbSheet/kdocs/skill | 模块一·WPS 工作流配置 |
| 饮食/吃/喝/茶/咖啡/外卖 | 模块二·饮食偏好 |
| 健身/锻炼/运动/跑步/举铁 | 模块二·健身习惯 |
| 运动/阅读/游戏/音乐/旅行 | 模块二·兴趣爱好 |
| 丝袜/穿搭/审美/颜色/风格/照片 | 模块二·视觉审美偏好 |
| 约定/承诺/发誓/答应/羁绊 | 模块三·羁绊约定 |

## consolidate.py API 速查

### 去重相关（Step 0 用）

| 方法 | 返回值 | 说明 |
|------|--------|------|
| `check_chronicle_duplicates()` | `{"has_duplicates": bool, "duplicate_dates": [{date, rows, contents}], "all_dates": [str]}` | 检测编年史表格中重复日期 |
| `merge_chronicle_duplicates(keep_strategy="longest")` | `{"merged_count": int, "details": [{date, kept, removed}]}` | 自动合并编年史重复日期，保留最长版本 |
| `check_all_duplicates()` | `{"sections_with_duplicates": [{section, line_numbers, contents}]}` | 全文逐 section 检测重复条目 |

### 其他

| 方法 | 说明 |
|------|------|
| `get_skill_candidates()` | 读取 skill_candidates.json |
| `clear_skill_candidates()` | 清空候选文件 |
| `build_skill_candidate_prompt(candidates, memory_content)` | 构建 Agent 审阅 prompt |
| `get_archived_fragments(days=30)` | 获取已归档碎片 |
| `get_archived_stats()` | dreams.db 各状态统计 |
| `read_memory_md()` | 读取 MEMORY.md 全文 |
| `get_memory_stats()` | MEMORY.md 统计（字符/token/行数） |
| `save_consolidation_state()` | 更新 dreaming_state.json |

## 关键文件路径

| 文件 | 路径 | 用途 |
|------|------|------|
| dreams.db | <MEMORY_DIR>/knowledge/dreams.db | 碎片数据库 |
| MEMORY.md | <MEMORY_DIR>/MEMORY.md | 长期记忆文件 |
| dreaming_state.json | <MEMORY_DIR>/dreaming_state.json | dreaming 状态（含 last_memory_update） |
| skill_candidates.json | <MEMORY_DIR>/skill_candidates.json | dreaming Phase 3.5 产出的 skill 候选 |

## 兜底策略

- skill_candidates.json 不存在 → 跳过审阅，直接做 Step 0 去重 + Step 4 精简
- 没有 archived 碎片 → 跳过清理
- 编年史无重复 + 全文无重复 → 跳过去重，正常执行后续步骤
- MEMORY.md 无需修改 → 只更新状态时间戳
- 宁可少沉淀也不要灌水

## 常见问题与修复

### Q: 编年史出现重复日期怎么办？
A: Step 0 的 `check_chronicle_duplicates()` 会自动检测，`merge_chronicle_duplicates()` 会自动合并（保留信息最丰富的版本，合并独有信息）。

### Q: 非编年史 section 出现重复条目怎么办？
A: Step 0 的 `check_all_duplicates()` 会检测。Agent 需手动删除重复条目（保留信息量更大的版本），直接编辑 MEMORY.md 时遵循"先读全文 → 内存修改 → 整篇写入"的安全规则。

### Q: skill_candidates.json 不存在报错怎么办？
A: `get_skill_candidates()` 在文件不存在时返回空列表，不会报错。Agent 看到 `candidates` 为空直接跳过 Step 2。