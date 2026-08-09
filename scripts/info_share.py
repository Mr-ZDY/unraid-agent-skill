#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""info_share.py — 共享列表/用量/浏览（只读）"""
import argparse

import unraid_api
import utils

QUERY = """
{ shares { name free used size cache allocator splitLevel comment } }
"""


def main():
    ap = argparse.ArgumentParser(description="查询共享列表与用量")
    ap.add_argument("--server", default="prod")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    c = unraid_api.UnraidClient(args.server)
    c.require_api()
    data = c.gql(QUERY)

    if "errors" in data:
        # shares 根字段结构不同，打印错误辅助修正
        print(c.safe_json(data))
        return

    shares = data["data"]["shares"]
    if args.json:
        print(c.safe_json(shares))
        return

    if not shares:
        print("(无共享)")
        return
    rows = []
    for s in shares:
        size = utils.human_size(s.get("size") or 0) if s.get("size") else "无限制"
        rows.append([s.get("name", "?"),
                     utils.human_size(s.get("used") or 0),
                     size,
                     "缓存" if s.get("cache") else "阵列",
                     s.get("allocator", "-")])
    print(utils.fmt_table(["共享名", "已用", "容量", "存储", "分配方式"], rows))


if __name__ == "__main__":
    main()
