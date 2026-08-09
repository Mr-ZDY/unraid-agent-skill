#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
unRAID Agent Skill — 通用工具 (utils.py)
格式化输出：表格 / JSON / 人类可读容量与时间
"""
import json


def human_size(num: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB", "PB"):
        if abs(num) < 1024.0 or unit == "PB":
            return f"{num:.1f} {unit}" if unit != "B" else f"{int(num)} B"
        num /= 1024.0


def fmt_table(headers: list, rows: list) -> str:
    """渲染简单表格（终端友好）。"""
    if not rows:
        return "(无数据)"
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(str(cell)))
    lines = ["  ".join(h.ljust(widths[i]) for i, h in enumerate(headers))]
    lines.append("  ".join("-" * w for w in widths))
    for row in rows:
        lines.append("  ".join(str(c).ljust(widths[i]) for i, c in enumerate(row)))
    return "\n".join(lines)


def out_json(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2)


def pick(data: dict, keys: list) -> dict:
    """从嵌套 dict 中挑字段（容忍缺失）。"""
    return {k: data.get(k) for k in keys}
