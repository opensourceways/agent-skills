# GitHub Action CI 诊断 Skill

> 专为昇腾（Ascend）NPU 集群（ARC/K8s）基础设施设计的 CI 故障自动诊断工具。

## 功能

- 自动收集失败 CI 的日志、Annotations、PR 变更等信息
- 通过 AI（Qwen3.6-Plus）分析根因，分类故障类型
- 支持查询 LTS 集群日志（MCP），获取 Runner Pod 完整日志
- 输出结构化诊断报告（定性、根因、责任方、建议）
- 支持单条诊断和批量诊断

## 快速开始

### 前置要求

- Python 3.12+
- `gh` CLI（已登录并认证）
- 百炼 API Key（用于调用 Qwen 模型）
- GitHub Token（用于调用 GitHub API）

### 安装依赖

```bash
pip install requests openpyxl openai
```

### 1. 收集失败的 CI

```bash
# 收集过去 12 小时，排除 lint 相关
python scripts/collect_failed_runs.py --hours 12 --exclude-jobs lint --token <github_token>

# 收集指定日期范围
python scripts/collect_failed_runs.py --from 2026-04-20 --to 2026-04-20 --exclude-jobs lint --token <github_token>
```

输出：`Fail_CI_Problem/failed-runs-YYYY-MM-DD.xlsx`

### 2. 诊断单个 Job

```bash
python scripts/diagnose_job.py --url "https://github.com/vllm-project/vllm-ascend/actions/runs/xxx/job/yyy" --api-key <dashscope_api_key>
```

### 3. 批量诊断

```bash
python scripts/batch_diagnose.py --input Fail_CI_Problem/failed-runs-2026-04-20.xlsx --api-key <dashscope_api_key>

# 只诊断前 N 条（测试用）
python scripts/batch_diagnose.py --input Fail_CI_Problem/failed-runs-2026-04-20.xlsx --api-key <dashscope_api_key> --limit 5
```

结果写回 xlsx 文件的"诊断结果"列，支持断点续传。

## 工具列表

### GitHub 数据获取（6 个）

| 工具 | 用途 |
|------|------|
| `fetch_run_script` | 运行 `fetch_run.py` 脚本，一次性获取 Job 信息、Annotations、预过滤日志 |
| `fetch_job_info` | 获取 Job 元数据（名称、Runner、失败步骤） |
| `fetch_job_logs` | 获取 GitHub Actions 日志（按关键词过滤） |
| `fetch_annotations` | 获取 GitHub Annotations（通常直接揭示根因） |
| `fetch_run_info` | 获取 Run 元数据（PR、分支、工作流名称） |
| `fetch_pr_diff` | 获取 PR 变更文件列表 |

### MCP 集群日志查询（4 个）

| 工具 | 用途 |
|------|------|
| `mcp_get_runner_logs` | **一键获取 Runner Pod 日志**（自动查找 Pod → 导出 → 下载） |
| `mcp_list_pods` | 列出集群中的 Pod |
| `mcp_export_logs` | 创建日志导出任务 |
| `mcp_get_export` | 查询导出结果 |

### 通用工具（5 个）

| 工具 | 用途 |
|------|------|
| `bash_execute` | 执行任意 shell 命令 |
| `read_file` | 读取本地文件 |
| `grep_file` | 搜索文件内容 |
| `glob_file` | 按模式查找文件 |
| `write_file` | 写入文件 |

## 诊断流程

```
用户输入 Job URL
    ↓
Step 1: fetch_run_script → 获取 GitHub 日志、Annotations、PR 信息
    ↓
AI 分析：信息够吗？
    ├─ 够 → 直接输出诊断报告
    └─ 不够 → 调用 mcp_get_runner_logs 获取集群日志
         ↓
    AI 分析集群日志
         ↓
    输出最终诊断报告
```

## 故障分类

| 类型 | 说明 | 责任方 |
|------|------|--------|
| A | 基础设施/环境故障（网络超时、NPU 硬件、OOM、K8s 调度） | 基础设施团队 |
| B | 代码 Bug（PR 引入的异常） | PR 作者 |
| C | 精度回归 | PR 作者 |
| D | YAML/配置错误 | PR 作者/CI 维护者 |
| E | 疑难/概率性问题 | 需进一步排查 |

## MCP 配置

MCP 服务地址：`http://150.158.143.223:30089/mcp`
默认日志源：`ascend-ci-log`
默认 namespace：`vllm-project`

## 文件结构

```
scripts/
├── collect_failed_runs.py   # 收集失败 CI，输出 xlsx
├── diagnose_job.py          # 单条诊断脚本（AI agentic loop）
├── batch_diagnose.py        # 批量诊断脚本（从 xlsx 读取，结果写回）
├── fetch_run.py             # 获取 Job 日志和元数据（Python 版）
├── fetch-run.sh             # 获取 Job 日志和元数据（Bash 版）
├── mcp_client.py            # MCP 客户端封装
```

## 费用估算

| 指标 | 数值 |
|------|------|
| 单条 Token 消耗 | ~1-3 万 |
| 单条费用 | ~¥0.02-0.06 |
| 100 条费用 | ~¥2-6 |

定价：Qwen3.6-Plus 输入 2 元/百万 Token，输出 12 元/百万 Token。
