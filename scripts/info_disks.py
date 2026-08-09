#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""info_disks.py — 磁盘用量 + SMART 通电时间（只读，SSH）"""
import argparse
import json
import sys

from info_gpu import ssh_run
import utils

REMOTE = r'''
eval "$(awk -F'"' '/^\[/{n=$0;gsub(/[\[\]"]/,"",n)} /^device=/{print "SLOT_"n"=/dev/"$2}' /var/local/emhttp/disks.ini 2>/dev/null)"
for s in disk1 disk2 disk3 disk4 disk5 disk6 disk7 disk8 disk9 cache; do
  dev=$(eval echo \${SLOT_$s:-}); [ -z "$dev" ] && continue
  mp=/mnt/$s
  read size used <<< $(df -k "$mp" 2>/dev/null | awk 'NR==2{print $2,$3}')
  if echo "$dev" | grep -q nvme; then
    poh=$(smartctl -A "$dev" 2>/dev/null | grep -i "Power On Hours" | awk '{print $NF}' | tr -d ',')
    model=$(smartctl -i "$dev" 2>/dev/null | grep -i "Model Number" | awk -F: '{print $2}' | xargs)
  else
    poh=$(smartctl -A "$dev" 2>/dev/null | grep -i "Power_On_Hours" | awk '{print $NF}')
    model=$(lsblk -dno MODEL "$dev" 2>/dev/null)
  fi
  echo "D|$s|$dev|${size:-0}|${used:-0}|${poh:-0}|$model"
done
managed=""
for s in disk1 disk2 disk3 disk4 disk5 disk6 disk7 disk8 disk9 cache flash; do
  dev=$(eval echo \${SLOT_$s:-})
  [ -n "$dev" ] && managed="$managed ${dev#/dev/}"
done
for d in $(lsblk -dno NAME 2>/dev/null | grep -E "^sd"); do
  case " $managed " in *" $d "*) continue;; esac
  poh=$(smartctl -A /dev/$d 2>/dev/null | grep -i "Power_On_Hours" | awk '{print $NF}')
  model=$(lsblk -dno MODEL /dev/$d 2>/dev/null)
  echo "U|$d|/dev/$d|0|0|${poh:-0}|$model"
done
'''


def parse(out: str) -> dict:
    disks, unassigned = [], []
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split("|")
        if len(parts) != 7:
            continue
        kind, slot, dev, size, used, poh, model = parts
        if kind == "D" and int(size) == 0:
            continue  # 空槽位
        item = {"slot": slot, "device": dev, "size_kb": int(size), "used_kb": int(used),
                "poh": int(poh), "model": model.strip()}
        (disks if kind == "D" else unassigned).append(item)
    return {"disks": disks, "unassigned": unassigned}


def main():
    ap = argparse.ArgumentParser(description="查询磁盘用量与通电时间")
    ap.add_argument("--server", default="prod")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    rc, out, err = ssh_run(args.server, REMOTE)
    if rc != 0 and not out:
        print(f"✗ SSH 执行失败: {err[:200]}")
        sys.exit(1)
    data = parse(out)

    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return

    rows = []
    for d in data["disks"]:
        size = utils.human_size(d["size_kb"] * 1024)
        used = utils.human_size(d["used_kb"] * 1024)
        pct = f"{d['used_kb'] * 100 // max(d['size_kb'], 1)}%"
        years = d["poh"] / 8760 if d["poh"] else 0
        rows.append([d["slot"], (d["model"] or "?")[:24], size, f"{used} ({pct})",
                     f"{d['poh']}h ({years:.1f}年)" if d["poh"] else "-"])
    print(utils.fmt_table(["槽位", "型号", "容量", "已用", "通电时间"], rows))
    if data["unassigned"]:
        print("\n未挂阵列:")
        for d in data["unassigned"]:
            years = d["poh"] / 8760 if d["poh"] else 0
            print(f"  {d['device']} {(d['model'] or '?')[:28]} 通电 {d['poh']}h ({years:.1f}年)" if d["poh"] else f"  {d['device']} {d['model']}")


if __name__ == "__main__":
    main()
