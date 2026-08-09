# 贡献指南（Contributing）

感谢你愿意为 unRAID Agent Skill 贡献！请遵守以下约定。

## 快速开始

```bash
git clone https://github.com/Mr-ZDY/unraid-agent-skill.git
cd unraid-agent-skill
bash install.sh            # 配置你的测试服务器（或用测试 profile）
cd scripts
python3 tests/test_redact.py
python3 tests/test_security.py
```

## 代码规范

- Python 3.10+，**仅标准库**（本项目的核心卖点，请勿引入第三方依赖）
- 模块职责单一：`info_*` = 只读查询，`op_*` = 写操作（必须走确认门）
- 写操作必须：展示摘要 → `confirm.request_confirm` → 审计留痕
- 所有输出经 `auth.redact` 脱敏
- 进入 SSH 命令的任何用户输入必须过 `validate_name` 白名单校验

## 提交 PR

1. 从 `main` 新建分支：`git checkout -b feat/xxx`
2. 提交信息：`feat: ` / `fix: ` / `docs: ` / `test: ` 前缀 + 简短说明
3. 运行测试：`python3 tests/test_redact.py && python3 tests/test_security.py`（须全绿）
4. 通过 PR 模板提交，说明改动与验证情况

## 隐私红线（重要）

本仓库是**公开仓库**：
- ❌ 不得提交任何真实服务器信息：IP / 端口 / 主机名 / 域名 / 密钥 / 账号
- ✅ 示例一律用占位符：IP 用 `192.0.2.x`（RFC5737 文档段）、主机名用 `MediaNAS`、端口用假值
- ✅ 提交前自行扫描残留：`grep -rnE "192\.168\.|你的真实域名" .`

## Issue 规范

- Bug 报告请用模板（含环境信息与 `--compat` 输出）
- 功能请求请说明使用场景与优先级
