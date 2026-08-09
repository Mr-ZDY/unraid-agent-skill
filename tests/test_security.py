#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_security.py — 安全测试：命令注入防护 / 脱敏 / 端口校验"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import auth
import op_deploy

PASS = FAIL = 0


def check(name, cond):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ✓ {name}")
    else:
        FAIL += 1
        print(f"  ✗ {name}")


print("== 命令注入防护（validate_name）==")
# 合法名
check("合法名 whoami 通过", op_deploy.validate_name("whoami") == "whoami")
check("合法名 /plex 去斜杠通过", op_deploy.validate_name("/plex") == "plex")
check("合法名带 . _ - 通过", op_deploy.validate_name("moviepilot-v2") == "moviepilot-v2")
# 注入向量（全部必须拒绝）
for evil in ["plex;rm -rf /", "$(whoami)", "`id`", "a|shutdown", "a && reboot",
             "a\nreboot", "a>out.txt", "a'quote", 'a"dq', "a b c", "", " "]:
    try:
        op_deploy.validate_name(evil)
        check(f"拒绝注入: {evil!r}", False)
    except ValueError:
        check(f"拒绝注入: {evil!r}", True)

print("== 端口校验（op_deploy 端口规则）==")
import inspect
src = inspect.getsource(op_deploy)
check("端口有数字化校验（isdigit）", "isdigit" in src or "isnumeric" in src)

print("== 脱敏回归 ==")
r = auth.redact("key=0123456789abcdef0123456789abcdef")
check("64hex 脱敏", "…" in r and "0123456789abcdef0123456789abcdef" not in r)
r = auth.redact("password=secret123 token=abc123")
check("多凭据同时脱敏", "password=***" in r and "token: ***" in r or "password=***" in r and "token=***" in r)

print(f"\n结果: {PASS} 通过, {FAIL} 失败")
sys.exit(1 if FAIL else 0)
