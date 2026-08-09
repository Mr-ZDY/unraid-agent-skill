#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""脱敏与工具测试（不访问网络）"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import auth
import utils

PASS = 0
FAIL = 0


def check(name, cond):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ✓ {name}")
    else:
        FAIL += 1
        print(f"  ✗ {name}")


# ---- auth.redact ----
hexkey = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
r = auth.redact(f"key={hexkey}")
check("64位hex密钥脱敏", "aaaa…aaaa" in r and hexkey not in r)

r = auth.redact("password=abc123")
check("password赋值脱敏", "password=***" in r and "abc123" not in r)

r = auth.redact("token: xyz789")
check("token赋值脱敏", "token: ***" in r and "xyz789" not in r)

r = auth.redact("authorization: Bearer abcdefgh123")
check("Authorization头脱敏", "authorization: ***" in r)

r = auth.redact("路径 keys/192.0.2.100.key 结束")
check("密钥文件名脱敏", "keys/***.key" in r)

r = auth.redact("hk-abcdef0123456789abcdef0123456789")
check("hk前缀密钥脱敏", "hk-abcd…" in r and "0123456789abcdef0123456789" not in r)

r = auth.redact("普通文本 unraid 7.3.2 正常内容")
check("普通文本不误伤", r == "普通文本 unraid 7.3.2 正常内容")

# ---- utils ----
check("human_size", utils.human_size(1073741824) == "1.0 GB")
check("fmt_table", "名称" in utils.fmt_table(["名称", "值"], [["a", "1"]]))
check("out_json", '"a": 1' in utils.out_json({"a": 1}))

print(f"\n结果: {PASS} 通过, {FAIL} 失败")
sys.exit(1 if FAIL else 0)
