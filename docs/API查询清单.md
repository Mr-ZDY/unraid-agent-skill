# unRAID API 查询清单（v1.0.0 实测）

> 端点：`http://192.0.2.100/graphql`（端口 80）｜认证：`x-api-key` 头
> 生产环境禁用全量 introspection，但 `__type(name:"X")` 单类型内省可用。

## 1. 认证

| 角色 | 能力 | 备注 |
|---|---|---|
| ADMIN | 完整权限（含 DOCKER 写） | **skill 使用此角色** |
| CONNECT | Unraid Connect 功能 | **无 DOCKER 写权限**（踩坑记录） |
| VIEWER | 只读 | 查询可用 |
| GUEST | 有限访问 | - |

## 2. 只读查询（实测通过）

### 系统/版本
```graphql
{ info { os { hostname distro release codename kernel arch uptime uefi }
         versions { core { unraid api kernel } }
         cpu { brand cores threads speedmax }
         system { manufacturer model virtual } } }
```

### 阵列/磁盘
```graphql
{ array { state
  capacity { kilobytes { free used total } }
  parityCheckStatus { running status progress errors speed }
  boot { name size status }
  parities { idx name device size status temp fsType }
  disks { idx name device size status temp fsType fsFree fsUsed rotational isSpinning } } }
```
⚠ 单位：`size/fsFree/fsUsed` 为 **KB**（BigInt），显示需 ×1024。

### 共享
```graphql
{ shares { name free used size cache allocator splitLevel comment } }
```
⚠ `size=0` 表示无限制（显示"无限制"）。

### Docker 容器
```graphql
{ docker { containers { id names image state status lanIpPorts autoStart isUpdateAvailable webUiUrl registryUrl mounts } } }
```

### VM（服务未启用时返回错误 "VMs are not available" → 优雅提示）
```graphql
{ vms { domains { name state } } }
```

### 通知概览
```graphql
{ notifications { overview { unread { alert warning info } } } }
```

## 3. 写操作（mutation，确认门保护）

```graphql
mutation { docker { start(id:"...") { id names state status } } }
mutation { docker { stop(id:"...") { id names state status } } }
mutation { docker { restart(id:"...") { id names state status } } }
mutation { docker { updateContainer(id:"...") { id names state status isUpdateAvailable } } }
```
- 容器 id 通过 `docker { containers { id names } }` 按名称解析
- ⚠ **API 无容器创建 mutation** → 部署走 SSH + docker CLI（CA 模板 → docker create + dockerman 标签）

## 4. Schema 关键类型（实测内省）

| 类型 | 关键字段 |
|---|---|
| Info | os / versions{core{unraid,api,kernel}} / cpu / memory / system / primaryNetwork |
| UnraidArray | state / capacity{kilobytes} / parityCheckStatus / boot / parities / disks |
| ArrayDisk | idx/name/device/size(KB)/status/temp/fsType/fsFree/fsUsed/rotational/isSpinning |
| DockerContainer | id/names/image/state/status/lanIpPorts/autoStart/isUpdateAvailable/mounts |
| Vms | domains{name,state} |
| Notification | title/subject/description/importance/timestamp |

## 5. 枚举值

- ArrayState: STARTED/STOPPED/NEW_ARRAY/PARITY_NOT_BIGGEST/TOO_MANY_MISSING_DISKS/NEW_DISK_TOO_SMALL/NO_DATA_DISKS
- ArrayDiskStatus: DISK_OK/DISK_NP/DISK_DSBL/DISK_NEW/DISK_INVALID/DISK_WRONG/DISK_NP_MISSING
- ContainerState: RUNNING/PAUSED/EXITED
- VmState: NOSTATE/RUNNING/IDLE/PAUSED/SHUTDOWN/SHUTOFF/CRASHED/PMSUSPENDED
- NotificationImportance: ALERT/INFO/WARNING

## 7. 版本兼容性（2026-08-09）

| unRAID 版本 | 状态 | 说明 |
|---|---|---|
| 7.3.x | ✅ 实测通过 | 7.3.2 / API 4.37.0（本 skill 开发与验证环境） |
| 7.2.x | ⚠️ 同代 API，未实测 | 建议先 `python3 unraid_api.py --compat` 全绿再使用 |
| <7.2 | ❌ 不兼容 | 无内置 GraphQL API，skill 拒绝运行（设计行为） |
| 未来版本 | ⚠️ 自动预警 | `--compat` 自检版本状态 + 关键 schema 字段，漂移时明确提示 |

- 运行 `python3 unraid_api.py --compat` 可随时自检（版本状态 + 6 组关键字段抽查）
- 风险点：GraphQL schema 漂移（字段改名/删除）、unraid-api 组件独立升级、权限模型调整、CA AppFeed 格式变化
- SSH 类模块（info_gpu/fan/disks）依赖 smartctl/lm-sensors，**版本无关**（任何 unRAID 版本可用）

## 8. CA AppFeed（op_deploy 数据源）

- 地址：`https://raw.githubusercontent.com/Squidly271/AppFeed/master/applicationFeed-small.json`（8.3MB，本地缓存 12h）
- 结构：`applist`（4067 应用）+ `repositories` + `categories`
- 应用字段：Name/Repository/Registry/Network/Privileged/Overview/TemplateURL/CategoryList/stars/downloads
- 模板格式：v1（`<Networking><Publish>`）与 v2（`<Config Type="Port|Variable|Path">`）均已支持解析
