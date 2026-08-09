#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""info_system.py — 系统信息查询（只读）"""
import argparse
import sys

import unraid_api
import utils

QUERY = """
{ info {
  os { hostname distro release codename kernel arch uptime uefi }
  versions { core { unraid api kernel } }
  cpu { brand cores threads speedmax }
  system { manufacturer model virtual }
} }
"""


def main():
    ap = argparse.ArgumentParser(description="查询 unRAID 系统信息")
    ap.add_argument("--server", default="prod")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    args = ap.parse_args()

    c = unraid_api.UnraidClient(args.server)
    c.require_api()
    data = c.gql(QUERY)["data"]["info"]
    os_ = data["os"]
    core = data["versions"]["core"]
    cpu = data["cpu"]
    sysinfo = data["system"]

    if args.json:
        print(c.safe_json(data))
        return

    rows = [
        ("主机名", os_["hostname"]),
        ("发行版", f"{os_['distro']} {os_['release']} ({os_['codename']})"),
        ("unRAID 版本", core["unraid"]),
        ("内核", core["kernel"]),
        ("API 版本", core["api"]),
        ("CPU", f"{cpu.get('brand') or '?'} ({cpu.get('cores')}核/{cpu.get('threads')}线程)"),
        ("主板", f"{sysinfo.get('manufacturer') or '?'} {sysinfo.get('model') or '?'}"),
        ("虚拟化", "是" if sysinfo.get("virtual") else "否"),
        ("UEFI 启动", "是" if os_.get("uefi") else "否"),
        ("运行时间", f"自 {os_.get('uptime')}"),
    ]
    print(utils.fmt_table(["项目", "值"], rows))


if __name__ == "__main__":
    main()
