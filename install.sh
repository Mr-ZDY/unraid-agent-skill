#!/bin/bash
# ============================================================
# unRAID Agent Skill — 安装引导脚本
# 要求: unRAID 7.2+（内置 GraphQL API）/ 本机 Python 3.10+ / 可访问 unRAID
# 用法: bash install.sh
# ============================================================
set -e

CONF_DIR="$HOME/.unraid"
KEYS_DIR="$CONF_DIR/keys"
SSH_DIR="$CONF_DIR/ssh"

echo "=============================================="
echo " unRAID Agent Skill 安装引导"
echo " 要求: unRAID 7.2+ / Python 3.10+（纯标准库）"
echo "=============================================="

# ---------- 1. 服务器地址 ----------
read -p "unRAID 服务器 GraphQL 地址 [如 http://192.0.2.100/graphql]: " URL
if [ -z "$URL" ]; then
  echo "✗ 地址不能为空"; exit 1
fi
HOST=$(echo "$URL" | sed -E 's|^https?://([^/:]+).*$|\1|')

read -p "profile 名称 [prod]: " NAME
NAME=${NAME:-prod}

mkdir -p "$KEYS_DIR" "$SSH_DIR"
chmod 700 "$CONF_DIR" "$KEYS_DIR" "$SSH_DIR"

# ---------- 2. API 密钥 ----------
echo ""
echo "=== 第 1 步: 创建 API 密钥 ==="
echo "在 unRAID WebGUI: 设置 → 管理访问 → API 密钥 → 创建"
echo "  角色: ADMIN（容器管理必需）或 VIEWER（仅只读查询）"
read -p "把密钥粘贴到这里: " API_KEY
if [ -z "$API_KEY" ]; then
  echo "✗ 密钥不能为空"; exit 1
fi
printf '%s' "$API_KEY" > "$KEYS_DIR/$HOST.key"
chmod 600 "$KEYS_DIR/$HOST.key"
echo "✓ 密钥已保存: $KEYS_DIR/$HOST.key (600)"

# ---------- 3. SSH 密钥 ----------
echo ""
echo "=== 第 2 步: SSH 密钥（容器部署 / GPU / 风扇 / 磁盘模块需要）==="
if [ ! -f "$SSH_DIR/id_ed25519" ]; then
  ssh-keygen -t ed25519 -N "" -C "unraid-agent-skill" -f "$SSH_DIR/id_ed25519" >/dev/null 2>&1
  echo "✓ 已生成: $SSH_DIR/id_ed25519"
fi
echo "在 unRAID WebGUI 终端执行以下命令安装公钥:"
echo ""
echo "  mkdir -p /root/.ssh && chmod 700 /root/.ssh && echo '$(cat "$SSH_DIR/id_ed25519.pub")' >> /root/.ssh/authorized_keys && chmod 600 /root/.ssh/authorized_keys"
echo ""
read -p "公钥安装完成了吗? (y/N): " SSH_OK
if [ "$SSH_OK" != "y" ]; then
  echo "⚠ 跳过 SSH 配置：部署/GPU/风扇/磁盘模块将不可用，其余模块不受影响"
fi

# ---------- 4. 写入 profiles.json ----------
python3 - "$NAME" "$URL" "$HOST" << 'EOF'
import sys, os, json
name, url, host = sys.argv[1], sys.argv[2], sys.argv[3]
conf_dir = os.path.expanduser("~/.unraid")
pf = os.path.join(conf_dir, "profiles.json")
profiles = {}
if os.path.exists(pf):
    try:
        profiles = json.load(open(pf))
    except Exception:
        profiles = {}
profiles[name] = {
    "url": url,
    "key_file": os.path.join(conf_dir, "keys", f"{host}.key"),
    "ssh_key": os.path.join(conf_dir, "ssh", "id_ed25519"),
    "ssh_user": "root",
    "verify_ssl": False,
    "timeout": 15,
}
with open(pf, "w", encoding="utf-8") as f:
    json.dump(profiles, f, ensure_ascii=False, indent=2)
os.chmod(pf, 0o600)
print(f"✓ profiles.json 已写入: {pf}")
EOF

# ---------- 5. 验证 ----------
echo ""
echo "=== 验证 ==="
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
if [ -d "$SCRIPT_DIR/scripts" ]; then
  cd "$SCRIPT_DIR/scripts"
else
  cd "$(dirname "$0")"
fi
if python3 unraid_api.py --compat; then
  echo ""
  echo "✅ 安装完成！常用命令:"
  echo "  python3 info_system.py    # 系统信息"
  echo "  python3 info_array.py     # 阵列/磁盘"
  echo "  python3 info_docker.py    # 容器"
  echo "  python3 info_gpu.py       # GPU"
  echo "  python3 op_docker.py stop <容器>   # 管理（需确认）"
else
  echo "⚠ 验证未通过，请检查密钥/地址/SSH 配置后重试"
fi
