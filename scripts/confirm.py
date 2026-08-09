#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
unRAID Agent Skill — 确认门框架 + 操作审计 (confirm.py)
- request_confirm(): 操作摘要 → 等待确认 → 通过/拒绝（超时默认拒绝）
- audit_log(): 审计记录（不含敏感值）
"""
import datetime
import os
import sys
import time

AUDIT_FILE = os.path.expanduser("~/.unraid/audit.log")

RISK_ZH = {"low": "低（只读）", "medium": "中（常规管理）", "high": "高（危险操作）"}


def request_confirm(summary: str, risk: str = "medium", timeout: int = 60, yes: bool = False) -> bool:
    """确认门。yes=True 表示已获用户批准（由 Agent 在用户明确同意后传入）。
    否则交互式等待输入 'yes' 确认；超时/其他输入 = 拒绝。"""
    print(f"\n┌─ 操作确认 ─────────────────────────────")
    print(f"│ 风险等级: {RISK_ZH.get(risk, risk)}")
    for line in summary.splitlines():
        print(f"│ {line}")
    print(f"└─────────────────────────────────────────")
    if yes:
        print("✓ 已获批准（--yes）")
        return True
    if not sys.stdin.isatty():
        print("✗ 非交互环境且未提供 --yes，拒绝执行")
        return False
    try:
        answer = input(f"输入 yes 确认执行（{timeout}s 超时自动拒绝）: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print("\n✗ 已取消")
        return False
    if answer == "yes":
        return True
    print("✗ 未确认，操作已取消")
    return False


def audit_log(server: str, operation: str, detail: str, result: str) -> None:
    """追加审计记录。detail 中不得包含密钥/密码等敏感值。"""
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] server={server} op={operation} detail={detail} result={result}"
    try:
        with open(AUDIT_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
        os.chmod(AUDIT_FILE, 0o600)
    except OSError as e:
        print(f"⚠ 审计写入失败: {e}")
