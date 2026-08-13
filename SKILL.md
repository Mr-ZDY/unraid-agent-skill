---
name: unraid-agent
description: >
  Use when the user asks about unRAID server status (version, array, disks, pools,
  SMART, parity), shares/disk usage, Docker containers, VMs, notifications, logs,
  or wants to start/stop/restart/update containers, or deploy/remove containers
  via Community Applications. Requires unRAID 7.2+ (built-in GraphQL API) and an
  API key on the WSL host (SSH key optional, only for CA deploy / GPU / fan / disk
  modules). All write operations require user approval.
version: 1.1.0
---

# unRAID Agent Skill v1.1.0

通过官方 GraphQL API 查询与管理 unRAID（SSH 可选，仅全功能模式）。**只读查询直接执行；一切写操作先展示摘要、等待用户确认，确认后才执行。**

**部署模式**：默认「最小权限模式」= 仅 API 密钥（覆盖 90% 需求：只读查询 + 容器启停/更新）；「全功能模式」= API + SSH（额外 CA 部署/卸载、GPU、风扇、磁盘）。SSH 缺失时相关脚本自动提示并退出，不影响其余模块。

## 前置条件

- unRAID 7.2+（实测 7.3.2，API 4.37.0）
- API 密钥（ADMIN 角色，容器管理必需）：`~/.unraid/keys/<server>.key`（600 权限）
- SSH 免密密钥（**可选，仅全功能模式**）：`~/.unraid/ssh/id_ed25519`（公钥装 unRAID `/root/.ssh/authorized_keys`）
- 服务器 profile：`~/.unraid/profiles.json`（由 install.sh 生成，支持多台服务器）

## 命令清单（scripts/ 目录下执行）

### 只读查询（无需确认）

| 命令 | 功能 |
|---|---|
| `python3 unraid_api.py` | API 连通性 + 版本检查（<7.2 拒绝） |
| `python3 info_system.py` | 系统/CPU/主板/版本/UEFI |
| `python3 info_array.py` | 阵列状态/容量/磁盘明细/校验状态 |
| `python3 info_share.py` | 共享列表/用量/分配方式 |
| `python3 info_docker.py` | 容器列表/状态/端口/更新提示 |
| `python3 info_vm.py` | VM 列表（服务未启用时提示） |
| `python3 info_logs.py` | 通知概览（警报/警告/信息） |
| `python3 info_gpu.py` | GPU 状态（宿主 nvidia-smi + 容器内验证两层） |
| `python3 info_fan.py` | 风扇转速（hwmon + sensors 标签） |
| `python3 info_disks.py` | 磁盘用量 + SMART 通电时间（含未挂阵列盘） |
| `python3 op_deploy.py search <关键词>` | CA 应用搜索（4067 应用，只读） |
| `python3 op_deploy.py info <应用>` | 应用详情 + 来源判定（官方/社区/第三方） |
| `python3 op_deploy.py plan <应用> --port N` | 部署计划预览（不执行） |

### 写操作（确认门：摘要 → 用户明确同意 → 执行 → 审计）

| 命令 | 说明 |
|---|---|
| `python3 op_docker.py start\|stop\|restart\|update <容器> --yes` | 容器生命周期管理（Agent 在用户同意后加 --yes） |
| `python3 op_deploy.py deploy <应用> --port N --yes` | 部署 CA 应用（SSH 自动执行） |
| `python3 op_deploy.py remove <容器> --yes` | 卸载容器（先展示数据卷路径） |

## 安全规则（必须遵守，用户规定）

1. **未经用户批准，不得执行任何写操作**；写操作必须走确认门（摘要 → 确认 → 执行 → 审计 ~/.unraid/audit.log）
2. **容器部署来源铁律**：优先 Community Applications 官方/可信应用；第三方必须用户明确许可；禁止裸 docker run/pull 任意镜像
3. **端口规则**：涉及新增端口必须用户提供；同时列出已占用端口 + 推荐端口（上限 3 个）
4. **权限矩阵**：VIEWER=只读；CONNECT=Connect 功能（无 DOCKER 写）；容器管理必须 ADMIN
5. 所有输出经 auth.redact 脱敏（密钥/密码/token 打码），审计不落敏感值
6. unRAID < 7.2 提示 API 不可用，改用 WebGUI 人工操作
7. 危险操作（关机/重启/阵列变更/格式化）不在本工具范围，一律人工处理

## 已知环境事实（2026-08-09 实测，示例环境 unRAID 7.3.2）

- API 端点：`http://<服务器IP>/graphql`（WebGUI 同源端口，非第三方容器端口）
- 磁盘 size/fsFree 等 BigInt 字段单位是 **KB**（需 ×1024）
- 容器 start/stop/restart/update 走 `docker { start/stop/restart/updateContainer }` mutation
- API 无容器创建 mutation → 部署经 SSH + docker CLI（CA 模板生成命令 + dockerman 标签；仅全功能模式）
- whoami 等 CA v2 模板用 `<Config Type="Port">` 定义端口（新旧格式解析均已支持）
- macvlan 隔离：宿主/经宿主转发的流量无法访问 macvlan 容器 → 用共享内部 bridge 网络（mp-net 方案）解决
- nvidia runtime 容器静态 inspect Devices=[] 属正常，GPU 是否注入以容器内验证为准（info_gpu.py）

## 故障排查

- `Forbidden resource` → 密钥角色权限不足（需 ADMIN）
- 401 → 密钥无效/已撤销，换新密钥更新 `~/.unraid/keys/`
- SSH 拒绝 → 确认用 `-i ~/.unraid/ssh/id_ed25519`；公钥在 unRAID `/root/.ssh/authorized_keys`
- GraphQL 字段名错误 → 用 `__type(name:"X"){fields{name}}` 内省（生产禁全量 introspection）
