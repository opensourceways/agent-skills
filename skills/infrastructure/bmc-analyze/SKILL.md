# bmc-analyze — OpenUBMC/iBMC 日志包故障诊断

分析 OpenUBMC/iBMC 的 dump_info 日志包，生成结构化故障诊断报告。用法：`/bmc-analyze [日志包路径]`，支持 .tar.gz 文件或目录。

# 示例：
#   /bmc-analyze dump_info.tar.gz
#   /bmc-analyze /path/to/dump_info/

Analyze the BMC log package at the path provided by the user (or use the current directory if no path given).

Follow these steps:

## Step 1: Find the log package

If the user provided a path, use it directly. Otherwise, look for:
- Files matching `*.tar.gz` in the current directory
- Directories named `dump_info*` or `null_*` in the current directory

## Step 2: Run the analyzer script

Use the Bash tool to run:
```bash
python3 /home/zhongjun/claude/zhongjun2/openUBMC_forum/bmc_log_analyzer.py <PATH> 2>&1
```

If no analyzer script is available, perform the analysis manually:

### Manual Analysis Checklist

**A. Version Info** - Read `RTOSDump/versioninfo/app_revision.txt`
- Look for: `Active iBMC Version:` or `Active openUBMC Version:`

**B. Network Config** - Read `RTOSDump/networkinfo/ifconfig_info`
- Look for: IP addresses, UP/DOWN interface states

**C. Serial/Telnet Config** - Read these files:
- `RTOSDump/sysinfo/ps_info` or `top_info` → grep for "telnetd"
- `RTOSDump/sysinfo/journalctl.log*` → grep for "telnetd"
- `LogDump/operation.log` → grep for "serial" or "SOL"
- `AppDump/bmc_network/network_info.txt` → check port 23 rules

**D. Error Logs** - Read `LogDump/app.log`
- Count ERROR lines, identify top modules

**E. Command History** - Read `RTOSDump/other_info/command_records/*/ash_history`

## Step 3: Present the report

Format the findings as a structured report with:
1. **Basic Info**: BMC type, version, product model
2. **Network Status**: IP addresses, interface states
3. **Serial/Telnet Status** (⚠️ PRIORITY): Is telnetd running? Is systemd service active?
4. **Error Summary**: ERROR count, top modules, critical errors
5. **Diagnosis & Recommendations**: Specific actionable steps

## Key Log File Map (tell the user which file to check for what)

| What to find | File path |
|---|---|
| BMC version | `RTOSDump/versioninfo/app_revision.txt` |
| IP address | `RTOSDump/networkinfo/ifconfig_info` |
| Serial/telnet config | `AppDump/bmc_network/network_info.txt` |
| App error logs | `LogDump/app.log` |
| Operation audit | `LogDump/operation.log` |
| Kernel errors | `RTOSDump/driver_info/dmesg_info` |
| Service status | `RTOSDump/sysinfo/journalctl.log` |
| Process list | `RTOSDump/sysinfo/ps_info` |
| Admin history | `RTOSDump/other_info/command_records/*/ash_history` |

## Serial Port Troubleshooting (for forum post #4257 type issues)

If user reports "cannot connect via telnet to BMC serial port":

1. Check `RTOSDump/sysinfo/ps_info` - is `telnetd` in process list?
2. Check `RTOSDump/sysinfo/journalctl.log*` - was telnetd.service deactivated?
3. Check `LogDump/operation.log` - look for "SOL session" failures
4. Check `AppDump/bmc_network/network_info.txt` - firewall rules for port 23

If telnetd service is stopped: recommend enabling serial forwarding via iBMC/openUBMC web interface → System Management → Serial Port Config.
