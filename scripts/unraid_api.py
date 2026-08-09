#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
unRAID Agent Skill — GraphQL 客户端封装 (unraid_api.py)
- 统一认证 (x-api-key)、超时、重试（仅幂等查询）、错误映射
- 所有返回内容经 redact() 脱敏后再输出
- 版本检查：<7.2 提示 API 不可用
"""
import json
import re
import sys
import urllib.error
import urllib.request

import auth
import conf

API_MIN_VERSION = "7.2.0"

# 已测试版本表（版本 → 测试状态）
TESTED_VERSIONS = [
    ("7.3", "实测通过 (7.3.2 / API 4.37.0)"),
    ("7.2", "API 同代，建议先 --compat 自检"),
    ("<7.2", "不兼容：无内置 GraphQL API，skill 拒绝运行"),
]

# capability 自检：关键 schema 字段抽查（版本漂移时给出明确提示）
COMPAT_PROBES = {
    "info_versions": ('{ __type(name: "Info"){fields{name}} }', ["versions", "os"]),
    "array": ('{ __type(name: "UnraidArray"){fields{name}} }', ["state", "disks", "capacity"]),
    "docker": ('{ __type(name: "DockerContainer"){fields{name}} }', ["id", "names", "state"]),
    "shares": ('{ __type(name: "Share"){fields{name}} }', ["name", "used", "free"]),
    "vms": ('{ __type(name: "Vms"){fields{name}} }', ["domains"]),
    "notifications": ('{ __type(name: "Notification"){fields{name}} }', ["title", "importance"]),
}


class UnraidAPIError(Exception):
    """统一 API 错误。"""

    def __init__(self, message, code=None, raw=None):
        super().__init__(message)
        self.code = code
        self.raw = raw


class UnraidClient:
    def __init__(self, server: str = "prod"):
        self.server = server
        p = conf.get_profile(server)
        self.url = p["url"]
        self.key = auth.load_key(server, p.get("key_file"))
        self.timeout = p.get("timeout", 15)
        self._version_cache = None

    # ---- 核心查询 ----
    def gql(self, query: str, variables: dict | None = None, retries: int = 1) -> dict:
        """执行 GraphQL 查询。retries 仅建议用于幂等只读查询。"""
        payload = json.dumps({"query": query, "variables": variables or {}}).encode()
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.key,
            "User-Agent": "unraid-agent-skill/1.0.0",
        }
        last_err = None
        for attempt in range(retries + 1):
            try:
                req = urllib.request.Request(self.url, data=payload, headers=headers, method="POST")
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                if "errors" in data:
                    msgs = [e.get("message", "?") for e in data["errors"]]
                    raise UnraidAPIError("GraphQL: " + "; ".join(msgs), code="GRAPHQL", raw=data)
                return data
            except urllib.error.HTTPError as e:
                body = e.read().decode("utf-8", errors="replace")[:300]
                if e.code == 401:
                    raise UnraidAPIError("认证失败（401）：密钥无效或已撤销", code="AUTH", raw=body)
                if e.code == 403:
                    raise UnraidAPIError("权限不足（403）：密钥角色不允许该操作", code="FORBIDDEN", raw=body)
                if e.code == 429:
                    raise UnraidAPIError("请求过于频繁（429）", code="RATE_LIMIT", raw=body)
                last_err = UnraidAPIError(f"HTTP {e.code}: {body}", code=f"HTTP_{e.code}", raw=body)
            except urllib.error.URLError as e:
                last_err = UnraidAPIError(f"连接失败: {e.reason}", code="NETWORK")
            except json.JSONDecodeError as e:
                last_err = UnraidAPIError(f"响应解析失败: {e}", code="BAD_RESPONSE")
        raise last_err

    # ---- 版本检查 ----
    def get_version(self) -> dict:
        if self._version_cache:
            return self._version_cache
        data = self.gql("{ info { versions { core { unraid api kernel } } os { hostname } } }")
        core = data["data"]["info"]["versions"]["core"]
        self._version_cache = core
        return core

    def require_api(self) -> dict:
        """版本门槛检查：<7.2 拒绝。返回 core 版本信息。"""
        core = self.get_version()
        try:
            major, minor = (int(x) for x in core["unraid"].split(".")[:2])
        except (ValueError, KeyError):
            raise UnraidAPIError("无法解析 unRAID 版本号", code="VERSION")
        if (major, minor) < (7, 2):
            raise UnraidAPIError(
                f"当前 unRAID {core['unraid']} 低于 7.2，内置 GraphQL API 不可用，请升级或改用 WebGUI 人工操作",
                code="VERSION_TOO_OLD",
            )
        return core

    def check_compat(self) -> dict:
        """capability 自检：版本状态 + 关键 schema 字段存在性（版本漂移防护）。"""
        core = self.get_version()
        unraid = core["unraid"]
        api = core["api"]
        report = {"unraid": unraid, "api": api, "status": "OK", "warnings": [], "checks": {}}
        major, minor = (int(x) for x in unraid.split(".")[:2])

        # 版本状态
        if (major, minor) < (7, 2):
            report["status"] = "REFUSED"
            report["warnings"].append("unRAID <7.2：无内置 API，skill 不可用")
        elif major == 7 and minor == 3:
            report["version_status"] = "✅ 已实测版本"
        elif major == 7 and minor == 2:
            report["version_status"] = "⚠️ 7.2 同代 API，未实测（建议先跑通 --compat 全部通过再使用）"
            report["warnings"].append("7.2.x 未实测")
        else:
            report["version_status"] = f"⚠️ 新版本 {unraid} 未测试，schema 可能漂移"
            report["warnings"].append("新版本未测试，注意 API 变更")

        # API 组件版本（独立升级可能带来 schema 变化）
        m = re.match(r"^(\d+)\.(\d+)", api or "")
        if m:
            api_major, api_minor = int(m.group(1)), int(m.group(2))
            if api_major > 4 or (api_major == 4 and api_minor > 37):
                report["warnings"].append(f"API 组件 {api} 高于已测试的 4.37，schema 可能有变")

        # schema 字段抽查
        for name, (probe, required) in COMPAT_PROBES.items():
            try:
                r = self.gql(probe)
                fields = [f["name"] for f in r["data"]["__type"]["fields"]]
                missing = [f for f in required if f not in fields]
                if missing:
                    report["checks"][name] = f"✗ 缺字段: {missing}"
                    report["warnings"].append(f"{name} schema 变化: 缺 {missing}")
                else:
                    report["checks"][name] = "✓"
            except Exception as e:
                report["checks"][name] = f"✗ 查询失败: {e}"
                report["warnings"].append(f"{name} 自检失败: {e}")
        if report["warnings"]:
            report["status"] = "WARN"
        return report

    # ---- 安全输出 ----
    def safe_json(self, obj) -> str:
        return auth.redact(json.dumps(obj, ensure_ascii=False, indent=2))


def main():
    import argparse
    ap = argparse.ArgumentParser(description="unRAID API 连通性/版本/capability 自检")
    ap.add_argument("--server", default="prod")
    ap.add_argument("--compat", action="store_true", help="capability 自检（版本+关键字段）")
    args = ap.parse_args()
    try:
        c = UnraidClient(args.server)
        if args.compat:
            r = c.check_compat()
            print(f"unRAID {r['unraid']} | API {r['api']} | 状态: {r['status']}")
            print(f"版本状态: {r.get('version_status', '-')}")
            print("schema 字段抽查:")
            for name, st in r["checks"].items():
                print(f"  {name}: {st}")
            for w in r["warnings"]:
                print(f"  ⚠ {w}")
            sys.exit(1 if r["status"] == "REFUSED" else 0)
        core = c.require_api()
        print("API 连通性: OK")
        print("unRAID 版本:", core["unraid"], "| 内核:", core["kernel"], "| API:", core["api"])
    except UnraidAPIError as e:
        print(f"✗ {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
