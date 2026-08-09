#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""info_array.py — 阵列/磁盘/池状态查询（只读）"""
import argparse

import unraid_api
import utils

QUERY = """
{ array {
  state
  capacity { kilobytes { free used total } }
  parityCheckStatus { running status progress errors speed }
  boot { name size status }
  parities { idx name device size status temp fsType }
  disks { idx name device size status temp fsType fsFree fsUsed rotational isSpinning }
} }
"""

_STATUS_ZH = {
    "DISK_OK": "正常", "DISK_NP": "未校验", "DISK_DSBL": "禁用", "DISK_NEW": "新盘",
    "DISK_INVALID": "无效", "DISK_WRONG": "错误", "DISK_NP_MISSING": "缺失",
    "DISK_NP_DSBL": "禁用(无校验)", "DISK_DSBL_NEW": "禁用(新)", "DISK_NP_DISABLED": "禁用",
}
_STATE_ZH = {"STARTED": "已启动", "STOPPED": "已停止", "NEW_ARRAY": "新阵列", "PARITY_NOT_BIGGEST": "校验盘非最大",
             "TOO_MANY_MISSING_DISKS": "缺失盘过多", "NEW_DISK_TOO_SMALL": "新盘太小", "NO_DATA_DISKS": "无数据盘"}


def main():
    ap = argparse.ArgumentParser(description="查询阵列/磁盘状态")
    ap.add_argument("--server", default="prod")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    c = unraid_api.UnraidClient(args.server)
    c.require_api()
    data = c.gql(QUERY)["data"]["array"]

    if args.json:
        print(c.safe_json(data))
        return

    kb = data["capacity"]["kilobytes"]
    total, used, free = int(kb["total"]), int(kb["used"]), int(kb["free"])
    print(f"阵列状态: {_STATE_ZH.get(data['state'], data['state'])}")
    print(f"容量: {utils.human_size(used*1024)} / {utils.human_size(total*1024)} "
          f"(剩余 {utils.human_size(free*1024)}, 使用率 {used*100//max(total,1)}%)")
    pc = data["parityCheckStatus"]
    if pc and pc.get("running"):
        print(f"校验检查: 运行中 {pc.get('progress',0)}% | 错误 {pc.get('errors',0)} | 速度 {pc.get('speed','?')}")
    elif pc and pc.get("status"):
        print(f"校验检查: {pc.get('status')}")

    boot = data.get("boot")
    if boot:
        print(f"启动盘: {boot.get('name','?')} ({utils.human_size((boot.get('size') or 0)*1024)})")

    disks = (data.get("parities") or []) + (data.get("disks") or [])
    if not disks:
        print("\n(无阵列磁盘)")
        return
    rows = []
    for d in disks:
        size = utils.human_size((d.get("size") or 0) * 1024)
        status = _STATUS_ZH.get(d.get("status"), d.get("status"))
        temp = f"{d['temp']}°C" if d.get("temp") else "-"
        fs = d.get("fsType") or "-"
        used_pct = ""
        if d.get("fsUsed") and d.get("fsSize"):
            used_pct = f" ({d['fsUsed']*100//d['fsSize']}%)"
        rows.append([f"disk{d.get('idx','?')}", d.get("name", "?"), size, fs + used_pct, temp, status])
    print(utils.fmt_table(["槽位", "设备", "容量", "文件系统", "温度", "状态"], rows))


if __name__ == "__main__":
    main()
