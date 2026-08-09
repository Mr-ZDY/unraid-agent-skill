#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
op_docker.py — 容器启停/重启/更新（写操作，全部走确认门）
用法: python3 op_docker.py <start|stop|restart|update> <容器名> [--server X] [--yes]
安全: 命令白名单（仅 4 种动作）；执行前确认；执行后审计。
"""
import argparse
import sys

import confirm
import unraid_api
import utils

LIST_QUERY = """
{ docker { containers { id names state status image isUpdateAvailable } } }
"""

ACTION_MUTATION = {
    "start": "mutation {{ docker {{ start(id: \"{id}\") {{ id names state status }} }} }}",
    "stop": "mutation {{ docker {{ stop(id: \"{id}\") {{ id names state status }} }} }}",
    "restart": "mutation {{ docker {{ restart(id: \"{id}\") {{ id names state status }} }} }}",
    "update": "mutation {{ docker {{ updateContainer(id: \"{id}\") {{ id names state status isUpdateAvailable }} }} }}",
}
ACTION_ZH = {"start": "启动", "stop": "停止", "restart": "重启", "update": "更新"}
ALLOWED = set(ACTION_MUTATION)


def resolve_container(c, target: str) -> dict | None:
    """按名称（含/前缀容错）或 id 前缀查找容器。"""
    data = c.gql(LIST_QUERY)["data"]["docker"].get("containers") or []
    t = target if target.startswith("/") else "/" + target
    for ct in data:
        names = ct.get("names") or []
        if t in names or target in names:
            return ct
        if ct.get("id", "").startswith(target):
            return ct
    return None


def main():
    ap = argparse.ArgumentParser(description="容器管理（确认门保护）")
    ap.add_argument("action", choices=sorted(ALLOWED), help="start/stop/restart/update")
    ap.add_argument("container", help="容器名（可带/前缀）或 id 前缀")
    ap.add_argument("--server", default="prod")
    ap.add_argument("--yes", action="store_true", help="已获用户批准（Agent 在用户同意后传入）")
    args = ap.parse_args()

    c = unraid_api.UnraidClient(args.server)
    c.require_api()
    ct = resolve_container(c, args.container)
    if not ct:
        print(f"✗ 未找到容器: {args.container}")
        sys.exit(1)

    name = (ct.get("names") or ["?"])[0]
    action_zh = ACTION_ZH[args.action]
    extra = ""
    if args.action == "update":
        extra = f"\n  更新可用: {'是' if ct.get('isUpdateAvailable') else '否'}"

    summary = (f"容器: {name}\n"
               f"镜像: {ct.get('image', '?')}\n"
               f"当前状态: {ct.get('state')} ({ct.get('status', '')})\n"
               f"操作: {action_zh}{extra}")
    if not confirm.request_confirm(summary, risk="medium", yes=args.yes):
        confirm.audit_log(args.server, f"docker_{args.action}", name, "REFUSED")
        sys.exit(1)

    mutation = ACTION_MUTATION[args.action].format(id=ct["id"])
    try:
        res = c.gql(mutation)
    except unraid_api.UnraidAPIError as e:
        print(f"✗ 执行失败: {e}")
        confirm.audit_log(args.server, f"docker_{args.action}", name, f"FAIL: {e.code}")
        sys.exit(1)

    if "errors" in res:
        print(f"✗ API 错误: {res['errors'][0]['message']}")
        confirm.audit_log(args.server, f"docker_{args.action}", name, "FAIL: api_error")
        sys.exit(1)

    ct2 = res["data"]["docker"][
        "start" if args.action == "start" else
        "stop" if args.action == "stop" else
        "restart" if args.action == "restart" else "updateContainer"]
    print(f"✓ {action_zh}成功: {name} → 状态 {ct2.get('state')} ({ct2.get('status', '')})")
    confirm.audit_log(args.server, f"docker_{args.action}", name, f"OK -> {ct2.get('state')}")


if __name__ == "__main__":
    main()
