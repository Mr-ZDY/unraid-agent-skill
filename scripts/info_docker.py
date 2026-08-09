#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""info_docker.py — Docker 容器/镜像/日志查询（只读）"""
import argparse

import unraid_api
import utils

QUERY = """
{ docker {
  containers { names image state status lanIpPorts autoStart isUpdateAvailable webUiUrl registryUrl }
} }
"""

_STATE_ZH = {"RUNNING": "运行中", "PAUSED": "已暂停", "EXITED": "已退出"}


def main():
    ap = argparse.ArgumentParser(description="查询 Docker 容器")
    ap.add_argument("--server", default="prod")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    c = unraid_api.UnraidClient(args.server)
    c.require_api()
    data = c.gql(QUERY)

    if "errors" in data:
        print(c.safe_json(data))
        return

    containers = data["data"]["docker"].get("containers") or []
    if args.json:
        print(c.safe_json(containers))
        return

    if not containers:
        print("(无容器)")
        return
    rows = []
    for ct in containers:
        name = (ct.get("names") or ["?"])[0] if isinstance(ct.get("names"), list) else ct.get("names", "?")
        state = _STATE_ZH.get(ct.get("state"), ct.get("state"))
        update = "⚠有更新" if ct.get("isUpdateAvailable") else ""
        rows.append([name, ct.get("image", "?")[:40], state,
                     ct.get("lanIpPorts") or "-", update])
    print(utils.fmt_table(["容器", "镜像", "状态", "IP:端口", "更新"], rows))


if __name__ == "__main__":
    main()
