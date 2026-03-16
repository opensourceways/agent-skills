#!/usr/bin/env python3
"""
BMC 日志分析 MCP Server
遵循 MCP (Model Context Protocol) 规范，为 Claude 提供 BMC 日志分析工具

使用方式：
  # 在 Claude Code 的 settings.json 中配置：
  {
    "mcpServers": {
      "bmc-log-analyzer": {
        "command": "python3",
        "args": ["/path/to/bmc_log_mcp_server.py"]
      }
    }
  }

可用工具：
  - analyze_log_package   : 全量分析日志包，返回摘要报告
  - get_version_info      : 获取 BMC 版本信息
  - get_network_info      : 获取网络配置
  - check_serial_config   : 专项检查串口/telnet 配置（帖子#4257 的核心问题）
  - search_errors         : 搜索错误日志
  - list_log_structure    : 列出日志包目录结构
  - read_log_file         : 读取指定日志文件内容
"""

import json
import sys
import os
import re
import gzip
from pathlib import Path


# ─── 复用分析库 ──────────────────────────────────────────────────────────────

# 在同一目录下导入分析模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bmc_log_analyzer import (
    find_dump_root,
    analyze_version,
    analyze_network,
    analyze_serial_config,
    analyze_errors,
    generate_report,
    read_file_safe,
    KEY_FILES,
)


# ─── MCP 协议实现（stdio 模式）───────────────────────────────────────────────

def send_response(response: dict):
    """向 stdout 发送 JSON-RPC 响应"""
    line = json.dumps(response, ensure_ascii=False)
    sys.stdout.write(line + "\n")
    sys.stdout.flush()


def send_error(req_id, code: int, message: str):
    send_response({
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {"code": code, "message": message}
    })


def send_result(req_id, result):
    send_response({
        "jsonrpc": "2.0",
        "id": req_id,
        "result": result
    })


# ─── 工具定义 ────────────────────────────────────────────────────────────────

TOOLS = [
    {
        "name": "analyze_log_package",
        "description": (
            "全量分析 OpenUBMC/iBMC 日志包，生成结构化 Markdown 摘要报告。\n"
            "报告包含：BMC版本、IP地址、串口配置状态、错误日志统计、诊断建议。\n"
            "适用于：用户上传日志包后的首次快速分析。"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "日志包路径：可以是 .tar.gz 文件或已解压的目录路径"
                }
            },
            "required": ["path"]
        }
    },
    {
        "name": "get_version_info",
        "description": "获取 BMC 版本信息，包括活跃版本号、备份版本号、产品型号、BIOS版本等。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "日志包路径"}
            },
            "required": ["path"]
        }
    },
    {
        "name": "get_network_info",
        "description": "获取网络配置信息，包括IP地址、网口状态、活跃端口、防火墙规则数量。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "日志包路径"}
            },
            "required": ["path"]
        }
    },
    {
        "name": "check_serial_config",
        "description": (
            "专项检查 BMC 串口和 telnet 配置。\n"
            "这是 OpenUBMC 论坛帖子 #4257 中发现的典型故障场景：\n"
            "用户反馈 BMC 无法通过 telnet 登录，根因是串口服务未配置或未启动。\n"
            "该工具会检查：telnetd 进程状态、systemd 服务状态、操作日志中的串口操作记录。"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "日志包路径"}
            },
            "required": ["path"]
        }
    },
    {
        "name": "search_errors",
        "description": "在日志包中搜索错误信息，支持关键词过滤和日志类型选择。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "日志包路径"},
                "keyword": {
                    "type": "string",
                    "description": "搜索关键词（可选，不填则搜索所有ERROR）",
                    "default": ""
                },
                "log_type": {
                    "type": "string",
                    "description": "日志类型：app、maintenance、dmesg、operation、all",
                    "enum": ["app", "maintenance", "dmesg", "operation", "all"],
                    "default": "all"
                },
                "max_results": {
                    "type": "integer",
                    "description": "最多返回条数",
                    "default": 50
                }
            },
            "required": ["path"]
        }
    },
    {
        "name": "list_log_structure",
        "description": (
            "列出日志包的目录结构，并标注每个关键文件的用途。\n"
            "帮助用户理解'哪个目录放哪类日志'。"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "日志包路径"},
                "depth": {
                    "type": "integer",
                    "description": "目录树显示深度（默认3层）",
                    "default": 3
                }
            },
            "required": ["path"]
        }
    },
    {
        "name": "read_log_file",
        "description": (
            "读取日志包中指定文件的内容。\n"
            "支持读取 .gz 压缩文件。可指定读取行数范围。"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "日志包路径"},
                "file_path": {
                    "type": "string",
                    "description": "要读取的文件路径（相对于 dump_info/ 根目录）"
                },
                "head": {
                    "type": "integer",
                    "description": "读取前N行（0表示全部）",
                    "default": 100
                },
                "grep": {
                    "type": "string",
                    "description": "过滤关键词（可选）",
                    "default": ""
                }
            },
            "required": ["path", "file_path"]
        }
    }
]


# ─── 工具实现 ────────────────────────────────────────────────────────────────

def _get_root(path_str: str) -> Path:
    """获取日志根目录"""
    from bmc_log_analyzer import extract_if_needed
    base = extract_if_needed(path_str)
    root = find_dump_root(base)
    if not root:
        raise ValueError(f"无法在 '{path_str}' 中找到有效的 BMC 日志结构（缺少 RTOSDump/ 或 LogDump/）")
    return root


def tool_analyze_log_package(params: dict) -> str:
    path = params["path"]
    root = _get_root(path)
    report = generate_report(root, Path(path).name)
    return report


def tool_get_version_info(params: dict) -> str:
    root = _get_root(params["path"])
    ver = analyze_version(root)
    lines = [
        f"## BMC 版本信息",
        f"",
        f"- **BMC类型**: {ver['bmc_type']}",
        f"- **活跃版本**: {ver['bmc_version']} (Build {ver['bmc_build']})",
        f"- **编译时间**: {ver['bmc_built']}",
        f"- **备份版本**: {ver['backup_version']}",
        f"- **产品型号**: {ver['product_name']}",
        f"- **BIOS版本**: {ver['bios_version']}",
        f"",
        f"**原始内容（app_revision.txt 前30行）：**",
        f"```",
        ver["raw"][:1500],
        f"```",
    ]
    return "\n".join(lines)


def tool_get_network_info(params: dict) -> str:
    root = _get_root(params["path"])
    net = analyze_network(root)
    lines = [
        f"## 网络配置信息",
        f"",
        f"- **BMC IP**: {net['bmc_ip']}",
        f"- **活跃端口**: {net['active_port']}",
        f"- **网络模式**: {net['net_mode']}",
        f"- **telnet端口(23)监听**: {'是' if net.get('telnet_port_open') else '否'}",
        f"- **防火墙规则数**: {net['firewall_rules_count']}",
        f"",
        f"**网络接口：**",
    ]
    for iface in net["interfaces"]:
        lines.append(f"- {iface['name']}: IP={iface.get('ip', '-')}  MAC={iface.get('mac', '-')}  状态={iface.get('state', '-')}")
    if net["listening_ports"]:
        lines.append(f"")
        lines.append(f"**监听端口**: {sorted(net['listening_ports'])}")
    return "\n".join(lines)


def tool_check_serial_config(params: dict) -> str:
    root = _get_root(params["path"])
    serial = analyze_serial_config(root)
    lines = [
        f"## 串口/Telnet 配置检查",
        f"",
        f"### 状态汇总",
        f"",
        f"| 检查项 | 结果 |",
        f"|-------|------|",
        f"| telnetd 进程 | {'✓ 运行中' if serial['telnetd_running'] else '✗ 未运行'} |",
        f"| systemd 服务状态 | {serial['telnetd_service_state']} |",
        f"",
        f"### 诊断结论",
        f"",
    ]
    for d in serial["diagnosis"]:
        lines.append(f"- {d}")

    if serial["telnetd_process"]:
        lines.append(f"")
        lines.append(f"### telnetd 进程详情")
        lines.append(f"```")
        lines.append(serial["telnetd_process"])
        lines.append(f"```")

    if serial["serial_operations"]:
        lines.append(f"")
        lines.append(f"### 操作日志：串口相关操作（最近5条）")
        lines.append(f"```")
        for op in serial["serial_operations"][-5:]:
            lines.append(op[:300])
        lines.append(f"```")

    if hasattr(serial, "get") and serial.get("telnetd_last_event"):
        lines.append(f"")
        lines.append(f"### systemd 最后一条 telnetd 事件")
        lines.append(f"```")
        lines.append(serial.get("telnetd_last_event", ""))
        lines.append(f"```")

    lines.append(f"")
    lines.append(f"### 相关文件")
    lines.append(f"- `AppDump/bmc_network/network_info.txt` - BMC 网络及串口配置")
    lines.append(f"- `RTOSDump/networkinfo/netstat_info` - 端口监听状态")
    lines.append(f"- `RTOSDump/sysinfo/journalctl.log` - 服务启停记录")
    lines.append(f"- `LogDump/operation.log` - 用户操作审计（含串口操作）")

    return "\n".join(lines)


def tool_search_errors(params: dict) -> str:
    root = _get_root(params["path"])
    keyword = params.get("keyword", "")
    log_type = params.get("log_type", "all")
    max_results = params.get("max_results", 50)

    # 确定要搜索的日志文件
    log_targets = {
        "app": [("LogDump/app.log", "app.log")],
        "maintenance": [("LogDump/maintenance.log", "maintenance.log")],
        "dmesg": [("RTOSDump/driver_info/dmesg_info", "dmesg")],
        "operation": [("LogDump/operation.log", "operation.log")],
        "all": [
            ("LogDump/app.log", "app.log"),
            ("LogDump/maintenance.log", "maintenance.log"),
            ("RTOSDump/driver_info/dmesg_info", "dmesg"),
            ("LogDump/operation.log", "operation.log"),
            ("RTOSDump/sysinfo/journalctl.log", "journalctl"),
        ]
    }
    targets = log_targets.get(log_type, log_targets["all"])

    results = []
    for rel_path, label in targets:
        full_path = root / rel_path
        if not full_path.exists():
            continue
        content = read_file_safe(full_path)
        for i, line in enumerate(content.split("\n"), 1):
            # 错误行过滤
            is_error = any(kw in line for kw in ["ERROR", "FATAL", "error:", "WARN"])
            # 关键词过滤
            if keyword:
                if keyword.lower() not in line.lower():
                    continue
            elif not is_error:
                continue

            results.append(f"[{label}:{i}] {line.strip()}")
            if len(results) >= max_results:
                break
        if len(results) >= max_results:
            break

    lines = [
        f"## 错误日志搜索结果",
        f"",
        f"- **关键词**: {keyword or '(所有ERROR)'}",
        f"- **日志范围**: {log_type}",
        f"- **找到**: {len(results)} 条（最多显示 {max_results} 条）",
        f"",
        f"```",
    ]
    lines.extend(results[:max_results])
    lines.append(f"```")
    return "\n".join(lines)


def tool_list_log_structure(params: dict) -> str:
    root = _get_root(params["path"])
    max_depth = params.get("depth", 3)

    # 关键目录说明
    dir_descriptions = {
        "RTOSDump": "操作系统层信息（网络、驱动、系统状态）",
        "RTOSDump/versioninfo": "版本信息（★首要检查）",
        "RTOSDump/networkinfo": "网络接口信息（IP、路由、防火墙）",
        "RTOSDump/driver_info": "内核驱动信息（dmesg）",
        "RTOSDump/sysinfo": "系统状态（内存、进程、journalctl）",
        "RTOSDump/other_info": "其他配置（SSH、NTP、命令历史）",
        "LogDump": "应用层日志（★核心日志目录）",
        "AppDump": "各子系统专项Dump",
        "AppDump/bmc_network": "BMC网络配置（★串口配置在此）",
        "AppDump/fault_diagnosis": "故障诊断数据",
        "AppDump/bmc_health": "BMC健康状态",
        "AppDump/sensor": "传感器数据",
        "AppDump/power_mgmt": "电源管理",
        "AppDump/cooling": "风扇/温控",
        "CoreDump": "进程崩溃coredump文件",
        "BMALogDump": "BMA（主机侧BMC代理）日志",
        "OSDump": "主机OS信息",
    }

    # 文件说明
    file_descriptions = {
        "app_revision.txt": "★ BMC版本号（首要查看）",
        "ifconfig_info": "★ 网口IP地址",
        "network_info.txt": "★ BMC网络和串口配置",
        "app.log": "★ 应用层错误日志（默认ERROR级）",
        "operation.log": "用户操作审计日志",
        "alarm.log": "告警事件日志",
        "maintenance.log": "维护任务日志",
        "dmesg_info": "内核日志（驱动错误）",
        "journalctl.log": "systemd服务日志",
        "ash_history": "管理员命令历史",
        "sshd_config": "SSH配置",
        "netstat_info": "端口监听状态",
        "ps_info": "当前进程列表",
    }

    def tree(path: Path, prefix: str = "", depth: int = 0) -> list:
        if depth > max_depth:
            return []
        lines = []
        try:
            items = sorted(path.iterdir(), key=lambda x: (x.is_file(), x.name))
        except PermissionError:
            return []

        for i, item in enumerate(items):
            is_last = (i == len(items) - 1)
            connector = "└── " if is_last else "├── "
            ext = "  " if is_last else "│ "

            # 获取说明
            rel = str(item.relative_to(root))
            desc = ""
            if item.is_dir():
                desc = dir_descriptions.get(rel, "")
            else:
                desc = file_descriptions.get(item.name, "")

            desc_str = f"  ← {desc}" if desc else ""
            lines.append(f"{prefix}{connector}{item.name}{desc_str}")

            if item.is_dir() and depth < max_depth:
                lines.extend(tree(item, prefix + ext + " ", depth + 1))
        return lines

    result_lines = [
        f"## 日志包目录结构",
        f"",
        f"根目录: `{root}`",
        f"",
        f"```",
        f"dump_info/",
    ]
    result_lines.extend(tree(root))
    result_lines.append(f"```")
    result_lines.append(f"")
    result_lines.append(f"## 关键文件快速参考")
    result_lines.append(f"")
    result_lines.append(f"| 查找什么 | 文件 |")
    result_lines.append(f"|---------|------|")
    key_refs = [
        ("BMC版本", "RTOSDump/versioninfo/app_revision.txt"),
        ("BMC IP地址", "RTOSDump/networkinfo/ifconfig_info"),
        ("串口/telnet配置", "AppDump/bmc_network/network_info.txt"),
        ("应用错误日志", "LogDump/app.log"),
        ("操作审计", "LogDump/operation.log"),
        ("内核错误", "RTOSDump/driver_info/dmesg_info"),
        ("服务状态", "RTOSDump/sysinfo/journalctl.log"),
        ("进程列表", "RTOSDump/sysinfo/ps_info"),
        ("命令历史", "RTOSDump/other_info/command_records/Administrator/ash_history"),
    ]
    for what, where in key_refs:
        exists = "✓" if (root / where).exists() else "✗"
        result_lines.append(f"| {what} | `{where}` {exists} |")

    return "\n".join(result_lines)


def tool_read_log_file(params: dict) -> str:
    root = _get_root(params["path"])
    file_path = params["file_path"]
    head = params.get("head", 100)
    grep_kw = params.get("grep", "")

    full_path = root / file_path
    if not full_path.exists():
        return f"文件不存在: `{file_path}`\n\n根目录: {root}"

    content = read_file_safe(full_path, max_bytes=500000)
    lines_all = content.split("\n")

    # 关键词过滤
    if grep_kw:
        filtered = [l for l in lines_all if grep_kw.lower() in l.lower()]
    else:
        filtered = lines_all

    # head 截取
    if head > 0:
        display = filtered[:head]
        truncated = len(filtered) > head
    else:
        display = filtered
        truncated = False

    result = [
        f"## 文件内容：`{file_path}`",
        f"",
        f"- **文件大小**: {full_path.stat().st_size} bytes",
        f"- **总行数**: {len(lines_all)}",
    ]
    if grep_kw:
        result.append(f"- **过滤关键词**: `{grep_kw}`，匹配 {len(filtered)} 行")
    if truncated:
        result.append(f"- **显示**: 前 {head} 行（共 {len(filtered)} 行）")
    result.append(f"")
    result.append(f"```")
    result.extend(display)
    result.append(f"```")

    return "\n".join(result)


# ─── 工具路由 ────────────────────────────────────────────────────────────────

TOOL_HANDLERS = {
    "analyze_log_package": tool_analyze_log_package,
    "get_version_info": tool_get_version_info,
    "get_network_info": tool_get_network_info,
    "check_serial_config": tool_check_serial_config,
    "search_errors": tool_search_errors,
    "list_log_structure": tool_list_log_structure,
    "read_log_file": tool_read_log_file,
}


# ─── MCP 主循环 ──────────────────────────────────────────────────────────────

def handle_request(request: dict):
    req_id = request.get("id")
    method = request.get("method", "")
    params = request.get("params", {})

    # 初始化握手
    if method == "initialize":
        send_result(req_id, {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": {
                "name": "bmc-log-analyzer",
                "version": "1.0.0"
            }
        })
        return

    if method == "notifications/initialized":
        return  # 无需响应

    # 列举工具
    if method == "tools/list":
        send_result(req_id, {"tools": TOOLS})
        return

    # 调用工具
    if method == "tools/call":
        tool_name = params.get("name", "")
        tool_params = params.get("arguments", {})

        handler = TOOL_HANDLERS.get(tool_name)
        if not handler:
            send_error(req_id, -32601, f"未知工具: {tool_name}")
            return

        try:
            result_text = handler(tool_params)
            send_result(req_id, {
                "content": [
                    {"type": "text", "text": result_text}
                ]
            })
        except Exception as e:
            send_result(req_id, {
                "content": [
                    {"type": "text", "text": f"工具执行错误: {str(e)}"}
                ],
                "isError": True
            })
        return

    send_error(req_id, -32601, f"未知方法: {method}")


def main():
    """MCP Server 主循环（stdio 模式）"""
    print(f"BMC Log Analyzer MCP Server 已启动 (stdio 模式)", file=sys.stderr)

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError as e:
            send_response({
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": f"JSON 解析错误: {e}"}
            })
            continue

        try:
            handle_request(request)
        except Exception as e:
            req_id = request.get("id")
            send_error(req_id, -32603, f"内部错误: {str(e)}")


if __name__ == "__main__":
    main()
