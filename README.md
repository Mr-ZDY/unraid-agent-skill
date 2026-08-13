<div align="center">

# 🖥️ unRAID Agent Skill

**让 AI Agent 通过官方 GraphQL API 查询与管理 unRAID（SSH 可选）**

纯 Python 标准库 · 零 pip 依赖 · 一切写操作走确认门 + 审计 · 默认最小权限（仅 API，不授 root/SSH）

[![unRAID](https://img.shields.io/badge/unRAID-7.2%2B-blue)](https://docs.unraid.net)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB)](https://www.python.org)
[![API](https://img.shields.io/badge/API-GraphQL-e10098)](#)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen)](#)

</div>

---

## ✨ 功能一览

| 类别 | 能力 | 说明 |
|---|---|---|
| 📊 **只读查询** | 9 个模块 | 系统 / 阵列磁盘 / 共享 / Docker / VM / 通知 / GPU / 风扇 / 磁盘用量+通电时间 |
| 🎛️ **容器管理** | 启停 / 重启 / 更新 | 官方 GraphQL mutation，确认门保护 |
| 📦 **CA 部署** | 搜索 / 详情 / 计划 / 部署 / 卸载 | Community Applications 全量目录（4000+ 应用），来源判定 + 端口规则 + SSH 自动执行 |
| 🔐 **安全框架** | 密钥认证 / 脱敏 / 审计 | 非密码认证；输出自动打码；全部操作留痕 |
| 🛡️ **兼容自检** | `--compat` | 版本门槛 + 关键 schema 字段抽查，升级无忧 |

> 🎯 **定位**：只读运维助手 + 容器常规管理。危险操作（电源管理、阵列变更）不在范围，人工处理。

> ⚠️ **风险声明**：本工具具有修改 NAS 状态的能力，请勿将未经验证的 Agent 会话授予生产数据权限；部署第三方容器前请核实镜像来源（默认强制 CA 官方应用 + 来源分级提示）。

---

## 🏗️ 架构

```
AI Agent (Hermes / Claude / ...)
        │
        │ 调用 CLI 脚本（确认门：写操作先展示摘要，显式确认才执行）
        ▼
┌─────────────────────────────┐
│      unraid-agent-skill     │
│  info_*.py   op_docker.py   │
│  op_deploy.py  unraid_api   │
└──────────────┬──────────────┘
       ┌───────┴────────┐
       ▼                ▼
  GraphQL API        SSH（可选，仅全功能模式）
  (x-api-key)        (部署/GPU/风扇/磁盘)
       │                │
       ▼                ▼
  unRAID 内置 API    Host OS (docker CLI / smartctl / lm-sensors)
```

---

## 🚀 快速开始

```bash
# 1. 克隆仓库
git clone https://github.com/Mr-ZDY/unraid-agent-skill.git
cd unraid-agent-skill

# 2. 一键安装引导（交互式）——默认最小权限模式
bash install.sh
#    → 输入服务器地址
#    → 粘贴 API 密钥（WebGUI：设置 → 管理访问 → API 密钥）
#    → SSH 步骤直接回车跳过（最小权限，推荐）；需要 CA 部署/GPU/风扇/磁盘再选 y
#    → 自动连通性验证

# 3. 开始使用
cd scripts
python3 info_system.py
```

**环境要求**：unRAID 7.2+ · Python 3.10+ · SSH 客户端（仅全功能模式需要）

---

## 🧭 部署模式（二选一）

> **最小权限模式【默认推荐】**：只配置 GraphQL API 密钥，不装 SSH、不授予 agent root。
> 覆盖 **90% 以上日常需求**：全部只读查询 + 容器启停/重启/更新。适合绝大多数用户与自动化场景。

| 模式 | 配置 | 能力 | 适合 |
|---|---|---|---|
| **🟢 最小权限**（默认） | API 密钥 | 9 个只读查询 + 容器管理（确认门） | 绝大多数用户；要求最小攻击面的生产环境 |
| **🔵 全功能** | API 密钥 + SSH 密钥 | 最小权限全部 + CA 部署/卸载、GPU、风扇、磁盘通电时间 | 需要 agent 代部署 CA 应用；自托管重度用户 |

**升级路径**：先用最小权限跑起来 → 确实需要 CA 部署 / GPU / 风扇 / 磁盘时，再运行
`install.sh` 补配 SSH（生成密钥 → unRAID 装公钥 → 重启 install 或手动在 profiles.json 补 `ssh_key` 字段）。

SSH 仅用于 4 个模块，**不配置时其余模块零影响**，且各脚本会明确提示当前为最小权限模式。

---

## 🖼️ 运行效果示例

> 以下为输出格式示例（主机名 / IP / 端口均已脱敏，按你的实际环境替换）：
> 示例值约定：IP 用文档保留段 `192.0.2.x`，主机名用 `MediaNAS`，端口用假值（见各命令旁的 `#` 注释）

```bash
$ python3 unraid_api.py --compat          # 版本 + 能力自检
unRAID 7.3.2 | API 4.37.0+8f6134ed | 状态: OK
版本状态: ✅ 已实测版本
schema 字段抽查:
  info_versions: ✓   array: ✓   docker: ✓
  shares: ✓   vms: ✓   notifications: ✓
```

```bash
$ python3 info_system.py                  # 系统信息
项目         值
---------  -----------------------------------
主机名        MediaNAS
发行版        Unraid OS 7.3 x86_64 (stable)
unRAID 版本  7.3.2
内核         6.18.38-Unraid
API 版本     4.37.0+8f6134ed
CPU        Gen Intel® Core™ i7-10700 (8核/16线程)
```

```bash
$ python3 info_array.py                   # 阵列与磁盘
阵列状态: 已启动
容量: 8.6 TB / 18.0 TB (剩余 9.5 TB, 使用率 47%)
校验检查: NEVER_RUN
启动盘: flash (14.9 GB)
```

```bash
$ python3 info_docker.py                  # 容器状态
容器          镜像                                    状态   IP:端口
----------  ----------------------------------------  ---  ----------------------------------------
/hermes-agent  nousresearch/hermes-agent:latest      运行中  ['192.0.2.100:9010']     ⚠有更新
/heimdall      lscr.io/linuxserver/heimdall          运行中  ['192.0.2.100:9020']
/iyuuplus-dev  iyuucn/iyuuplus-dev:latest            运行中  ['192.0.2.100:9030']
```

```bash
$ python3 op_deploy.py deploy whoami --port 9006 --yes   # CA 部署（确认门 + SSH 自动执行）
✓ 部署完成: whoami 运行中 (192.0.2.100:9006)
```

---

## 📖 命令速查

| 命令 | 功能 |
|---|---|
| `python3 unraid_api.py` / `--compat` | API 连通性 / 版本+能力自检 |
| `python3 info_system.py` | 系统信息（版本/内核/CPU/内存） |
| `python3 info_array.py` | 阵列状态 / 磁盘用量 / 温度 |
| `python3 info_share.py` | 共享目录使用情况 |
| `python3 info_docker.py` | 容器状态 / 端口 / 更新提示 |
| `python3 info_vm.py` | 虚拟机列表 |
| `python3 info_logs.py` | 通知概览（警报/警告） |
| `python3 info_gpu.py` | GPU 状态（宿主+容器双层验证） |
| `python3 info_fan.py` | 风扇转速 |
| `python3 info_disks.py` | 磁盘用量 + SMART 通电时间 |
| `python3 op_docker.py start\|stop\|restart\|update <容器>` | 容器管理（确认门） |
| `python3 op_deploy.py search\|info\|plan <应用>` | CA 搜索 / 详情 / 部署计划 |
| `python3 op_deploy.py deploy <应用> --port N` | 部署（需确认） |
| `python3 op_deploy.py remove <容器>` | 卸载（先展示数据卷） |

所有模块均支持 `--json` 输出，便于脚本化。

---

## 🔐 安全设计

1. **最小权限默认**：安装引导默认不配置 SSH（最小权限模式），agent 仅持有 GraphQL API 能力；SSH/root 是显式选择的全功能模式
2. **确认门**：写操作先展示摘要，显式确认才执行；无确认自动拒绝；全部审计到 `~/.unraid/audit.log`（600）
3. **CA 来源铁律**：部署优先 Community Applications 官方应用；第三方必须用户明确许可
4. **端口规则**：涉及新端口必须用户提供，同时列出已占用端口 + 推荐 3 个
5. **输出脱敏**：密钥 / 密码 / token 自动打码，不落日志
6. **多实例**：`profiles.json` 支持多台 unRAID 服务器

## 🛡️ Threat Model（威胁模型）

| 威胁 | 防护 |
|---|---|
| **Prompt Injection**（Agent 被诱导执行危险操作） | 写操作全走确认门；SKILL.md 明示危险操作一律人工 |
| **命令注入**（恶意容器名 / 参数） | `validate_name` 白名单校验；SSH 只执行代码内固定命令模板，**LLM 永不生成 shell** |
| **权限越界**（只读会话拿到写能力） | API 密钥角色分级（VIEWER 只读 / ADMIN 管理）；`--compat` 校验；最小权限模式无 SSH 面 |
| **Secret 泄露**（密钥进配置 / 日志 / 输出） | 密钥仅存 600 文件，配置只引用路径；输出经 auth.redact 脱敏；审计不含凭据 |
| **横向入侵**（Agent 被攻破后利用 SSH/root 控制宿主） | 默认最小权限模式根本不存在 SSH 面；全功能模式才引入，且写操作仍走确认门 |
| **供应链风险**（恶意第三方应用 / Skill 描述） | CA 来源分级强制提示；第三方安装必须用户显式许可 |
| **版本漂移**（unRAID 升级导致 API 破坏） | `<7.2` 拒绝；`--compat` 字段级自检预警 |

---

## ⚙️ 配置文件说明（profiles.json）

多实例配置存放在 `~/.unraid/profiles.json`（权限 600，`install.sh` 自动生成，也可用 `python3 conf.py add <名称> <url>` 手动添加）：

```json
{
  "prod": {
    "url": "http://192.0.2.100/graphql",
    "key_file": "/home/你的用户/.unraid/keys/192.0.2.100.key",
    "ssh_key": "/home/你的用户/.unraid/ssh/id_ed25519",
    "ssh_user": "root",
    "verify_ssl": false,
    "timeout": 15
  }
}
```

| 字段 | 说明 |
|---|---|
| `url` | unRAID GraphQL 端点（WebGUI 同源端口，如 `http://<IP>/graphql`） |
| `key_file` | API 密钥文件路径（`install.sh` 写入，600 权限） |
| `ssh_key` | SSH 私钥路径（**可选**，仅全功能模式；最小权限模式不配置此项） |
| `ssh_user` | SSH 登录用户（默认 root，仅全功能模式） |
| `verify_ssl` | 自签证书环境设 `false` |
| `timeout` | 请求超时秒数 |

> 多台服务器 = 多个 profile，用 `--server <名称>` 切换（如 `python3 info_array.py --server backup`）。

---

## 🧹 卸载 / 重置

```bash
# 1. 删除本机配置与缓存（profiles / 密钥 / SSH 密钥 / 审计日志 / CA 缓存）
rm -rf ~/.unraid

# 2. 撤销 unRAID 侧权限
#    - API 密钥：WebGUI → 设置 → 管理访问 → API 密钥 → 删除
#    - SSH 公钥：unRAID 终端执行（只删本 skill 的 key，不影响其他）
sed -i '/unraid-agent-skill/d' /root/.ssh/authorized_keys
```

---

## 🧩 版本兼容性

| unRAID 版本 | 状态 |
|---|---|
| 7.3.x | ✅ **实测通过**（7.3.2 / API 4.37.0） |
| 7.2.x | ⚠️ 同代 API，未实测（`--compat` 全绿即可用） |
| <7.2 | ❌ 无内置 API，自动拒绝 |
| 未来版本 | ⚠️ `--compat` 自动预警 schema 漂移 |

SSH 类模块（GPU / 风扇 / 磁盘）基于 smartctl / lm-sensors，**版本无关**。

---

## 📁 目录结构

```
unraid-agent-skill/
├── install.sh          # 安装引导（服务器 / 密钥 / SSH 可选 / 验证）
├── SKILL.md            # 技能声明（Agent 加载用）
├── SECURITY.md         # 安全说明 / 漏洞报告
├── CONTRIBUTING.md     # 贡献指南
├── CHANGELOG.md        # 变更日志
├── scripts/            # 16 个 Python 模块（纯标准库）
│   ├── unraid_api.py   # GraphQL 客户端（认证/重试/错误映射/兼容自检）
│   ├── auth.py         # 密钥管理 + 输出脱敏
│   ├── confirm.py      # 确认门 + 审计
│   ├── info_*.py       # 9 个只读查询模块
│   └── op_*.py         # 容器管理 / CA 部署
├── docs/               # API 查询清单 + 操作清单（含踩坑记录）
└── tests/              # 单元测试 + 安全测试
```

---

## 🗺️ 路线图

- **v1.1**：文件写操作 / 共享配置修改 / 校验检查发起 / VM 管理 / Permission Policy（操作白名单 + 三级风险 + 高危输入短语确认如 "CONFIRM DELETE plex"）/ Mock unRAID 测试（Golden+Fuzz）/ 哈希链审计日志 / 结构化返回协议（JSON action 结果 + **Operation ID** 全链路追踪）/ 非 root SSH 操作用户
- **后续**：影视库适配器（Plex / Jellyfin）/ 接入 Hermes 长期会话 / **MCP Server 化**（Skill + MCP，兼容 Claude/OpenClaw/Cursor）/ 操作回滚（docker update 前快照）/ 审计 Agent Identity / CI 加固（bandit）
- **最后一版**：电源管理（重启 / 关机，双重确认）/ 签名发布

---

## 🤝 贡献

- 🐛 发现问题？[提交 Issue](https://github.com/Mr-ZDY/unraid-agent-skill/issues/new?template=bug_report.md)（附 `--compat` 输出）
- 💡 有想法？[功能请求](https://github.com/Mr-ZDY/unraid-agent-skill/issues/new?template=feature_request.md)
- ✏️ PR 欢迎！

---

<div align="center">

**MIT License** · Made with ❤️ for the unRAID community

</div>
