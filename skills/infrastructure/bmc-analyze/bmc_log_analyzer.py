#!/usr/bin/env python3
"""
BMC 日志包分析器 - 独立脚本版本
用途：解析 OpenUBMC/iBMC 的 dump_info.tar.gz 日志包，生成结构化摘要报告
版本：v1.0  日期：2026-03-11
"""

import os
import re
import sys
import gzip
import tarfile
import argparse
import textwrap
from pathlib import Path
from datetime import datetime


# ─── 1. 日志包结构定义 ───────────────────────────────────────────────────────

# 关键文件路径模式（相对于 dump_info/ 根目录）
KEY_FILES = {
    "version":       "RTOSDump/versioninfo/app_revision.txt",
    "rtos_release":  "RTOSDump/versioninfo/RTOS-Release",
    "server_config": "RTOSDump/versioninfo/server_config.txt",
    "ifconfig":      "RTOSDump/networkinfo/ifconfig_info",
    "network_info":  "AppDump/bmc_network/network_info.txt",
    "netstat":       "RTOSDump/networkinfo/netstat_info",
    "route":         "RTOSDump/networkinfo/route_info",
    "sshd_config":   "RTOSDump/other_info/sshd_config",
    "app_log":       "LogDump/app.log",
    "operation_log": "LogDump/operation.log",
    "alarm_log":     "LogDump/alarm.log",
    "maintenance_log": "LogDump/maintenance.log",
    "dmesg":         "RTOSDump/driver_info/dmesg_info",
    "journalctl":    "RTOSDump/sysinfo/journalctl.log",
    "ps_info":       "RTOSDump/sysinfo/ps_info",
    "top_info":      "RTOSDump/sysinfo/top_info",
    "cmd_history":   "RTOSDump/other_info/command_records/Administrator/ash_history",
    "lldp_info":     "AppDump/bmc_network/lldp_info.txt",
}

# ─── 2. 日志包发现与解压 ─────────────────────────────────────────────────────

def find_dump_root(base_path: Path) -> Path | None:
    """在给定路径下找到 dump_info 根目录（处理嵌套结构）"""
    # 情况1: base_path 本身就是 dump_info 目录
    if (base_path / "RTOSDump").exists():
        return base_path
    if (base_path / "LogDump").exists():
        return base_path
    # 情况2: base_path/dump_info/...（单层嵌套）
    for sub in base_path.iterdir():
        if sub.is_dir():
            if (sub / "RTOSDump").exists() or (sub / "LogDump").exists():
                return sub
    # 情况3: base_path/dump_info/dump_info/...（双层嵌套）
    for sub in base_path.iterdir():
        if sub.is_dir():
            for sub2 in sub.iterdir():
                if sub2.is_dir():
                    if (sub2 / "RTOSDump").exists() or (sub2 / "LogDump").exists():
                        return sub2
    return None


def extract_if_needed(path_str: str) -> Path:
    """如果是 tar.gz 则解压到临时目录，否则直接返回路径"""
    p = Path(path_str)
    if not p.exists():
        raise FileNotFoundError(f"路径不存在: {path_str}")

    if p.suffix in (".gz", ".tgz") or path_str.endswith(".tar.gz"):
        import tempfile
        tmpdir = tempfile.mkdtemp(prefix="bmc_analyze_")
        print(f"[INFO] 解压 {p.name} 到 {tmpdir} ...", file=sys.stderr)
        with tarfile.open(p, "r:gz") as tar:
            tar.extractall(tmpdir)
        return Path(tmpdir)
    return p


# ─── 3. 文件读取工具 ─────────────────────────────────────────────────────────

def read_file_safe(path: Path, max_bytes: int = 102400) -> str:
    """安全读取文件内容，处理编码错误，支持 .gz"""
    if not path.exists():
        return ""
    try:
        if path.suffix == ".gz":
            with gzip.open(path, "rt", encoding="utf-8", errors="replace") as f:
                return f.read(max_bytes)
        else:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                return f.read(max_bytes)
    except Exception:
        return ""


def get_file(root: Path, rel_path: str) -> tuple[Path, str]:
    """获取文件路径和内容"""
    full_path = root / rel_path
    content = read_file_safe(full_path)
    return full_path, content


# ─── 4. 各模块分析函数 ───────────────────────────────────────────────────────

def analyze_version(root: Path) -> dict:
    """解析版本信息"""
    _, content = get_file(root, KEY_FILES["version"])
    result = {
        "bmc_version": "未知",
        "bmc_type": "iBMC",   # iBMC or openUBMC
        "bmc_build": "未知",
        "bmc_built": "未知",
        "backup_version": "未知",
        "product_name": "未知",
        "bios_version": "未知",
        "raw": content[:2000] if content else "",
    }
    if not content:
        return result

    # 检测是iBMC还是openUBMC
    if "openUBMC" in content:
        result["bmc_type"] = "openUBMC"
        m = re.search(r"Active openUBMC\s+Version:\s+(\S+)", content)
    else:
        result["bmc_type"] = "iBMC"
        m = re.search(r"Active iBMC\s+Version:\s+(\S+)", content)

    if m:
        result["bmc_version"] = m.group(1)

    m = re.search(r"Active iBMC\s+Build:\s+(\S+)|Active openUBMC\s+Build:\s+(\S+)", content)
    if m:
        result["bmc_build"] = m.group(1) or m.group(2) or "未知"

    m = re.search(r"Active iBMC\s+Built:\s+(.+)|Active openUBMC\s+Built:\s+(.+)", content)
    if m:
        result["bmc_built"] = (m.group(1) or m.group(2) or "").strip()

    m = re.search(r"Backup iBMC\s+Version:\s+(\S+)|Backup openUBMC\s+Version:\s+(\S+)", content)
    if m:
        result["backup_version"] = m.group(1) or m.group(2) or "未知"

    m = re.search(r"Product\s+Name:\s+(.+)", content)
    if m:
        result["product_name"] = m.group(1).strip()

    m = re.search(r"Active BIOS\s+Version:\s+(.+)", content)
    if m:
        result["bios_version"] = m.group(1).strip()

    return result


def analyze_network(root: Path) -> dict:
    """解析网络配置"""
    _, ifconfig = get_file(root, KEY_FILES["ifconfig"])
    _, network_info = get_file(root, KEY_FILES["network_info"])
    _, netstat = get_file(root, KEY_FILES["netstat"])

    result = {
        "interfaces": [],
        "bmc_ip": "未知",
        "active_port": "未知",
        "net_mode": "未知",
        "telnet_port_open": False,
        "telnet_port": 23,
        "listening_ports": [],
        "firewall_rules_count": 0,
    }

    # 解析 ifconfig
    if ifconfig:
        # 解析各网口
        blocks = re.split(r'\n(?=\w)', ifconfig.strip())
        for block in blocks:
            m_iface = re.match(r'^(\w+)\s+', block)
            m_ip = re.search(r'inet addr:(\S+)', block)
            m_mac = re.search(r'HWaddr (\S+)', block)
            m_state = re.search(r'\b(UP|DOWN)\b', block)
            if m_iface:
                iface = {
                    "name": m_iface.group(1),
                    "ip": m_ip.group(1) if m_ip else None,
                    "mac": m_mac.group(1) if m_mac else None,
                    "state": m_state.group(1) if m_state else "UNKNOWN",
                }
                result["interfaces"].append(iface)
                if iface["ip"] and iface["ip"] != "127.0.0.1":
                    result["bmc_ip"] = iface["ip"]

    # 解析 network_info.txt（BMC应用层配置）
    if network_info:
        m = re.search(r"Active Port\s*:\s*(\S+)", network_info)
        if m:
            result["active_port"] = m.group(1)
        m = re.search(r"Net Mode\s*:\s*(.+)", network_info)
        if m:
            result["net_mode"] = m.group(1).strip()
        # 统计防火墙规则数
        result["firewall_rules_count"] = network_info.count("ACCEPT") + network_info.count("DROP")

    # 解析 netstat（检查监听端口）
    if netstat:
        for line in netstat.split("\n"):
            m = re.search(r"tcp.*:(\d+)\s+.*LISTEN", line)
            if m:
                port = int(m.group(1))
                result["listening_ports"].append(port)
                if port == 23:
                    result["telnet_port_open"] = True

    return result


def analyze_serial_config(root: Path) -> dict:
    """专项分析串口/telnet配置（帖子#4257的核心问题）"""
    _, ps_info = get_file(root, KEY_FILES["ps_info"])
    _, top_info = get_file(root, KEY_FILES["top_info"])
    # 合并所有 journalctl 文件（.log, .log.1, .log.2, .log.3）
    journalctl_all = []
    for jname in ["RTOSDump/sysinfo/journalctl.log", "RTOSDump/sysinfo/journalctl.log.1",
                  "RTOSDump/sysinfo/journalctl.log.2", "RTOSDump/sysinfo/journalctl.log.3"]:
        _, jcontent = get_file(root, jname)
        if jcontent:
            journalctl_all.append(jcontent)
    journalctl = "\n".join(journalctl_all)
    _, op_log = get_file(root, KEY_FILES["operation_log"])
    _, netstat = get_file(root, KEY_FILES["netstat"])

    result = {
        "telnetd_running": False,
        "telnetd_process": "",
        "telnetd_service_state": "未知",  # active/inactive/stopped
        "serial_operations": [],          # 从操作日志提取
        "sol_config": "未知",             # SOL (Serial Over LAN) 状态
        "diagnosis": [],                  # 诊断结论
    }

    # 1. 检查 telnetd 进程
    for source, text in [("ps_info", ps_info), ("top_info", top_info)]:
        if text:
            for line in text.split("\n"):
                if "telnetd" in line.lower() and not line.strip().startswith("#"):
                    result["telnetd_running"] = True
                    result["telnetd_process"] = line.strip()
                    break

    # 2. 从 journalctl 检查 telnetd service 状态
    if journalctl:
        # 找最后一条关于 telnetd 的记录
        telnet_events = []
        for line in journalctl.split("\n"):
            if "telnetd" in line.lower():
                telnet_events.append(line.strip())
        if telnet_events:
            last_event = telnet_events[-1]
            if "Deactivated" in last_event or "Stopped" in last_event:
                result["telnetd_service_state"] = "已停止(inactive)"
            elif "Started" in last_event or "Active" in last_event:
                result["telnetd_service_state"] = "已启动(active)"
            result["telnetd_last_event"] = last_event

    # 3. 从操作日志提取串口操作
    if op_log:
        for line in op_log.split("\n"):
            if "serial" in line.lower() or "sol" in line.lower() or "串口" in line:
                result["serial_operations"].append(line.strip())

    # 4. 检查 netstat 中是否有 telnet 端口 23 监听
    if netstat:
        telnet_listening = bool(re.search(r":23\s+.*LISTEN", netstat))
        if telnet_listening:
            result["telnetd_port_listening"] = True
        else:
            result["telnetd_port_listening"] = False

    # 5. 生成诊断结论
    if result["telnetd_running"]:
        result["diagnosis"].append("✓ telnetd 进程运行中（可通过 telnet 登录 BMC）")
    else:
        result["diagnosis"].append("✗ 未检测到运行中的 telnetd 进程")

    if result["telnetd_service_state"] == "已停止(inactive)":
        result["diagnosis"].append("✗ systemd telnetd.service 已停止，这可能导致无法通过 telnet 登录 BMC 串口")
        result["diagnosis"].append("→ 建议：通过 iBMC Web 界面 → 系统管理 → 串口配置，检查并启用串口转发功能")
    elif result["telnetd_service_state"] == "已启动(active)":
        result["diagnosis"].append("✓ systemd telnetd.service 已启动")

    if result["serial_operations"]:
        result["diagnosis"].append(f"ℹ 操作日志中有 {len(result['serial_operations'])} 条串口相关操作记录")

    return result


def analyze_errors(root: Path) -> dict:
    """分析错误日志"""
    result = {
        "app_error_count": 0,
        "app_errors_top": [],       # 按模块统计
        "dmesg_errors": [],
        "maintenance_errors": [],
        "alarm_count": 0,
        "critical_errors": [],      # 严重错误（需要关注的）
    }

    # app.log 错误分析
    _, app_log = get_file(root, KEY_FILES["app_log"])
    if app_log:
        errors = [l for l in app_log.split("\n") if " ERROR:" in l or " FATAL:" in l or " WARNING:" in l]
        result["app_error_count"] = len([l for l in errors if " ERROR:" in l or " FATAL:" in l])
        # 按模块统计（日志格式: TIMESTAMP MODULE LEVEL: file(line): msg）
        module_counts = {}
        for err in errors:
            # 格式1: 2023-08-15 09:20:57.640619 devmon ERROR: ...
            m = re.match(r"\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\S*\s+(\w+)\s+(?:ERROR|FATAL|WARNING):", err)
            if m:
                mod = m.group(1)
                module_counts[mod] = module_counts.get(mod, 0) + 1
        result["app_errors_top"] = sorted(module_counts.items(), key=lambda x: -x[1])[:10]
        # 提取 FATAL 级别
        fatals = [l.strip() for l in app_log.split("\n") if " FATAL:" in l]
        result["critical_errors"].extend(fatals[:5])

    # dmesg 错误
    _, dmesg = get_file(root, KEY_FILES["dmesg"])
    if dmesg:
        dmesg_errs = [l.strip() for l in dmesg.split("\n")
                      if re.search(r'\b(error|fail|panic|oops|BUG|WARN)\b', l, re.I)]
        result["dmesg_errors"] = dmesg_errs[:20]

    # maintenance_log 错误
    _, maint = get_file(root, KEY_FILES["maintenance_log"])
    if maint:
        maint_errs = [l.strip() for l in maint.split("\n") if " ERROR:" in l]
        result["maintenance_errors"] = maint_errs[:10]

    # alarm.log
    _, alarm = get_file(root, KEY_FILES["alarm_log"])
    if alarm:
        result["alarm_count"] = len([l for l in alarm.split("\n") if l.strip()])

    return result


def analyze_system_state(root: Path) -> dict:
    """分析系统状态（内存、进程、运行时间）"""
    result = {
        "uptime": "未知",
        "memory_total": "未知",
        "memory_free": "未知",
        "top_processes": [],
    }

    # uptime
    uptime_path = root / "RTOSDump/sysinfo/uptime"
    if uptime_path.exists():
        content = read_file_safe(uptime_path)
        result["uptime"] = content.strip()

    # memory
    free_path = root / "RTOSDump/sysinfo/free_info"
    if free_path.exists():
        content = read_file_safe(free_path)
        for line in content.split("\n"):
            if line.startswith("Mem:"):
                parts = line.split()
                if len(parts) >= 3:
                    result["memory_total"] = parts[1] + " kB"
                    result["memory_free"] = parts[3] + " kB"

    return result


def analyze_command_history(root: Path) -> dict:
    """分析管理员命令历史"""
    # 支持通配符：command_records 下可能有多个用户目录
    cmd_records_dir = root / "RTOSDump/other_info/command_records"
    history_content = ""
    if cmd_records_dir.exists():
        for user_dir in cmd_records_dir.iterdir():
            if user_dir.is_dir():
                hist_file = user_dir / "ash_history"
                if hist_file.exists():
                    history_content += read_file_safe(hist_file)
    # 兜底：尝试固定路径
    if not history_content:
        _, history_content = get_file(root, KEY_FILES["cmd_history"])
    result = {
        "has_history": bool(history_content),
        "commands": [],
        "telnet_attempts": [],
        "suspicious_commands": [],
    }
    if history_content:
        cmds = [l.strip() for l in history_content.split("\n") if l.strip()]
        result["commands"] = cmds
        result["telnet_attempts"] = [c for c in cmds if "telnet" in c.lower()]
        # 标记危险操作
        dangerous = ["rm -rf", "chmod 777", "mkfs", "dd if=", "passwd", "> /dev/"]
        for cmd in cmds:
            for d in dangerous:
                if d in cmd:
                    result["suspicious_commands"].append(cmd)
    return result


# ─── 5. 报告生成 ─────────────────────────────────────────────────────────────

def generate_report(root: Path, pkg_name: str) -> str:
    """生成完整的 Markdown 格式分析报告"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    print("[INFO] 分析版本信息...", file=sys.stderr)
    ver = analyze_version(root)
    print("[INFO] 分析网络配置...", file=sys.stderr)
    net = analyze_network(root)
    print("[INFO] 分析串口配置...", file=sys.stderr)
    serial = analyze_serial_config(root)
    print("[INFO] 分析错误日志...", file=sys.stderr)
    errors = analyze_errors(root)
    print("[INFO] 分析系统状态...", file=sys.stderr)
    sysstate = analyze_system_state(root)
    print("[INFO] 分析命令历史...", file=sys.stderr)
    cmdhist = analyze_command_history(root)

    lines = []

    # 标题
    lines.append(f"# BMC 日志分析报告")
    lines.append(f"")
    lines.append(f"- **日志包**: `{pkg_name}`")
    lines.append(f"- **分析时间**: {now}")
    lines.append(f"- **日志根目录**: `{root}`")
    lines.append(f"")

    # ── 基本信息 ──
    lines.append(f"## 一、基本信息")
    lines.append(f"")
    lines.append(f"| 项目 | 值 |")
    lines.append(f"|------|-----|")
    lines.append(f"| BMC类型 | {ver['bmc_type']} |")
    lines.append(f"| 活跃版本 | **{ver['bmc_version']}** (Build {ver['bmc_build']}) |")
    lines.append(f"| 编译时间 | {ver['bmc_built']} |")
    lines.append(f"| 备份版本 | {ver['backup_version']} |")
    lines.append(f"| 产品型号 | {ver['product_name']} |")
    lines.append(f"| BIOS版本 | {ver['bios_version']} |")
    lines.append(f"")

    # ── 网络配置 ──
    lines.append(f"## 二、网络配置")
    lines.append(f"")
    lines.append(f"| 项目 | 值 |")
    lines.append(f"|------|-----|")
    lines.append(f"| BMC IP地址 | **{net['bmc_ip']}** |")
    lines.append(f"| 活跃端口 | {net['active_port']} |")
    lines.append(f"| 网络模式 | {net['net_mode']} |")
    lines.append(f"")
    lines.append(f"**网络接口状态：**")
    lines.append(f"")
    if net["interfaces"]:
        lines.append(f"| 接口 | IP地址 | MAC | 状态 |")
        lines.append(f"|------|--------|-----|------|")
        for iface in net["interfaces"]:
            ip = iface.get("ip") or "-"
            mac = iface.get("mac") or "-"
            state = iface.get("state", "UNKNOWN")
            state_icon = "✓" if state == "UP" else "✗"
            lines.append(f"| {iface['name']} | {ip} | {mac} | {state_icon} {state} |")
    else:
        lines.append(f"_未找到网络接口信息_")
    lines.append(f"")

    # ── 串口/Telnet 配置（重点！） ──
    lines.append(f"## 三、串口/Telnet 配置 ⚠️")
    lines.append(f"")
    lines.append(f"| 项目 | 值 |")
    lines.append(f"|------|-----|")
    telnetd_icon = "✓ 运行中" if serial["telnetd_running"] else "✗ 未运行"
    lines.append(f"| telnetd 进程 | **{telnetd_icon}** |")
    lines.append(f"| telnetd 服务状态 | {serial['telnetd_service_state']} |")
    lines.append(f"")

    if serial["telnetd_process"]:
        lines.append(f"**进程信息：**")
        lines.append(f"```")
        lines.append(serial["telnetd_process"][:200])
        lines.append(f"```")
        lines.append(f"")

    lines.append(f"**诊断结论：**")
    lines.append(f"")
    for d in serial["diagnosis"]:
        lines.append(f"- {d}")
    lines.append(f"")

    if serial["serial_operations"]:
        lines.append(f"**操作日志中的串口操作记录（最近 {min(5, len(serial['serial_operations']))} 条）：**")
        lines.append(f"")
        lines.append(f"```")
        for op in serial["serial_operations"][-5:]:
            lines.append(op[:200])
        lines.append(f"```")
        lines.append(f"")

    # ── 错误日志摘要 ──
    lines.append(f"## 四、错误日志摘要")
    lines.append(f"")
    lines.append(f"| 日志类型 | 数量 |")
    lines.append(f"|---------|------|")
    lines.append(f"| app.log ERROR 条数 | {errors['app_error_count']} |")
    lines.append(f"| 告警日志条数 | {errors['alarm_count']} |")
    lines.append(f"| dmesg 异常条数 | {len(errors['dmesg_errors'])} |")
    lines.append(f"| maintenance ERROR 条数 | {len(errors['maintenance_errors'])} |")
    lines.append(f"")

    if errors["app_errors_top"]:
        lines.append(f"**app.log 错误按模块分布（Top 10）：**")
        lines.append(f"")
        lines.append(f"| 模块 | 错误数 |")
        lines.append(f"|------|--------|")
        for mod, cnt in errors["app_errors_top"]:
            lines.append(f"| {mod} | {cnt} |")
        lines.append(f"")

    if errors["critical_errors"]:
        lines.append(f"**FATAL 级别错误：**")
        lines.append(f"")
        lines.append(f"```")
        for e in errors["critical_errors"]:
            lines.append(e[:200])
        lines.append(f"```")
        lines.append(f"")

    if errors["dmesg_errors"]:
        lines.append(f"**dmesg 关键错误（前20条）：**")
        lines.append(f"")
        lines.append(f"```")
        for e in errors["dmesg_errors"][:10]:
            lines.append(e[:200])
        lines.append(f"```")
        lines.append(f"")

    # ── 命令历史 ──
    if cmdhist["has_history"]:
        lines.append(f"## 五、管理员命令历史")
        lines.append(f"")
        lines.append(f"共 {len(cmdhist['commands'])} 条命令记录。")
        lines.append(f"")

        if cmdhist["telnet_attempts"]:
            lines.append(f"**telnet 尝试记录：**")
            lines.append(f"```")
            for c in cmdhist["telnet_attempts"]:
                lines.append(c)
            lines.append(f"```")
            lines.append(f"")

        if cmdhist["suspicious_commands"]:
            lines.append(f"**⚠️ 注意：发现可能的危险操作：**")
            lines.append(f"```")
            for c in cmdhist["suspicious_commands"]:
                lines.append(c)
            lines.append(f"```")
            lines.append(f"")

    # ── 日志文件地图 ──
    lines.append(f"## 六、日志文件导航地图")
    lines.append(f"")
    lines.append(f"以下是主要日志文件的位置说明，便于手动深入排查：")
    lines.append(f"")
    lines.append(f"| 查找内容 | 文件路径 | 说明 |")
    lines.append(f"|---------|---------|------|")
    file_map = [
        ("BMC版本",     "RTOSDump/versioninfo/app_revision.txt",           "首要检查：版本号、编译时间"),
        ("IP地址",      "RTOSDump/networkinfo/ifconfig_info",               "网口IP、MAC、状态"),
        ("BMC网络配置", "AppDump/bmc_network/network_info.txt",             "IP模式、VLAN、防火墙规则"),
        ("串口配置",    "AppDump/bmc_network/network_info.txt",             "⚠️ telnet串口配置在此"),
        ("错误日志",    "LogDump/app.log",                                  "应用层ERROR日志"),
        ("操作日志",    "LogDump/operation.log",                            "用户操作审计（含串口操作）"),
        ("告警日志",    "LogDump/alarm.log",                                "告警事件记录"),
        ("内核日志",    "RTOSDump/driver_info/dmesg_info",                  "驱动错误、内核崩溃"),
        ("服务状态",    "RTOSDump/sysinfo/journalctl.log",                  "systemd服务启动/停止"),
        ("进程状态",    "RTOSDump/sysinfo/ps_info",                         "当前运行进程"),
        ("命令历史",    "RTOSDump/other_info/command_records/*/ash_history", "管理员执行的命令"),
        ("维护日志",    "LogDump/maintenance.log",                          "周期性维护任务日志"),
        ("启动日志",    "AppDump/dfm/",                                     "BMC启动过程日志"),
        ("存储信息",    "LogDump/storage/",                                  "RAID/磁盘状态"),
    ]
    for item, path, desc in file_map:
        full = root / path
        exists = "✓" if (root / path.rstrip("/")).exists() else "✗"
        lines.append(f"| {item} | `{path}` | {exists} {desc} |")
    lines.append(f"")

    # ── 诊断建议 ──
    lines.append(f"## 七、综合诊断建议")
    lines.append(f"")

    suggestions = []

    # 串口问题
    if not serial["telnetd_running"] or serial["telnetd_service_state"] == "已停止(inactive)":
        suggestions.append({
            "level": "HIGH",
            "issue": "BMC 串口/telnet 服务未运行",
            "steps": [
                "登录 iBMC/openUBMC Web 界面",
                "进入：系统管理 → 串口配置",
                '确认"串口转发"或"SOL"功能已启用',
                "检查 telnet 端口（默认23）防火墙规则",
                "参考文件：AppDump/bmc_network/network_info.txt（查看防火墙规则）",
            ]
        })

    # 大量错误
    if errors["app_error_count"] > 100:
        top_mod = errors["app_errors_top"][0][0] if errors["app_errors_top"] else "未知"
        suggestions.append({
            "level": "MEDIUM",
            "issue": f"app.log 中存在大量 ERROR（{errors['app_error_count']} 条），主要来自模块：{top_mod}",
            "steps": [
                f"检查 LogDump/app.log，重点关注模块 '{top_mod}' 的错误",
                "查找最早的 ERROR 时间戳，定位问题发生时间点",
            ]
        })

    # dmesg 错误
    if errors["dmesg_errors"]:
        suggestions.append({
            "level": "MEDIUM",
            "issue": f"dmesg 中有 {len(errors['dmesg_errors'])} 条内核异常",
            "steps": [
                "检查 RTOSDump/driver_info/dmesg_info",
                "重点关注 'error'、'fail'、'panic' 等关键词",
            ]
        })

    if not suggestions:
        lines.append(f"未发现明显问题，建议进一步分析 `LogDump/app.log` 中的详细错误信息。")
    else:
        for i, s in enumerate(suggestions, 1):
            level_icon = "🔴" if s["level"] == "HIGH" else "🟡"
            lines.append(f"### {level_icon} 问题 {i}：{s['issue']}")
            lines.append(f"")
            lines.append(f"**排查步骤：**")
            for j, step in enumerate(s["steps"], 1):
                lines.append(f"{j}. {step}")
            lines.append(f"")

    lines.append(f"---")
    lines.append(f"_报告由 bmc_log_analyzer.py v1.0 自动生成_")

    return "\n".join(lines)


# ─── 6. 主程序 ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="OpenUBMC/iBMC 日志包分析工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""
        示例：
          # 分析解压后的目录
          python3 bmc_log_analyzer.py dump_info/

          # 分析 tar.gz 包（自动解压）
          python3 bmc_log_analyzer.py dump_info.tar.gz

          # 输出到文件
          python3 bmc_log_analyzer.py dump_info/ -o report.md

          # 只查看串口诊断
          python3 bmc_log_analyzer.py dump_info/ --check serial
        """)
    )
    parser.add_argument("path", help="日志包路径（.tar.gz 或解压后的目录）")
    parser.add_argument("-o", "--output", help="输出报告文件路径（默认打印到 stdout）")
    parser.add_argument("--check", choices=["all", "serial", "network", "errors", "version"],
                        default="all", help="检查范围（默认 all）")
    args = parser.parse_args()

    # 解压（如需要）
    base_path = extract_if_needed(args.path)

    # 找到 dump_info 根目录
    root = find_dump_root(base_path)
    if not root:
        print(f"[ERROR] 无法在 '{base_path}' 中找到有效的 BMC 日志目录结构", file=sys.stderr)
        print(f"[ERROR] 预期找到包含 RTOSDump/ 或 LogDump/ 的目录", file=sys.stderr)
        sys.exit(1)

    print(f"[INFO] 找到日志根目录: {root}", file=sys.stderr)
    pkg_name = Path(args.path).name

    # 生成报告
    report = generate_report(root, pkg_name)

    # 输出
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"[INFO] 报告已保存到: {args.output}", file=sys.stderr)
    else:
        print(report)


if __name__ == "__main__":
    main()
