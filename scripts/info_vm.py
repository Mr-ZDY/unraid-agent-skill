#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""info_vm.py — 虚拟机列表查询（只读）"""
import argparse

import unraid_api
import utils

QUERY = """
{ vms { domains { name state } } }
"""

_STATE_ZH = {"RUNNING": "运行中", "SHUTOFF": "已关机", "PAUSED": "已暂停", "CRASHED": "崩溃",
             "NOSTATE": "无状态", "IDLE": "空闲", "SHUTDOWN": "关机中", "PMSUSPENDED": "挂起"}


def main():
    ap = argparse.ArgumentParser(description="查询虚拟机列表")
    ap.add_argument("--server", default="prod")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    c = unraid_api.UnraidClient(args.server)
    c.require_api()
    try:
        data = c.gql(QUERY)
    except unraid_api.UnraidAPIError as e:
        if "VMs are not available" in str(e):
            print("VM 服务未启用（设置 → 虚拟机 中开启后才可用）")
            return
        raise

    if "errors" in data:
        print(c.safe_json(data))
        return

    domains = data["data"]["vms"].get("domains") or []
    if args.json:
        print(c.safe_json(domains))
        return

    if not domains:
        print("(无虚拟机)")
        return
    rows = []
    for d in domains:
        rows.append([d.get("name", "?"), _STATE_ZH.get(d.get("state"), d.get("state"))])
    print(utils.fmt_table(["虚拟机", "状态"], rows))


if __name__ == "__main__":
    main()
