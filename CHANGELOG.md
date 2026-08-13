# Changelog

本项目遵循 [Semantic Versioning](https://semver.org/lang/zh-CN/)。

## [v1.1.0] - 2026-08-13

### 新增
- **最小权限模式【默认推荐】**：SSH 改为可选。仅配置 GraphQL API 密钥即可使用全部只读查询 + 容器启停/重启/更新（覆盖 90% 以上需求），不再默认授予 agent root/SSH
- 部署模式二选一：🟢 最小权限（仅 API）/ 🔵 全功能（API + SSH，额外 CA 部署/卸载、GPU、风扇、磁盘）
- `conf.py` 新增 `ssh_available()`；`ssh_key` 字段改为可选（缺省 = 最小权限模式）
- SSH 模块优雅降级：最小权限模式下 info_gpu / info_fan / info_disks / op_deploy 明确提示并退出，其余模块零影响

### 安全
- 威胁模型新增「横向入侵」防护：默认无 SSH 面，agent 被攻破也无法控制宿主

### 文档
- README 新增「部署模式」章节 + 快速开始默认最小权限 + 升级路径
- SECURITY.md 权限建议重写（最小权限默认 / SSH 面最小化）
- SKILL.md / install.sh / CHANGELOG 同步

## [v1.0.0] - 2026-08-09

### 新增
- 只读查询 9 模块：系统 / 阵列磁盘 / 共享 / Docker / VM / 通知 / GPU / 风扇 / 磁盘用量+通电时间
- 容器管理：启动 / 停止 / 重启 / 更新（op_docker，确认门保护）
- CA 应用部署：搜索 / 详情 / 部署计划 / 部署 / 卸载（op_deploy）
  - CA 来源分级（官方 / 社区 / 第三方）+ 端口规则（用户提供 + 推荐 3 个）+ SSH 自动执行
- 安全框架：API 密钥认证、输出脱敏、确认门、审计日志、版本门槛
- `--compat` 能力自检（版本状态 + 关键 schema 字段抽查）
- 安装引导：`install.sh`（服务器 / 密钥 / SSH / 连通性验证）

### 安全
- 命令注入防护：容器名 / 应用名白名单校验（`validate_name`）
- 多实例 profile 支持（`profiles.json`，600 权限）

### 文档
- README（功能 / 真实效果示例 / 命令速查 / 安全设计 / 配置说明 / 卸载指南）
- API 查询清单（GraphQL 实测字段 / 角色权限矩阵 / 版本兼容表）
- 操作清单（操作分级 / 踩坑记录）
- SECURITY.md / CONTRIBUTING.md

### 测试
- 脱敏单元测试 10 项
- 安全测试（注入防护 / 端口校验 / 脱敏回归）
