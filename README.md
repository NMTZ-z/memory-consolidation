# memory-consolidation

> Periodic memory cleanup and consolidation for AI agents. Reviews skill candidates, archives stale fragments, and deduplicates long-term memory files.

## Overview

A self-contained skill for the [WPS Lingxi Claw](https://ai.wps.cn) AI agent platform. Install by copying the `memory-consolidation/` directory into your Claw skills folder.

## Installation

Copy the entire `memory-consolidation/` folder to your WPS Lingxi Claw skills directory:

```
<USER_HOME>/AppData/Roaming/WPS 灵犀/serverdir/skills/memory-consolidation/
```

## Dependencies

This skill requires the following skills to be installed:

- **dreaming**

## Environment Variables

All sensitive configuration is managed via environment variables. Copy `.env.example` (if provided) to `.env` and fill in your values:

- `MEMORY_DIR`
- `WPS_SKILLS_DIR`

## Usage

Trigger this skill by mentioning its capabilities in your conversation with the AI agent. See `SKILL.md` for detailed usage instructions and workflow documentation.

## File Structure

```
memory-consolidation/
├── SKILL.md           # Skill documentation and usage guide
└── scripts/           # Python scripts
├── scripts/__init__.py
├── scripts/consolidate.py
└── scripts/memory_writer.py

## License

[MIT License](LICENSE)
