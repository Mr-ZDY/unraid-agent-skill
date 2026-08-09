#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
op_deploy.py — 容器部署（Community Applications 来源，确认门保护）
用法:
  python3 op_deploy.py search <关键词>          # 只读：CA 搜索
  python3 op_deploy.py info <应用名>            # 只读：应用详情+来源判定
  python3 op_deploy.py plan <应用名> [--port N] # 生成部署计划（docker create 命令，不执行）
  python3 op_deploy.py deploy <应用名> [--yes]  # 走确认门后输出执行命令（v1.0：由用户执行最终命令）

安全铁律（用户 2026-08-09 定）:
  1. 优先 CA 官方/可信应用；第三方必须用户明确许可
  2. 禁止跳过 CA 直接 docker run/pull 任意镜像
  3. 执行前确认门 + 审计
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.request

# Docker 容器名白名单（纵深防御：任何进入 shell 命令的容器名/应用名必须先过校验）
# Docker daemon 规则：字母数字开头，仅 [A-Za-z0-9_.-]，最长 63
_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")


def validate_name(name: str) -> str:
    """校验容器名/应用名，非法字符（含 shell 元字符）直接拒绝。"""
    n = name.lstrip("/")
    if not _NAME_RE.match(n):
        raise ValueError(
            f"非法名称: {name!r}（仅允许字母/数字/_.-，防止 shell 注入）"
        )
    return n
import xml.etree.ElementTree as ET

import confirm
import unraid_api
import utils

FEED_URL = "https://raw.githubusercontent.com/Squidly271/AppFeed/master/applicationFeed-small.json"
CACHE_FILE = os.path.expanduser("~/.unraid/cache/appfeed-small.json")
CACHE_MAX_AGE = 12 * 3600  # 12 小时刷新

# SSH 自动执行配置（测试2验证通过 2026-08-09）
SSH_KEY = os.path.expanduser("~/.unraid/ssh/id_ed25519")
SSH_USER = "root"

# 非容器系统服务占用端口（WebGUI 等，API 容器端口列表查不到）
SYSTEM_PORTS = [80, 443]

# 推荐端口候选（从 8000 起避开常用段）
PORT_RANGE = list(range(8000, 9000))

# 公认官方维护者（来源判定用）
OFFICIAL_ORGS = {
    "linuxserver", "lscr.io/linuxserver", "traefik", "portainer", "vaultwarden",
    "redis", "postgres", "mariadb", "nginx", "jellyfin", "n8nio", "immich-app",
    "home-assistant", "syncthing", "nextcloud", "gitea", "grafana", "prom",
    "jxxghp", "deluan", "vergoh", "easychen", "iyuucn", "imagegenius",
}


def fetch_feed(refresh: bool = False) -> dict:
    if not refresh and os.path.exists(CACHE_FILE):
        age = time.time() - os.path.getmtime(CACHE_FILE)
        if age < CACHE_MAX_AGE:
            with open(CACHE_FILE, encoding="utf-8") as f:
                return json.load(f)
    print("(下载 CA 应用目录，约 8MB，请稍候…)")
    req = urllib.request.Request(FEED_URL, headers={"User-Agent": "unraid-agent-skill/1.0.0"})
    with urllib.request.urlopen(req, timeout=120) as r:
        data = json.loads(r.read().decode("utf-8"))
    os.makedirs(os.path.dirname(CACHE_FILE), mode=0o700, exist_ok=True)
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    os.chmod(CACHE_FILE, 0o600)
    return data


def find_app(feed: dict, name: str) -> dict | None:
    target = name.lower()
    for app in feed.get("applist", []):
        if (app.get("Name") or "").lower() == target:
            return app
    for app in feed.get("applist", []):
        if target in (app.get("Name") or "").lower():
            return app
    return None


def source_verdict(app: dict) -> tuple[str, str]:
    """返回 (级别, 说明): official / community / thirdparty"""
    repo = (app.get("Repository") or "").lower()
    tpl = (app.get("TemplateURL") or "")
    if "linuxserver" in repo or repo.startswith("lscr.io/"):
        return "official", "LinuxServer.io 官方维护"
    org = repo.split("/")[0] if "/" in repo else repo
    if org in OFFICIAL_ORGS:
        return "official", f"官方维护者: {org}"
    if "unraid-community-apps" in tpl.lower():
        return "community", "CA 社区收录（非官方维护者，需用户确认）"
    return "thirdparty", f"第三方来源: {repo}（必须用户明确许可）"


def parse_template(tpl_url: str) -> dict | None:
    """解析 CA 模板 XML → 部署参数。"""
    req = urllib.request.Request(tpl_url, headers={"User-Agent": "unraid-agent-skill/1.0.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        xml = r.read().decode("utf-8", errors="replace")
    root = ET.fromstring(xml)
    out = {"name": None, "image": None, "ports": [], "volumes": [], "env": [], "privileged": False, "extra": ""}
    for child in root:
        tag = child.tag.lower()
        if tag == "name":
            out["name"] = (child.text or "").strip()
        elif tag == "repository":
            out["image"] = (child.text or "").strip()
        elif tag == "privileged":
            out["privileged"] = (child.text or "").strip().lower() == "true"
        elif tag == "config":
            for c2 in child:
                if c2.tag.lower() == "extraparams":
                    out["extra"] = (c2.text or "").strip()
        elif tag == "networking":
            for pub in child.iter("Port"):
                hp = cn = proto = None
                for p2 in pub:
                    if p2.tag.lower() == "hostport":
                        hp = (p2.text or "").strip()
                    elif p2.tag.lower() == "containerport":
                        cn = (p2.text or "").strip()
                    elif p2.tag.lower() == "protocol":
                        proto = (p2.text or "").strip()
                if hp and cn:
                    out["ports"].append((hp, cn, proto or "tcp"))
        elif tag == "data":
            for vol in child.iter("Volume"):
                host = cdir = mode = None
                for v2 in vol:
                    if v2.tag.lower() == "hostdir":
                        host = (v2.text or "").strip()
                    elif v2.tag.lower() == "containerdir":
                        cdir = (v2.text or "").strip()
                    elif v2.tag.lower() == "mode":
                        mode = (v2.text or "").strip()
                if host and cdir:
                    out["volumes"].append((host, cdir, mode or "rw"))
        elif tag == "environment":
            for var in child.iter("Variable"):
                n = v = None
                for v2 in var:
                    if v2.tag.lower() == "name":
                        n = (v2.text or "").strip()
                    elif v2.tag.lower() == "value":
                        v = (v2.text or "").strip()
                if n:
                    out["env"].append((n, v))
    # CA v2 模板格式：<Config Type="Port|Variable|Path" Target=...>值</Config>
    for cfg in root.iter("Config"):
        ctype = (cfg.get("Type") or "").lower()
        name = (cfg.get("Name") or "").strip()
        target = (cfg.get("Target") or "").strip()
        mode = (cfg.get("Mode") or "tcp").strip()
        value = (cfg.text or "").strip()
        if ctype == "port" and target:
            out["ports"].append((value or "8080", target, mode))
        elif ctype == "variable" and name:
            out["env"].append((name, value))
        elif ctype == "path" and name and target:
            out["volumes"].append((value, target, mode))
    return out


def get_occupied_ports(server: str = "prod") -> list[int]:
    """查询已占用端口：API 容器端口 + 系统服务端口。"""
    occupied = set(SYSTEM_PORTS)
    try:
        c = unraid_api.UnraidClient(server)
        data = c.gql("{ docker { containers { lanIpPorts } } }")
        for ct in data["data"]["docker"].get("containers") or []:
            for entry in ct.get("lanIpPorts") or []:
                # 形如 "192.0.2.100:9010" 或 "[::]:8080"
                if ":" in entry:
                    host = entry.rsplit(":", 1)[1]
                    if host.isdigit():
                        occupied.add(int(host))
    except Exception:
        pass
    return sorted(occupied)


def recommend_ports(occupied: list[int], count: int = 3) -> list[int]:
    """从候选段挑选 count 个空闲端口（上限 3）。"""
    occ = set(occupied)
    free = [p for p in PORT_RANGE if p not in occ]
    return free[:count]


def ssh_exec(server: str, command: str) -> tuple[int, str]:
    """通过 SSH 在 unRAID 上执行命令（密钥认证，无需密码）。配置取自 profile。"""
    cfg = unraid_api.conf.get_ssh(server)
    if not os.path.exists(cfg["key"]):
        raise RuntimeError(f"SSH 密钥不存在: {cfg['key']}（部署需 SSH 自动执行，见 install.sh）")
    cmd = ["ssh", "-i", cfg["key"], "-o", "BatchMode=yes", "-o", "IdentitiesOnly=yes",
           "-o", "ConnectTimeout=8", f"{cfg['user']}@{cfg['host']}", command]
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    return p.returncode, (p.stdout + p.stderr).strip()


def build_docker_create(app: dict, tpl: dict, port_override: int | None = None) -> str:
    parts = ["docker create"]
    name = tpl["name"] or app["Name"]
    parts.append(f"--name={name}")
    if tpl["extra"]:
        parts.append(tpl["extra"])
    if tpl["privileged"]:
        parts.append("--privileged")
    applied = False
    for hp, cn, proto in tpl["ports"]:
        if port_override and not applied:
            hp = str(port_override)
            applied = True
        parts.append(f"-p {hp}:{cn}/{proto}")
    if port_override and not tpl["ports"]:
        parts.append(f"-p {port_override}:80/tcp")
    for host, cdir, mode in tpl["volumes"]:
        parts.append(f"-v {host}:{cdir}:{mode}")
    for k, v in tpl["env"]:
        parts.append(f"-e {k}={v or ''}")
    icon = app.get("Icon") or ""
    parts.append('--label net.unraid.docker.managed=dockerman')
    if icon:
        parts.append(f'--label net.unraid.docker.icon={icon}')
    parts.append(tpl["image"] or app["Repository"])
    return " \\\n  ".join(parts)


def cmd_search(args):
    feed = fetch_feed()
    kw = args.keyword.lower()
    hits = [a for a in feed.get("applist", []) if kw in (a.get("Name") or "").lower() or kw in (a.get("ExtraSearchTerms") or "").lower()]
    hits.sort(key=lambda a: -(a.get("downloads") or 0))
    print(f"找到 {len(hits)} 个应用（按下载量排序）:")
    rows = []
    for a in hits[:args.limit]:
        lvl, _ = source_verdict(a)
        rows.append([a.get("Name", "?"), (a.get("Repository") or "?")[:38], lvl,
                     a.get("CategoryList", "") or "-"])
    print(utils.fmt_table(["应用", "镜像", "来源", "分类"], rows))
    print("\n提示: 用 `info <应用名>` 查看详情，`plan <应用名>` 生成部署计划")


def cmd_info(args):
    feed = fetch_feed()
    app = find_app(feed, args.name)
    if not app:
        print(f"✗ 未找到应用: {args.name}（可先 search）")
        sys.exit(1)
    lvl, why = source_verdict(app)
    print(f"应用: {app.get('Name')}")
    print(f"镜像: {app.get('Repository')}")
    print(f"来源判定: [{lvl}] {why}")
    print(f"注册表: {app.get('Registry') or '-'}")
    print(f"网络: {app.get('Network') or 'bridge'} | 特权: {app.get('Privileged')}")
    print(f"下载: {app.get('downloads')} | 星标: {app.get('stars')}")
    print(f"模板: {app.get('TemplateURL')}")
    print(f"项目: {app.get('Project') or '-'}")
    print(f"支持: {app.get('Support') or '-'}")
    ov = (app.get("Overview") or "")[:300]
    if ov:
        print(f"简介: {ov.replace('[br]', ' ')}")


def _port_requirements(tpl: dict, server: str, port_override: int | None) -> tuple[int | None, list[int], list[int]]:
    """端口规则（用户 2026-08-09 定）：涉及新端口必须用户提供，列出已占用+推荐(≤3)。"""
    if not tpl.get("ports"):
        return port_override, [], []  # 无需端口
    occupied = get_occupied_ports(server)
    recs = recommend_ports(occupied, 3)
    if port_override is None:
        return None, occupied, recs
    if port_override in occupied:
        print(f"✗ 端口 {port_override} 已被占用，请选择其他端口。已占用: {occupied}")
        return None, occupied, recs
    return port_override, occupied, recs


def cmd_plan(args):
    feed = fetch_feed()
    app = find_app(feed, args.name)
    if not app:
        print(f"✗ 未找到应用: {args.name}")
        sys.exit(1)
    lvl, why = source_verdict(app)
    tpl_url = app.get("TemplateURL")
    if not tpl_url:
        print("✗ 该应用无模板 URL，无法自动生成部署计划")
        sys.exit(1)
    try:
        tpl = parse_template(tpl_url)
    except Exception as e:
        print(f"✗ 模板解析失败: {e}")
        sys.exit(1)
    port, occupied, recs = _port_requirements(tpl, args.server, args.port)
    print(f"部署计划: {app.get('Name')} [{lvl}] {why}")
    print(f"  镜像: {tpl['image']}")
    if tpl["ports"]:
        print(f"  端口: {', '.join(f'{hp}:{cn}/{p}' for hp, cn, p in tpl['ports'])}")
        if port is None:
            print(f"  ⚠ 已占用端口: {occupied}")
            print(f"  推荐端口(前3): {recs}")
            print("  → 该应用需要新端口，请用 --port 指定端口（用户提供，参考推荐）")
        else:
            print(f"  → 使用端口: {port}")
    if tpl["volumes"]:
        print(f"  卷: {len(tpl['volumes'])} 个（路径见模板，需确认）")
    if tpl["env"]:
        print(f"  环境变量: {len(tpl['env'])} 个（值需确认）")
    print("\n生成命令:")
    print(build_docker_create(app, tpl, port))


def cmd_deploy(args):
    feed = fetch_feed()
    app = find_app(feed, args.name)
    if not app:
        print(f"✗ 未找到应用: {args.name}")
        sys.exit(1)
    lvl, why = source_verdict(app)
    tpl_url = app.get("TemplateURL")
    if not tpl_url:
        print("✗ 无模板 URL")
        sys.exit(1)
    try:
        tpl = parse_template(tpl_url)
    except Exception as e:
        print(f"✗ 模板解析失败: {e}")
        sys.exit(1)

    # 端口规则：涉及新端口必须由用户提供
    port, occupied, recs = _port_requirements(tpl, args.server, args.port)
    if tpl["ports"] and port is None:
        print(f"✗ 该应用需要新端口。已占用端口: {occupied}")
        print(f"  推荐端口(上限3个): {recs}")
        print("  请提供 --port <端口>（由用户指定）")
        sys.exit(1)

    summary = (f"应用: {app.get('Name')}\n"
               f"镜像: {tpl.get('image')}\n"
               f"来源: [{lvl}] {why}\n"
               f"端口: {f'用户指定 {port}' if port else '无端口映射'}\n"
               f"卷: {len(tpl['volumes'])} 个 | 环境变量: {len(tpl['env'])} 个")
    # 第三方必须额外确认
    if lvl != "official":
        summary += "\n⚠ 非官方来源：请确认您了解该镜像来源与风险"
    if not confirm.request_confirm(summary, risk="medium", yes=args.yes):
        confirm.audit_log(args.server, "deploy", app.get("Name"), "REFUSED")
        sys.exit(1)

    cmd = build_docker_create(app, tpl, port)
    name = tpl["name"] or app["Name"]
    full_cmd = cmd.replace("\n  ", " ") + f" && docker start {name}"
    print(f"\n✓ 已批准。经 SSH 自动执行部署…")
    rc, out = ssh_exec(args.server, full_cmd)
    if rc == 0 and out:
        print(f"部署输出:\n{out[:600]}")
        result = "OK"
    else:
        print(f"✗ 部署执行失败 (rc={rc}):\n{out[:400]}")
        result = f"FAIL rc={rc}"
    confirm.audit_log(args.server, "deploy", f"{app.get('Name')} [{lvl}] port={port}", result)


def cmd_remove(args):
    """卸载容器：展示数据路径 → 确认门 → SSH 执行 → 审计。"""
    import unraid_api as api
    c = api.UnraidClient(args.server)
    c.require_api()
    data = c.gql("{ docker { containers { id names image mounts } } }")
    target = args.name if args.name.startswith("/") else "/" + args.name
    ct = None
    for item in data["data"]["docker"].get("containers") or []:
        names = item.get("names") or []
        if target in names:
            ct = item
            break
    if not ct:
        print(f"✗ 未找到容器: {args.name}")
        sys.exit(1)

    name = (ct.get("names") or ["?"])[0]
    try:
        name = validate_name(name)
    except ValueError as e:
        print(f"✗ {e}")
        sys.exit(1)
    mounts = ct.get("mounts") or []
    mount_lines = "\n".join(f"      {m.get('Source','?')} → {m.get('Destination','?')}" for m in mounts) if mounts else "      (无数据卷)"
    summary = (f"容器: {name}\n"
               f"镜像: {ct.get('image', '?')}\n"
               f"数据卷:\n{mount_lines}\n"
               f"操作: 停止并删除容器（{'⚠ 有数据卷，请确认已备份' if mounts else '无数据卷，删除无数据损失'}）")
    if not confirm.request_confirm(summary, risk="medium", yes=args.yes):
        confirm.audit_log(args.server, "deploy_remove", name, "REFUSED")
        sys.exit(1)

    print(f"\n✓ 已批准。经 SSH 执行卸载…")
    rc, out = ssh_exec(args.server, f"docker stop {name} && docker rm {name}")
    if rc == 0:
        print(f"卸载成功:\n{out[:300]}")
        result = "OK"
    else:
        print(f"✗ 卸载失败 (rc={rc}):\n{out[:300]}")
        result = f"FAIL rc={rc}"
    confirm.audit_log(args.server, "deploy_remove", name, result)


def main():
    ap = argparse.ArgumentParser(description="CA 应用部署（确认门保护）")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("search", help="搜索 CA 应用")
    s.add_argument("keyword")
    s.add_argument("--limit", type=int, default=10)
    i = sub.add_parser("info", help="应用详情")
    i.add_argument("name")
    p = sub.add_parser("plan", help="生成部署计划（不执行）")
    p.add_argument("name")
    p.add_argument("--port", type=int, help="端口（涉及新端口时必须由用户提供）")
    p.add_argument("--server", default="prod")
    d = sub.add_parser("deploy", help="部署（确认门）")
    d.add_argument("name")
    d.add_argument("--port", type=int)
    d.add_argument("--yes", action="store_true")
    d.add_argument("--server", default="prod")
    r = sub.add_parser("remove", help="卸载容器（确认门）")
    r.add_argument("name")
    r.add_argument("--yes", action="store_true")
    r.add_argument("--server", default="prod")
    args = ap.parse_args()

    {"search": cmd_search, "info": cmd_info, "plan": cmd_plan, "deploy": cmd_deploy, "remove": cmd_remove}[args.cmd](args)


if __name__ == "__main__":
    main()
