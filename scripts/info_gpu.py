#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""info_gpu.py — GPU 状态查询（只读，SSH 实现）

正确判定方法（2026-08-09 踩坑沉淀）:
- 宿主层: nvidia-smi + lspci + /dev/dri
- 容器层: --runtime=nvidia 容器的 GPU 由 runtime 在启动时动态注入，
  静态 docker inspect 的 Devices=[] 不代表没 GPU → 必须容器内验证
"""
import argparse
import os
import re
import subprocess
import sys

import unraid_api
import utils

REMOTE_SCRIPT = r'''
echo "===GPUHOST==="
if command -v nvidia-smi >/dev/null 2>&1; then
  nvidia-smi --query-gpu=index,name,driver_version,temperature.gpu,utilization.gpu,memory.used,memory.total --format=csv,noheader,nounits
else
  echo "NO_NVIDIA_SMI"
fi
echo "===PCIDEV==="
lspci 2>/dev/null | grep -iE "vga|3d|display" | sed 's/^/PCI|/'
echo "===DRINODES==="
ls /dev/dri/ 2>/dev/null | sed 's/^/DRI|/' || echo "DRI|none"
echo "===CONTAINERS==="
for c in $(docker ps --format "{{.Names}}"); do
  rt=$(docker inspect "$c" --format "{{.HostConfig.Runtime}}" 2>/dev/null || echo "default")
  if [ "$rt" = "nvidia" ]; then
    img=$(docker inspect "$c" --format "{{.Config.Image}}" 2>/dev/null)
    gpu=$(docker exec "$c" sh -c "ls /dev/nvidia0 >/dev/null 2>&1 && echo OK || echo NO" 2>/dev/null || echo "EXEC_FAIL")
    echo "CTN|$c|$img|$gpu"
  fi
done
'''


def ssh_run(server: str, script: str, timeout: int = 60) -> tuple[int, str, str]:
    cfg = unraid_api.conf.get_ssh(server)
    if not cfg["key"] or not os.path.exists(cfg["key"]):
        print("⚠ 最小权限模式（未配置 SSH）：此模块不可用。")
        print("  当前 profile 仅使用 GraphQL API（只读查询 + 容器管理已覆盖 90% 需求）。")
        print("  如需 GPU/风扇/磁盘/CA 部署能力，见 README「部署模式」章节配置 SSH。")
        sys.exit(2)
    cmd = ["ssh", "-i", cfg["key"], "-o", "BatchMode=yes", "-o", "IdentitiesOnly=yes",
           "-o", "ConnectTimeout=8", f"{cfg['user']}@{cfg['host']}", "bash -s"]
    p = subprocess.run(cmd, input=script, capture_output=True, text=True, timeout=timeout)
    return p.returncode, p.stdout, p.stderr


def parse(remote_out: str) -> dict:
    """解析远程输出为结构化数据。"""
    result = {"host_gpu": [], "pci": [], "dri": [], "containers": []}
    section = None
    for line in remote_out.splitlines():
        line = line.strip()
        if line.startswith("==="):
            section = line.strip("=").strip()
            continue
        if not section or not line:
            continue
        if section == "GPUHOST":
            if line == "NO_NVIDIA_SMI":
                continue
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 7:
                result["host_gpu"].append({
                    "index": parts[0], "name": parts[1], "driver": parts[2],
                    "temp": parts[3], "util": parts[4],
                    "mem_used": parts[5], "mem_total": parts[6],
                })
        elif section == "PCIDEV":
            result["pci"].append(line)
        elif section == "DRINODES":
            result["dri"].append(line.removeprefix("DRI|"))
        elif section == "CONTAINERS" and line.startswith("CTN|"):
            _, name, img, gpu = line.split("|", 3)
            result["containers"].append({"name": name, "image": img[:40], "gpu_in_container": gpu})
    return result


def main():
    ap = argparse.ArgumentParser(description="查询 GPU 状态（宿主 + 容器两层验证）")
    ap.add_argument("--server", default="prod")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    rc, out, err = ssh_run(args.server, REMOTE_SCRIPT)
    if rc != 0 and not out:
        print(f"✗ SSH 执行失败: {err[:200]}")
        sys.exit(1)
    data = parse(out)

    if args.json:
        print(json_dumps(data))
        return

    # 宿主 GPU
    if data["host_gpu"]:
        print("=== 宿主 NVIDIA GPU ===")
        rows = []
        for g in data["host_gpu"]:
            mem = f"{int(g['mem_used'])/1024:.1f}/{int(g['mem_total'])/1024:.1f} GB"
            rows.append([f"GPU{g['index']}", g["name"], g["driver"],
                         f"{g['temp']}°C", f"{g['util']}%", mem])
        print(utils.fmt_table(["编号", "型号", "驱动", "温度", "利用率", "显存"], rows))
    else:
        print("=== 宿主 NVIDIA GPU ===\n(未检测到 nvidia-smi / 无 NVIDIA 独显)")

    if data["pci"]:
        print("\n=== PCI 显示设备 ===")
        for p in data["pci"]:
            print(f"  {p}")
        has_intel = any("intel" in p.lower() for p in data["pci"])
        has_nvidia = any("nvidia" in p.lower() for p in data["pci"])
        if has_intel and has_nvidia:
            print("  (Intel 核显 + NVIDIA 独显共存)")
        elif has_nvidia and not has_intel:
            print("  (仅 NVIDIA 独显 — 核显被 BIOS 屏蔽是正常现象)")

    print(f"\n=== /dev/dri 节点 ===")
    print("  " + (", ".join(data["dri"]) if data["dri"] else "无"))

    # 容器 GPU 使用
    if data["containers"]:
        print("\n=== nvidia runtime 容器 GPU 验证 ===")
        rows = []
        for c in data["containers"]:
            status = "✓ GPU 已注入" if c["gpu_in_container"] == "OK" else (
                "✗ 无 GPU" if c["gpu_in_container"] == "NO" else f"? {c['gpu_in_container']}")
            rows.append([c["name"], c["image"], status])
        print(utils.fmt_table(["容器", "镜像", "容器内 GPU"], rows))
        print("\n注: nvidia runtime 容器静态 inspect Devices=[] 属正常，以容器内验证为准")
    else:
        print("\n(无使用 nvidia runtime 的容器)")


def json_dumps(obj) -> str:
    import json
    return json.dumps(obj, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
