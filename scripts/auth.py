#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
unRAID Agent Skill — 认证与脱敏 (auth.py)
- 从 ~/.unraid/keys/<name>.key 读取 API 密钥（权限必须 600）
- redact()：输出脱敏（API 密钥 / 密码 / token 等敏感信息）
"""
import os
import re

# 64 位十六进制密钥（unRAID API key 形态）
_HEX64 = re.compile(r"\b[0-9a-fA-F]{32,}\b")
# hk- 前缀密钥（Hermes 等）
_HKPREFIX = re.compile(r"\b(hk|sk|pk)-[A-Za-z0-9_\-]{8,}\b")
# password/passwd/token/secret 赋值（含中文标点边界，保留原分隔符与空格）
_PASSASSIGN = re.compile(r"(?i)(password|passwd|token|secret|api[_-]?key)\s*([=:])(\s*)['\"]?[^\s'\"&,;，。：]+")
# Authorization 头
_AUTHHEADER = re.compile(r"(?i)(authorization:\s*)(bearer\s+)?[A-Za-z0-9._\-]+")
# 独立 Bearer token
_BEARER = re.compile(r"(?i)\b(bearer\s+)[A-Za-z0-9._\-]{8,}")
# 路径中的密钥文件名
_KEYFILE = re.compile(r"(keys?/)[^/\s]+\.key\b")


def load_key(server: str = "prod", key_file: str | None = None) -> str:
    """读取指定服务器密钥。key_file 为空时从 profile 配置取。"""
    if key_file is None:
        import conf
        profile = conf.get_profile(server)
        key_file = profile["key_file"]
    if not os.path.exists(key_file):
        raise FileNotFoundError(f"密钥文件不存在: {key_file}（请先创建 API 密钥并放入 ~/.unraid/keys/）")
    mode = os.stat(key_file).st_mode & 0o777
    if mode != 0o600:
        # 权限过宽则收紧，并提示
        os.chmod(key_file, 0o600)
    with open(key_file, encoding="utf-8") as f:
        key = f.read().strip()
    if len(key) < 16:
        raise ValueError("密钥内容异常（过短），请检查密钥文件")
    return key


def redact(text: str) -> str:
    """对文本中的敏感信息打码。"""
    if not text:
        return text
    text = _HEX64.sub(lambda m: m.group(0)[:4] + "…" + m.group(0)[-4:], text)
    text = _HKPREFIX.sub(lambda m: m.group(0)[:6] + "…", text)
    text = _PASSASSIGN.sub(lambda m: m.group(1) + m.group(2) + m.group(3) + "***", text)
    text = _AUTHHEADER.sub(lambda m: m.group(1) + "***", text)
    text = _BEARER.sub(lambda m: m.group(1) + "***", text)
    text = _KEYFILE.sub(r"\1***.key", text)
    return text


def main():
    import argparse
    ap = argparse.ArgumentParser(description="密钥/脱敏工具")
    ap.add_argument("--server", default="prod", help="profile 名")
    ap.add_argument("--show-masked", action="store_true", help="显示脱敏后的密钥")
    args = ap.parse_args()
    key = load_key(args.server)
    print(f"密钥已加载: {len(key)} 字符 (权限校验通过)")
    if args.show_masked:
        print("脱敏显示:", redact(key))


if __name__ == "__main__":
    main()
