# OpenUBMC Forum 故障定位工具

本工具集用于 OpenUBMC/iBMC 日志包的自动化故障诊断，提供 Claude Code Skill 和独立 Python 脚本两种使用方式。

## 文件说明

| 文件 | 用途 |
|------|------|
| `bmc_log_analyzer.py` | 独立 Python 解析脚本，支持 `.tar.gz` 和目录 |
| `bmc_log_mcp_server.py` | MCP Server（6 个工具，stdio 模式） |
| `my_skill/bmc-analyze.md` | Claude Code Skill 定义文件 |

---

## bmc-analyze 使用说明

### 概述

`/bmc-analyze` 是一个 Claude Code Skill，用于分析 OpenUBMC/iBMC 的 `dump_info` 日志包，自动生成结构化故障诊断报告。

### 安装

将 `my_skill/bmc-analyze.md` 复制到 Claude Code 的 skills 目录：

```bash
cp my_skill/bmc-analyze.md ~/.claude/skills/bmc-analyze.md
```

### 用法

```
/bmc-analyze [日志包路径]
```

**支持的输入格式：**
- `.tar.gz` 压缩包：`/bmc-analyze dump_info.tar.gz`
- 解压后目录：`/bmc-analyze /path/to/dump_info/`
- 不指定路径：自动搜索当前目录下的 `*.tar.gz`、`dump_info*`、`null_*`

### 报告结构

Skill 执行后输出以下诊断报告：

1. **基本信息** — BMC 类型（iBMC/openUBMC）、固件版本、产品型号
2. **网络配置** — IP 地址、网口状态
3. **串口/Telnet 状态**（⚠️ 优先检查）— telnetd 进程是否运行、systemd 服务是否激活
4. **错误日志摘要** — ERROR 总数、Top 模块分布
5. **命令历史** — 管理员操作记录
6. **诊断建议** — 针对发现问题的可操作步骤

### 日志文件速查表

| 查找内容 | 文件路径 |
|---------|---------|
| BMC 版本 | `RTOSDump/versioninfo/app_revision.txt` |
| IP 地址 | `RTOSDump/networkinfo/ifconfig_info` |
| 串口/Telnet 配置 | `AppDump/bmc_network/network_info.txt` |
| 应用错误日志 | `LogDump/app.log` |
| 操作审计 | `LogDump/operation.log` |
| 内核错误 | `RTOSDump/driver_info/dmesg_info` |
| 服务状态 | `RTOSDump/sysinfo/journalctl.log` |
| 进程列表 | `RTOSDump/sysinfo/ps_info` |
| 管理员历史 | `RTOSDump/other_info/command_records/*/ash_history` |

### 串口故障专项排查（论坛 #4257 类问题）

用户反映"无法通过 Telnet 连接 BMC 串口"时，按以下顺序检查：

1. `RTOSDump/sysinfo/ps_info` — telnetd 进程是否在列
2. `RTOSDump/sysinfo/journalctl.log*` — telnetd.service 是否被 deactivated
3. `LogDump/operation.log` — 查找 "SOL session" / "Connect SOL failed"
4. `AppDump/bmc_network/network_info.txt` — 端口 23 防火墙规则

若 telnetd 服务已停止：通过 iBMC/openUBMC Web 界面 → 系统管理 → 串口配置，重新启用串口转发。

---

## 示例：分析 dump_info 日志包

### 执行命令

```
/bmc-analyze dump_info
```

### 输出报告示例

以下为对 `dump_info/` 目录（iBMC S920X20 设备）的实际分析结果：

---

#### 一、基本信息

| 项目 | 值 |
|------|-----|
| BMC 类型 | iBMC |
| 活跃版本 | 25.12.02.03 (Build 001) |
| 编译时间 | 2026-03-09 13:48:26 |
| 产品型号 | S920X20 |
| BIOS 版本 | (U75)000 |

#### 二、网络配置

| 接口 | IP 地址 | 状态 |
|------|---------|------|
| eth0 | 10.0.2.15 | UP |
| lo | 127.0.0.1 | UP |

#### 三、串口/Telnet 状态

| 项目 | 状态 |
|------|------|
| telnetd 进程 | 运行中 |
| 进程详情 | `/data/home/busybox_x telnetd` (PID 2150) |

**结论：** telnetd 正常运行，可通过 telnet 登录 BMC。

#### 四、错误日志摘要

| 日志类型 | 数量 |
|---------|------|
| app.log ERROR | 136 条 |
| 告警日志 | 1061 条 |
| dmesg 异常 | 0 条 |
| maintenance ERROR | 10 条 |

**Top 模块错误分布：**

| 模块 | 错误数 |
|------|--------|
| snmp | 43 |
| fault_diagnosis | 22 |
| interface | 18 |
| firmware_mgmt | 12 |
| power_mgmt | 11 |
| event | 11 |
| pcie_device | 9 |

#### 五、命令历史

共 11 条记录，发现 telnet 尝试：

```
telnet localhost
```

#### 六、诊断建议

**主要问题：** app.log 存在 136 条 ERROR，snmp 模块最多（43 条）

排查步骤：
1. 检查 `LogDump/app.log`，重点关注 `snmp` 模块错误
2. 查找最早 ERROR 时间戳，定位问题发生时间点
3. 如需深入排查 snmp：检查 `RTOSDump/sysinfo/journalctl.log` 中 snmp 服务状态

**串口/Telnet 方面无异常**，telnetd 进程正常运行。

---

## 底层脚本直接使用

不依赖 Claude Code，也可直接运行 Python 脚本：

```bash
python3 bmc_log_analyzer.py <日志包路径>
```

**示例：**

```bash
# 分析目录
python3 bmc_log_analyzer.py ./dump_info

# 分析压缩包
python3 bmc_log_analyzer.py ./dump_info.tar.gz
```

脚本自动处理 `dump_info/dump_info/`（双层嵌套）和 `null_xxx/dump_info/`（单层嵌套）两种目录结构。
