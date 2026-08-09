#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
unRAID Agent Skill — 服务器配置管理 (conf.py)
管理多 unRAID 实例的 profile：地址、密钥路径、SSH 配置。
配置文件: ~/.unraid/profiles.json (权限 600)
本文件无硬编码服务器信息：DEFAULT_PROFILES 为空，由 install.sh 引导生成 profiles.json。
"""
import json
import os
import re
import sys

CONF_DIR = os.path.expanduser("~/.unraid")
CONF_FILE = os.path.join(CONF_DIR, "profiles.json")
KEYS_DIR = os.path.join(CONF_DIR, "keys")
SSH_DIR = os.path.join(CONF_DIR, "ssh")

DEFAULT_PROFILES = {}  # 由 install.sh 或 conf.py add 生成，禁止硬编码具体服务器

# profile 字段说明：
#   url        GraphQL 端点，如 http://192.0.2.100/graphql
#   key_file   API 密钥文件路径（默认 <KEYS_DIR>/<host>.key）
#   ssh_key    SSH 私钥路径（默认 <SSH_DIR>/id_ed25519）
#   ssh_user   SSH 用户（默认 root）
#   verify_ssl 自签证书时 False
#   timeout    请求超时（秒）


def _ensure_dirs():
    os.makedirs(CONF_DIR, mode=0o700, exist_ok=True)
    os.makedirs(KEYS_DIR, mode=0o700, exist_ok=True)
    os.makedirs(SSH_DIR, mode=0o700, exist_ok=True)


def load_profiles() -> dict:
    """读取全部 profile；不存在则返回空。"""
    if not os.path.exists(CONF_FILE):
        return {}
    try:
        with open(CONF_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def save_profiles(profiles: dict) -> None:
    _ensure_dirs()
    with open(CONF_FILE, "w", encoding="utf-8") as f:
        json.dump(profiles, f, ensure_ascii=False, indent=2)
    os.chmod(CONF_FILE, 0o600)


def get_profile(name: str = "prod") -> dict:
    profiles = load_profiles()
    if name not in profiles:
        raise KeyError(
            f"profile '{name}' 不存在，可用: {list(profiles) or '(空)'}。"
            f"请先运行 install.sh 或 conf.py add 配置服务器"
        )
    return profiles[name]


def list_profiles() -> dict:
    return load_profiles()


def add_profile(name: str, url: str, key_file: str | None = None,
                ssh_key: str | None = None, ssh_user: str = "root",
                verify_ssl: bool = False) -> None:
    host = re.sub(r"^https?://([^/:]+).*$", r"\1", url)
    profiles = load_profiles()
    profiles[name] = {
        "url": url,
        "key_file": key_file or os.path.join(KEYS_DIR, f"{host}.key"),
        "ssh_key": ssh_key or os.path.join(SSH_DIR, "id_ed25519"),
        "ssh_user": ssh_user,
        "verify_ssl": verify_ssl,
        "timeout": 15,
    }
    save_profiles(profiles)


def get_ssh(name: str = "prod") -> dict:
    """返回 SSH 连接配置 {host, user, key}，从 profile 解析。"""
    p = get_profile(name)
    url = p["url"]
    host = re.sub(r"^https?://([^/:]+).*$", r"\1", url)
    return {
        "host": host,
        "user": p.get("ssh_user", "root"),
        "key": p.get("ssh_key", os.path.join(SSH_DIR, "id_ed25519")),
    }


def main():
    import argparse
    ap = argparse.ArgumentParser(description="unRAID profile 管理")
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("list", help="列出所有 profile")
    add = sub.add_parser("add", help="添加 profile")
    add.add_argument("name")
    add.add_argument("url")
    add.add_argument("--key", dest="key_file", help="API 密钥文件（默认 ~/.unraid/keys/<host>.key）")
    add.add_argument("--ssh-key", dest="ssh_key", help="SSH 私钥（默认 ~/.unraid/ssh/id_ed25519）")
    add.add_argument("--ssh-user", default="root")
    add.add_argument("--no-verify-ssl", action="store_true")
    args = ap.parse_args()

    if args.cmd == "list":
        for name, p in list_profiles().items():
            print(f"{name}: {p['url']} (key: {p['key_file']})")
    elif args.cmd == "add":
        add_profile(args.name, args.url, args.key_file, args.ssh_key, args.ssh_user, not args.no_verify_ssl)
        print(f"已添加 profile: {args.name}")
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
