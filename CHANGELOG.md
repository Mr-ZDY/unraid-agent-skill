# Changelog

本项目遵循 [Semantic Versioning](https://semver.org/lang/zh-CN/)。

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
