#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""info_logs.py — 系统日志/通知查询（只读）"""
import argparse

import unraid_api
import utils

QUERY_NOTIF = """
{ notifications { overview { unread { alert warning info } } } }
"""


def main():
    ap = argparse.ArgumentParser(description="查询通知概览")
    ap.add_argument("--server", default="prod")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    c = unraid_api.UnraidClient(args.server)
    c.require_api()
    data = c.gql(QUERY_NOTIF)

    if "errors" in data:
        print(c.safe_json(data))
        return

    if args.json:
        print(c.safe_json(data["data"]["notifications"]))
        return

    ov = data["data"]["notifications"].get("overview") or {}
    unread = ov.get("unread") or {}
    print("=== 通知概览（未读） ===")
    print(f"  警报: {unread.get('alert', 0)} | 警告: {unread.get('warning', 0)} | 信息: {unread.get('info', 0)}")


if __name__ == "__main__":
    main()
