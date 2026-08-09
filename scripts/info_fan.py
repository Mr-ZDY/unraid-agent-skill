#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""info_fan.py — 风扇转速查询（只读，SSH + lm-sensors/hwmon）"""
import argparse
import json
import re

from info_gpu import ssh_run
import utils

REMOTE = r'''
for h in /sys/class/hwmon/hwmon*; do
  name=$(cat $h/name 2>/dev/null)
  for f in $h/fan*_input; do
    [ -f "$f" ] || continue
    rpm=$(cat $f 2>/dev/null)
    label=$(cat ${f%_input}_label 2>/dev/null || echo "fan$(basename $f | tr -cd '0-9')")
    echo "HW|$name|$label|$rpm"
  done
done
echo "===SENSORS==="
if command -v sensors >/dev/null 2>&1; then sensors 2>/dev/null | grep -iE "fan|rpm"; fi
'''


def parse(out: str) -> list[dict]:
    """合并 hwmon 与 sensors 数据，按转速匹配自定义标签。"""
    hw = []
    labels_by_rpm = {}
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("HW|"):
            _, chip, label, rpm = line.split("|")
            hw.append({"chip": chip, "label": label, "rpm": int(rpm)})
        elif "RPM" in line and ("fan" in line.lower() or "fan" in line[:20].lower()):
            m = re.match(r"^\s*([^:]+):\s+(\d+)\s+RPM", line)
            if m:
                labels_by_rpm[int(m.group(2))] = m.group(1).strip()
    fans = []
    for f in hw:
        label = labels_by_rpm.get(f["rpm"], f["label"])
        fans.append({"chip": f["chip"], "label": label, "rpm": f["rpm"]})
    return fans


def main():
    ap = argparse.ArgumentParser(description="查询风扇转速")
    ap.add_argument("--server", default="prod")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    rc, out, err = ssh_run(args.server, REMOTE)
    if rc != 0 and not out:
        print(f"✗ SSH 执行失败: {err[:200]}")
        sys.exit(1)
    fans = parse(out)

    if args.json:
        print(json.dumps(fans, ensure_ascii=False, indent=2))
        return
    if not fans:
        print("(未检测到风扇节点)")
        return
    rows = []
    for f in fans:
        status = "✓" if f["rpm"] > 0 else "停转/未接"
        rows.append([f["label"], f["chip"], f"{f['rpm']} RPM", status])
    print(utils.fmt_table(["风扇", "芯片", "转速", "状态"], rows))


if __name__ == "__main__":
    main()
