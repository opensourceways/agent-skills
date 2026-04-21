#!/usr/bin/env python3
"""
diagnose_job.py - 通过百炼 API 调用 Qwen3.6-Plus，使用 SKILL 引擎诊断失败的 CI Job

用法:
  python diagnose_job.py --url "https://github.com/owner/repo/actions/runs/xxx/job/yyy"
  python diagnose_job.py --url "https://github.com/owner/repo/actions/runs/xxx/job/yyy" --skill-dir /path/to/skill

依赖:
  pip install dashscope openai
  gh CLI 已安装并认证
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import io
from pathlib import Path
from typing import Optional

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")


SKILL_DIR = Path(__file__).parent.parent  # scripts 的父目录即 skill 根目录
SKILL_FILES = {
    "SKILL.md": "SKILL.md",
    "references/common-patterns.md": "references/common-patterns.md",
    "references/vllm-ascend.md": "references/vllm-ascend.md",
    "references/classification-guide.md": "references/classification-guide.md",
    "references/ascend-troubleshooting.md": "references/ascend-troubleshooting.md",
}

BASH_EXECUTE = {
    "type": "function",
    "function": {
        "name": "bash_execute",
        "description": "Execute a bash command and return its stdout and stderr. Use this to run scripts, fetch logs, query kubectl, etc.",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The bash command to execute",
                }
            },
            "required": ["command"],
        },
    },
}

READ_FILE = {
    "type": "function",
    "function": {
        "name": "read_file",
        "description": "Read the content of a file. Use this to read reference files, scripts, or templates.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Absolute or relative path to the file",
                }
            },
            "required": ["path"],
        },
    },
}

GREP_FILE = {
    "type": "function",
    "function": {
        "name": "grep_file",
        "description": "Search for a pattern in file contents. Returns matching lines with file paths and line numbers.",
        "parameters": {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Regex pattern to search for",
                },
                "path": {
                    "type": "string",
                    "description": "Directory or file to search in (default: current directory)",
                },
                "include": {
                    "type": "string",
                    "description": "File pattern to include (e.g. '*.md', '*.sh')",
                },
            },
            "required": ["pattern"],
        },
    },
}

GLOB_FILE = {
    "type": "function",
    "function": {
        "name": "glob_file",
        "description": "Find files matching a glob pattern. Returns list of matching file paths.",
        "parameters": {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Glob pattern (e.g. '*.md', 'scripts/*.sh')",
                },
                "path": {
                    "type": "string",
                    "description": "Directory to search in (default: current directory)",
                },
            },
            "required": ["pattern"],
        },
    },
}

WRITE_FILE = {
    "type": "function",
    "function": {
        "name": "write_file",
        "description": "Write content to a file. Use this to create reports, action plans, or temporary files.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file to write",
                },
                "content": {
                    "type": "string",
                    "description": "Content to write to the file",
                },
            },
            "required": ["path", "content"],
        },
    },
}

FETCH_RUN_SCRIPT = {
    "type": "function",
    "function": {
        "name": "fetch_run_script",
        "description": "Run the fetch_run.py script to collect job metadata, annotations, and filtered logs. This is the PRIMARY tool for gathering CI failure data. It outputs: job info, runner name, failed steps, annotations, and pre-filtered error lines. ALWAYS use this FIRST before any other data collection.",
        "parameters": {
            "type": "object",
            "properties": {
                "repo": {
                    "type": "string",
                    "description": "Owner/repo, e.g. vllm-project/vllm-ascend",
                },
                "job_id": {"type": "string", "description": "GitHub Job ID"},
            },
            "required": ["repo", "job_id"],
        },
    },
}

FETCH_JOB_INFO = {
    "type": "function",
    "function": {
        "name": "fetch_job_info",
        "description": "Fetch job metadata including name, conclusion, runner_name, started_at, completed_at, run_id, and steps. Use this FIRST to understand the job before fetching logs.",
        "parameters": {
            "type": "object",
            "properties": {
                "repo": {
                    "type": "string",
                    "description": "Owner/repo, e.g. vllm-project/vllm-ascend",
                },
                "job_id": {"type": "string", "description": "GitHub Job ID"},
            },
            "required": ["repo", "job_id"],
        },
    },
}

FETCH_JOB_LOGS = {
    "type": "function",
    "function": {
        "name": "fetch_job_logs",
        "description": "Fetch filtered job logs. Returns only key error lines (RuntimeError, AssertionError, exit code, ETIMEDOUT, OOM, etc.) to avoid overwhelming output. Use this instead of raw log fetch.",
        "parameters": {
            "type": "object",
            "properties": {
                "repo": {
                    "type": "string",
                    "description": "Owner/repo, e.g. vllm-project/vllm-ascend",
                },
                "job_id": {"type": "string", "description": "GitHub Job ID"},
                "filter_type": {
                    "type": "string",
                    "enum": [
                        "runtime_errors",
                        "compile_errors",
                        "upload_errors",
                        "network_errors",
                        "all_errors",
                    ],
                    "description": "Type of errors to filter for",
                },
            },
            "required": ["repo", "job_id"],
        },
    },
}

FETCH_ANNOTATIONS = {
    "type": "function",
    "function": {
        "name": "fetch_annotations",
        "description": "Fetch GitHub check-run annotations for a job. Often directly reveals root cause (ETIMEDOUT, exit code, etc.). Check this BEFORE fetching logs.",
        "parameters": {
            "type": "object",
            "properties": {
                "repo": {
                    "type": "string",
                    "description": "Owner/repo, e.g. vllm-project/vllm-ascend",
                },
                "job_id": {"type": "string", "description": "GitHub Job ID"},
            },
            "required": ["repo", "job_id"],
        },
    },
}

FETCH_RUN_INFO = {
    "type": "function",
    "function": {
        "name": "fetch_run_info",
        "description": "Fetch workflow run metadata including PR number, branch, display_title, and all job statuses. Use to understand run context and PR changes.",
        "parameters": {
            "type": "object",
            "properties": {
                "repo": {
                    "type": "string",
                    "description": "Owner/repo, e.g. vllm-project/vllm-ascend",
                },
                "run_id": {"type": "string", "description": "GitHub Run ID"},
            },
            "required": ["repo", "run_id"],
        },
    },
}

FETCH_PR_DIFF = {
    "type": "function",
    "function": {
        "name": "fetch_pr_diff",
        "description": "Fetch list of changed files in a PR. Use for classification (code bug vs infrastructure).",
        "parameters": {
            "type": "object",
            "properties": {
                "repo": {
                    "type": "string",
                    "description": "Owner/repo, e.g. vllm-project/vllm-ascend",
                },
                "pr_number": {"type": "string", "description": "PR number"},
            },
            "required": ["repo", "pr_number"],
        },
    },
}

MCP_LIST_PODS = {
    "type": "function",
    "function": {
        "name": "mcp_list_pods",
        "description": "通过 LTS 日志服务查询集群中的 Pod 列表。用于定位 Runner Pod 或查找相关 Pod 名称。需要 source、namespace 和时间范围。",
        "parameters": {
            "type": "object",
            "properties": {
                "namespace": {
                    "type": "string",
                    "description": "Kubernetes namespace，如 vllm-project",
                },
                "start": {
                    "type": "string",
                    "description": "开始时间，格式 YYYY-MM-DD HH:MM:SS",
                },
                "end": {
                    "type": "string",
                    "description": "结束时间，格式 YYYY-MM-DD HH:MM:SS",
                },
                "source": {
                    "type": "string",
                    "description": "LTS 日志源（默认 ascend-ci-log）",
                },
            },
            "required": ["namespace", "start", "end"],
        },
    },
}

MCP_EXPORT_LOGS = {
    "type": "function",
    "function": {
        "name": "mcp_export_logs",
        "description": "创建日志导出任务，按 Pod 名称和关键词过滤。返回 export_id 用于后续查询结果。",
        "parameters": {
            "type": "object",
            "properties": {
                "namespace": {"type": "string", "description": "Kubernetes namespace"},
                "pod_name": {
                    "type": "string",
                    "description": "Pod 名称（支持模糊匹配）",
                },
                "keywords": {
                    "type": "string",
                    "description": "搜索关键词，如 RuntimeError|ETIMEDOUT|OOM",
                },
                "start": {
                    "type": "string",
                    "description": "开始时间，格式 YYYY-MM-DD HH:MM:SS",
                },
                "end": {
                    "type": "string",
                    "description": "结束时间，格式 YYYY-MM-DD HH:MM:SS",
                },
                "source": {
                    "type": "string",
                    "description": "LTS 日志源（默认 ascend-ci-log）",
                },
            },
            "required": ["namespace", "pod_name", "start", "end"],
        },
    },
}

MCP_GET_EXPORT = {
    "type": "function",
    "function": {
        "name": "mcp_get_export",
        "description": "查询日志导出任务的结果。传入 export_id 获取日志内容或下载链接。",
        "parameters": {
            "type": "object",
            "properties": {
                "export_id": {"type": "string", "description": "导出任务 ID"},
            },
            "required": ["export_id"],
        },
    },
}

MCP_GET_RUNNER_LOGS = {
    "type": "function",
    "function": {
        "name": "mcp_get_runner_logs",
        "description": "一键获取 Runner Pod 的日志。自动完成查找 Pod → 导出 → 下载全流程。只需提供 Runner 名称和时间范围。",
        "parameters": {
            "type": "object",
            "properties": {
                "runner_name": {
                    "type": "string",
                    "description": "Runner 名称，如 linux-aarch64-a3-0-ggwx6-runner-qbq72",
                },
                "namespace": {
                    "type": "string",
                    "description": "Kubernetes namespace（默认 vllm-project）",
                },
                "start": {
                    "type": "string",
                    "description": "开始时间，格式 YYYY-MM-DD HH:MM:SS",
                },
                "end": {
                    "type": "string",
                    "description": "结束时间，格式 YYYY-MM-DD HH:MM:SS",
                },
                "keywords": {"type": "string", "description": "搜索关键词（可选）"},
            },
            "required": ["runner_name", "start", "end"],
        },
    },
}

TOOLS = [
    FETCH_RUN_SCRIPT,
    MCP_GET_RUNNER_LOGS,
    MCP_LIST_PODS,
    MCP_EXPORT_LOGS,
    MCP_GET_EXPORT,
    FETCH_JOB_INFO,
    FETCH_JOB_LOGS,
    FETCH_ANNOTATIONS,
    FETCH_RUN_INFO,
    FETCH_PR_DIFF,
    BASH_EXECUTE,
    READ_FILE,
    GREP_FILE,
    GLOB_FILE,
    WRITE_FILE,
]


def parse_args():
    parser = argparse.ArgumentParser(description="诊断失败的 CI Job")
    parser.add_argument(
        "--url",
        required=True,
        help="GitHub Job URL，如 https://github.com/owner/repo/actions/runs/xxx/job/yyy",
    )
    parser.add_argument(
        "--skill-dir",
        default=str(SKILL_DIR),
        help="Skill 目录路径（包含 SKILL.md 和 references/）",
    )
    parser.add_argument(
        "--api-key",
        default=os.environ.get("DASHSCOPE_API_KEY", ""),
        help="百炼 API Key",
    )
    parser.add_argument(
        "--model",
        default="qwen3.6-plus",
        help="模型名称（默认 qwen3.6-plus）",
    )
    parser.add_argument(
        "--max-turns",
        type=int,
        default=20,
        help="最大工具调用轮数（防止无限循环）",
    )
    return parser.parse_args()


def parse_job_url(url: str) -> tuple[str, str]:
    """从 Job URL 提取 owner/repo 和 job_id"""
    match = re.search(r"github\.com/([^/]+/[^/]+)/actions/runs/\d+/job/(\d+)", url)
    if not match:
        # 尝试 Run URL 格式
        match_run = re.search(r"github\.com/([^/]+/[^/]+)/actions/runs/(\d+)", url)
        if match_run:
            return match_run.group(1), match_run.group(2)
        raise ValueError(f"无法解析 URL: {url}")
    return match.group(1), match.group(2)


def load_skill_content(skill_dir: str) -> str:
    """加载 SKILL.md + references/*.md 作为 system prompt"""
    parts = []
    skill_path = Path(skill_dir)

    for name, rel_path in SKILL_FILES.items():
        file_path = skill_path / rel_path
        if file_path.exists():
            content = file_path.read_text(encoding="utf-8")
            parts.append(f"## {name}\n\n{content}")
        else:
            print(f"警告: 文件不存在 {name} ({file_path})", file=sys.stderr)

    return "\n\n".join(parts)


def bash_execute(command: str) -> str:
    """执行 bash 命令"""
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=120,
            encoding="utf-8",
            errors="replace",
        )
        output = result.stdout
        if result.stderr:
            output += result.stderr
        return output if output else "(无输出)"
    except subprocess.TimeoutExpired:
        return "命令执行超时（120秒）"
    except Exception as e:
        return f"执行错误: {str(e)}"


def read_file_tool(path: str) -> str:
    """读取文件内容"""
    try:
        p = Path(path)
        if not p.exists():
            return f"文件不存在: {path}"
        content = p.read_text(encoding="utf-8", errors="replace")
        if len(content) > 50000:
            return (
                content[:50000]
                + f"\n... (内容过长，已截断，总长度 {len(content)} 字符)"
            )
        return content
    except Exception as e:
        return f"读取错误: {str(e)}"


def grep_file_tool(pattern: str, path: str = ".", include: str = None) -> str:
    """搜索文件内容"""
    try:
        cmd = ["rg", "--no-heading", "--line-number", "--color=never"]
        if include:
            cmd.extend(["-g", include])
        cmd.extend([pattern, path])
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        output = result.stdout
        if not output and result.returncode != 0:
            # 回退到 Python 实现
            import glob as glob_mod

            files = list(glob_mod.glob(f"{path}/**/*", recursive=True))
            if include:
                files = [f for f in files if Path(f).match(include)]
            matches = []
            for f in files:
                if Path(f).is_file():
                    try:
                        content = Path(f).read_text(encoding="utf-8", errors="ignore")
                        for i, line in enumerate(content.splitlines(), 1):
                            if re.search(pattern, line):
                                matches.append(f"{f}:{i}:{line}")
                    except Exception:
                        pass
            output = "\n".join(matches)
        return output if output else f"未找到匹配: {pattern}"
    except Exception as e:
        return f"搜索错误: {str(e)}"


def glob_file_tool(pattern: str, path: str = ".") -> str:
    """查找匹配 glob 的文件"""
    try:
        import glob as glob_mod

        files = glob_mod.glob(f"{path}/{pattern}", recursive=True)
        return "\n".join(files) if files else f"未找到匹配文件: {pattern}"
    except Exception as e:
        return f"搜索错误: {str(e)}"


def write_file_tool(path: str, content: str) -> str:
    """写入文件"""
    try:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return f"已写入: {path} ({len(content)} 字符)"
    except Exception as e:
        return f"写入错误: {str(e)}"


def _run_gh(args: list, repo: str = "") -> str:
    """执行 gh 命令，自动查找路径"""
    gh_candidates = [
        os.environ.get("GH_PATH", ""),
        "C:\\Program Files\\GitHub CLI\\gh.exe",
    ]
    try:
        where = subprocess.run(
            "where gh.exe",
            shell=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if where.stdout.strip():
            gh_candidates.insert(0, where.stdout.strip().split("\n")[0])
    except Exception:
        pass

    for gh in gh_candidates:
        if gh and Path(gh).exists():
            cmd = [gh] + args
            if repo:
                cmd.extend(["--repo", repo])
            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=60,
                    encoding="utf-8",
                    errors="replace",
                )
                return result.stdout + result.stderr
            except Exception as e:
                return f"gh 执行错误: {e}"

    return "gh CLI 未找到"


def fetch_job_info_tool(repo: str, job_id: str) -> str:
    """获取 Job 元数据"""
    output = _run_gh(["api", f"repos/{repo}/actions/jobs/{job_id}"])
    try:
        data = json.loads(output)
        steps_info = ""
        for s in data.get("steps", []):
            if s.get("conclusion") not in ("success", "skipped", None):
                steps_info += (
                    f"  [{s['conclusion'].upper():8}] Step {s['number']}: {s['name']}\n"
                )

        return (
            f"名称: {data.get('name', 'N/A')}\n"
            f"结论: {data.get('conclusion', 'N/A')}\n"
            f"Runner: {data.get('runner_name', 'unknown')}\n"
            f"时间: {data.get('started_at', '?')} ~ {data.get('completed_at', '?')}\n"
            f"Run ID: {data.get('run_id', 'N/A')}\n"
            f"失败步骤:\n{steps_info or '  (无)'}"
        )
    except json.JSONDecodeError:
        return output[:2000]


def fetch_job_logs_tool(
    repo: str, job_id: str, filter_type: str = "runtime_errors"
) -> str:
    """获取过滤后的 Job 日志"""
    filters = {
        "runtime_errors": "RuntimeError OutOfMemoryError AssertionError EngineDeadError exit code 255 synchronized memcpy",
        "compile_errors": "error: failed fatal error unsatisfiable dubious",
        "upload_errors": "upload artifact CreateArtifact ETIMEDOUT",
        "network_errors": "ETIMEDOUT timeout refused ConnectionResetError",
        "all_errors": "RuntimeError AssertionError EngineDeadError exit code ETIMEDOUT OutOfMemoryError fatal ERROR",
    }
    pattern = filters.get(filter_type, filters["runtime_errors"])

    gh_path = _find_gh()
    log_file = f"_diag_job_{job_id}.log"

    # 先下载完整日志
    subprocess.run(
        f'"{gh_path}" run view --job {job_id} --log --repo {repo} > "{log_file}" 2>nul',
        shell=True,
        capture_output=True,
        timeout=120,
    )

    # 用 findstr 过滤
    cmd = f'findstr /i "{pattern}" "{log_file}"'
    result = subprocess.run(
        cmd,
        shell=True,
        capture_output=True,
        text=True,
        timeout=30,
        encoding="utf-8",
        errors="replace",
    )
    output = result.stdout

    # 清理临时文件
    try:
        Path(log_file).unlink()
    except Exception:
        pass

    if not output:
        return f"（未找到 {filter_type} 类型的错误日志）"

    lines = output.strip().split("\n")
    if len(lines) > 50:
        return "\n".join(lines[:50]) + f"\n... (共 {len(lines)} 行，已截断)"
    return output


def _find_gh() -> str:
    """查找 gh.exe 路径"""
    try:
        where = subprocess.run(
            "where gh.exe",
            shell=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if where.stdout.strip():
            return where.stdout.strip().split("\n")[0]
    except Exception:
        pass
    return "C:\\Program Files\\GitHub CLI\\gh.exe"


def fetch_annotations_tool(repo: str, job_id: str) -> str:
    """获取 Annotations"""
    output = _run_gh(["api", f"repos/{repo}/check-runs/{job_id}/annotations"])
    try:
        data = json.loads(output)
        if not data:
            return "（无 Annotations）"
        result = []
        for a in data:
            level = a.get("annotation_level", "?").upper()
            msg = a.get("message", "").splitlines()[0]
            result.append(f"[{level}] {msg}")
        return "\n".join(result)
    except json.JSONDecodeError:
        return output[:2000]


def fetch_run_info_tool(repo: str, run_id: str) -> str:
    """获取 Run 元数据"""
    output = _run_gh(["api", f"repos/{repo}/actions/runs/{run_id}"])
    try:
        data = json.loads(output)
        pr_info = ""
        if data.get("pull_requests"):
            pr = data["pull_requests"][0]
            pr_info = f"\nPR: #{pr['number']} - {pr['title']}"
        return (
            f"工作流: {data.get('name', 'N/A')}\n"
            f"标题: {data.get('display_title', 'N/A')}\n"
            f"分支: {data.get('head_branch', 'N/A')}\n"
            f"事件: {data.get('event', 'N/A')}\n"
            f"结论: {data.get('conclusion', 'N/A')}{pr_info}"
        )
    except json.JSONDecodeError:
        return output[:2000]


def fetch_pr_diff_tool(repo: str, pr_number: str) -> str:
    """获取 PR 变更文件列表"""
    output = _run_gh(["pr", "diff", pr_number, "--repo", repo, "--name-only"])
    files = output.strip().split("\n")
    return "\n".join(f"  - {f}" for f in files if f) or "（无变更文件）"


def fetch_run_script_tool(repo: str, job_id: str) -> str:
    """调用 fetch_run.py 脚本（优先），失败则回退到 fetch-run.sh"""
    py_path = SKILL_DIR / "scripts" / "fetch_run.py"
    sh_path = SKILL_DIR / "scripts" / "fetch-run.sh"

    # 优先使用 Python（跨平台，编码正确）
    if py_path.exists():
        try:
            result = subprocess.run(
                [sys.executable, str(py_path), "--job", job_id, repo],
                capture_output=True,
                text=True,
                timeout=120,
                encoding="utf-8",
                errors="replace",
            )
            output = result.stdout
            if result.stderr:
                output += result.stderr
            if output.strip():
                return output
        except subprocess.TimeoutExpired:
            return "fetch_run.py 执行超时（120秒）"
        except Exception as e:
            pass  # 回退到 bash

    # 回退到 bash
    if sh_path.exists():
        cmd = f'bash "{sh_path}" --job {job_id} {repo}'
        result = bash_execute(cmd)
        if result and "错误" not in result and "not found" not in result.lower():
            return result

    return f"错误: fetch_run.py 和 fetch-run.sh 均不存在或执行失败"


def _get_mcp_client():
    """获取 MCP 客户端实例"""
    sys.path.insert(0, str(SKILL_DIR / "scripts"))
    from mcp_client import MCPClient

    return MCPClient()


def mcp_list_pods_tool(
    namespace: str, start: str, end: str, source: str = "ascend-ci-log"
) -> str:
    """列出 Pod"""
    try:
        client = _get_mcp_client()
        result = client.list_pods(namespace, start, end, source)
        if "error" in result:
            return f"MCP 错误: {result['error']}"
        pods = result.get("result", {}).get("pods", [])
        return "\n".join(f"  - {p}" for p in pods) if pods else "（未找到 Pod）"
    except Exception as e:
        return f"MCP 调用失败: {e}"


def mcp_export_logs_tool(
    namespace: str,
    pod_name: str,
    start: str,
    end: str,
    keywords: str = "",
    source: str = "ascend-ci-log",
) -> str:
    """导出日志"""
    try:
        client = _get_mcp_client()
        result = client.export_logs(namespace, pod_name, keywords, start, end, source)
        if "error" in result:
            return f"MCP 错误: {result['error']}"
        export_id = result.get("export_id", "N/A")
        status = result.get("status", "pending")
        return f"导出任务已创建\n  export_id: {export_id}\n  状态: {status}\n\n请使用 mcp_get_export 查询结果"
    except Exception as e:
        return f"MCP 调用失败: {e}"


def mcp_get_export_tool(export_id: str) -> str:
    """查询导出结果"""
    try:
        client = _get_mcp_client()
        status = client.get_export_status(export_id)
        if "error" in status:
            return f"MCP 错误: {status['error']}"
        phase = status.get("progress", {}).get("phase", "unknown")
        percent = status.get("progress", {}).get("percent", 0)
        logs_written = status.get("progress", {}).get("logs_written", 0)

        if phase != "completed":
            return f"导出进度: {phase} ({percent}%), 已写入 {logs_written} 行"

        download_url = status.get("result", {}).get("download_url", "")
        if download_url:
            content = client.download_export(status)
            if len(content) > 50000:
                return content[:50000] + f"\n... (内容过长，已截断)"
            return content
        return "无下载链接"
    except Exception as e:
        return f"MCP 调用失败: {e}"


def mcp_get_runner_logs_tool(
    runner_name: str,
    start: str,
    end: str,
    namespace: str = "vllm-project",
    keywords: str = "",
) -> str:
    """一键获取 Runner 日志"""
    try:
        client = _get_mcp_client()
        result = client.get_runner_logs(runner_name, namespace, start, end, keywords)
        if not result:
            return "未获取到日志"
        return result
    except Exception as e:
        return f"MCP 调用失败: {e}"


def execute_tool(tool_name: str, arguments: dict) -> str:
    """执行工具调用"""
    if tool_name == "fetch_run_script":
        return fetch_run_script_tool(
            arguments.get("repo", ""), arguments.get("job_id", "")
        )
    elif tool_name == "mcp_list_pods":
        return mcp_list_pods_tool(
            arguments.get("namespace", ""),
            arguments.get("start", ""),
            arguments.get("end", ""),
            arguments.get("source", "ascend-ci-log"),
        )
    elif tool_name == "mcp_export_logs":
        return mcp_export_logs_tool(
            arguments.get("namespace", ""),
            arguments.get("pod_name", ""),
            arguments.get("start", ""),
            arguments.get("end", ""),
            arguments.get("keywords", ""),
            arguments.get("source", "ascend-ci-log"),
        )
    elif tool_name == "mcp_get_export":
        return mcp_get_export_tool(arguments.get("export_id", ""))
    elif tool_name == "mcp_get_runner_logs":
        return mcp_get_runner_logs_tool(
            arguments.get("runner_name", ""),
            arguments.get("start", ""),
            arguments.get("end", ""),
            arguments.get("namespace", "vllm-project"),
            arguments.get("keywords", ""),
        )
    elif tool_name == "fetch_job_info":
        return fetch_job_info_tool(
            arguments.get("repo", ""), arguments.get("job_id", "")
        )
    elif tool_name == "fetch_job_logs":
        return fetch_job_logs_tool(
            arguments.get("repo", ""),
            arguments.get("job_id", ""),
            arguments.get("filter_type", "runtime_errors"),
        )
    elif tool_name == "fetch_annotations":
        return fetch_annotations_tool(
            arguments.get("repo", ""), arguments.get("job_id", "")
        )
    elif tool_name == "fetch_run_info":
        return fetch_run_info_tool(
            arguments.get("repo", ""), arguments.get("run_id", "")
        )
    elif tool_name == "fetch_pr_diff":
        return fetch_pr_diff_tool(
            arguments.get("repo", ""), arguments.get("pr_number", "")
        )
    elif tool_name == "bash_execute":
        return bash_execute(arguments.get("command", ""))
    elif tool_name == "read_file":
        return read_file_tool(arguments.get("path", ""))
    elif tool_name == "grep_file":
        return grep_file_tool(
            arguments.get("pattern", ""),
            arguments.get("path", "."),
            arguments.get("include"),
        )
    elif tool_name == "glob_file":
        return glob_file_tool(
            arguments.get("pattern", ""),
            arguments.get("path", "."),
        )
    elif tool_name == "write_file":
        return write_file_tool(
            arguments.get("path", ""),
            arguments.get("content", ""),
        )
    else:
        return f"未知工具: {tool_name}"


def call_qwen(messages: list, model: str, api_key: str, tools: list) -> dict:
    """调用百炼 API（使用 OpenAI 兼容接口）"""
    from openai import OpenAI

    client = OpenAI(
        api_key=api_key,
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    )

    response = client.chat.completions.create(
        model=model,
        messages=messages,
        tools=tools,
    )

    choice = response.choices[0].message
    result = {
        "role": choice.role,
        "content": choice.content,
        "usage": {
            "prompt_tokens": response.usage.prompt_tokens,
            "completion_tokens": response.usage.completion_tokens,
            "total_tokens": response.usage.total_tokens,
        },
    }
    if choice.tool_calls:
        result["tool_calls"] = [
            {
                "id": tc.id,
                "function": {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,
                },
            }
            for tc in choice.tool_calls
        ]

    return result


def run_diagnosis(
    job_url: str,
    skill_dir: str,
    api_key: str,
    model: str,
    max_turns: int,
):
    """执行诊断流程"""
    repo, job_id = parse_job_url(job_url)
    print(f"仓库: {repo}")
    print(f"Job ID: {job_id}")
    print(f"Skill 目录: {skill_dir}")
    print()

    skill_content = load_skill_content(skill_dir)

    gh_path = (
        subprocess.run(
            "where gh.exe",
            shell=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        .stdout.strip()
        .split("\n")[0]
        if True
        else ""
    )

    env_info = f"""环境信息：
- 操作系统: Windows (PowerShell 5.1)
- gh CLI 路径: {gh_path or "C:\\Program Files\\GitHub CLI\\gh.exe"}
- 没有 bash、python3、curl 等 Unix 工具
- 使用 cmd 命令或 PowerShell 命令
- 使用 findstr 替代 grep
- 使用 type 替代 cat
- 使用 dir 替代 ls"""

    system_prompt = f"""你是一个 CI 故障诊断专家。请严格按照以下 SKILL 文档的指引，诊断用户提供的失败 Job。

<skill_document>
{skill_content}
</skill_document>

{env_info}

## 推荐诊断流程

**第一步（必须）：调用 fetch_run_script**
- `fetch_run_script(repo, job_id)` 会优先运行 `fetch-run.sh`（bash），失败则回退到 `fetch_run.py`
- 一次性输出：
  - Job 基本信息、Runner、失败步骤
  - PR 上下文和变更文件
  - Annotations（通常直接揭示根因）
  - 预过滤的错误日志（如需要）
- **这个工具的输出通常已足够完成诊断**

**第二步（按需）：当 GitHub 日志不足以定位根因时，使用 MCP 查询集群日志**
- 场景：GitHub 日志只显示 exit code 1，但不知道具体原因
- `mcp_get_runner_logs(runner_name, start, end, keywords)` - 一键获取 Runner Pod 日志
  - runner_name: 从 fetch_run_script 输出中获取（如 linux-aarch64-a3-0-ggwx6-runner-qbq72）
  - start/end: 从 fetch_run_script 输出的时间范围获取，格式 YYYY-MM-DD HH:MM:SS
  - **keywords: 必须传，根据错误类型选择过滤词**：
    - 超时/网络: `"ETIMEDOUT|timeout|connection refused"`
    - 内存: `"OOM|OutOfMemory|Killed"`
    - 运行时错误: `"RuntimeError|AssertionError|EngineDeadError"`
    - 编译错误: `"error:|failed|fatal"`
    - 不确定: `"Error|Failed|exit code|Exception"`
- 或分步调用：`mcp_list_pods` → `mcp_export_logs` → `mcp_get_export`

**重要规则：**
1. **必须先调用 fetch_run_script**，它的输出通常足以完成诊断
2. **PR 号从 fetch_run_script 输出的 "PR #xxx" 行获取，不要猜测或使用分支名**
3. **fetch_run_script 输出后，如果信息足够，直接输出诊断报告，不要再调用其他工具**
4. 只有在 GitHub 日志不足以定位根因时，才使用 MCP 查询集群日志
5. **如果某一步获取信息失败（如 PR 不存在），不要反复重试，基于已有信息输出诊断**
6. **最终诊断结果必须有内容，不能输出空报告**
7. 不粘贴大段原始日志，只引用最关键的一行错误标识
8. 每个问题标注责任方（基础设施团队 / PR 作者）

Skill 目录: {skill_dir}
当前工作目录: {os.getcwd()}"""

    messages = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": f"请诊断这个失败的 Job: {job_url}\n\n仓库: {repo}\nJob ID: {job_id}",
        },
    ]

    print("开始诊断...")
    print()

    for turn in range(1, max_turns + 1):
        print(f"--- 第 {turn} 轮 ---")

        message = call_qwen(messages, model, api_key, TOOLS)

        if message.get("tool_calls"):
            tool_calls = message["tool_calls"]
            tool_results = []

            for tc in tool_calls:
                tool_name = tc["function"]["name"]
                tool_args = json.loads(tc["function"]["arguments"])

                print(f"  调用工具: {tool_name}")
                print(f"  参数: {json.dumps(tool_args, ensure_ascii=False)[:200]}")

                result = execute_tool(tool_name, tool_args)

                print(f"  结果长度: {len(result)} 字符")
                if len(result) > 300:
                    print(f"  结果预览: {result[:300]}...")
                else:
                    print(f"  结果: {result}")
                print()

                tool_results.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": result,
                    }
                )

            messages.append(message)
            messages.extend(tool_results)

        else:
            content = message.get("content", "").strip()
            if not content:
                # AI 输出了空内容，强制生成诊断
                print("⚠️  AI 输出为空，基于已有信息生成诊断...")
                messages.append({
                    "role": "user",
                    "content": "请基于以上收集的信息，立即输出诊断报告。即使信息不完整，也要给出当前最佳判断。格式：\n\n# CI 故障诊断报告\n\n- **定性**: 类型 A/B/C/D/E\n- **根因**: ...\n- **关键标识**: ...\n- **责任方**: ...\n- **建议**: ..."
                })
                continue
            print("诊断完成！")
            print()
            print("=" * 60)
            print(content)
            print("=" * 60)
            return

    print(f"达到最大轮数限制 ({max_turns})，停止。")


def check_prerequisites(api_key: str):
    """检查前置要求和依赖"""
    errors = []
    warnings = []

    # 1. Python 版本
    if sys.version_info < (3, 8):
        errors.append(f"Python 版本过低 (当前 {sys.version.split()[0]})，需要 3.8+")

    # 2. 依赖包
    for pkg in ["openai", "requests"]:
        try:
            __import__(pkg)
        except ImportError:
            errors.append(f"缺少依赖: {pkg} (pip install {pkg})")

    # 3. gh CLI
    gh_path = shutil.which("gh") or shutil.which("gh.exe")
    gh_found = False
    gh_logged_in = False
    if gh_path:
        gh_found = True
        # 检查登录状态
        try:
            result = subprocess.run(
                [gh_path, "auth", "status"],
                capture_output=True, text=True, timeout=10,
                encoding="utf-8", errors="replace",
            )
            if result.returncode == 0:
                gh_logged_in = True
            else:
                errors.append("gh 未登录，请先运行: gh auth login")
        except Exception:
            warnings.append("无法检查 gh 登录状态")
    else:
        errors.append("未找到 gh CLI，请安装: https://cli.github.com/")

    # 4. API Key
    if not api_key:
        errors.append("未设置 API Key，请使用 --api-key 参数或设置环境变量 DASHSCOPE_API_KEY")

    # 5. 脚本文件存在性（警告级别）
    for script in ["fetch_run.py", "mcp_client.py"]:
        if not (SKILL_DIR / "scripts" / script).exists():
            warnings.append(f"脚本不存在: {script}")

    # 6. SKILL.md
    if not (SKILL_DIR / "SKILL.md").exists():
        warnings.append("SKILL.md 不存在，AI 将缺少诊断指引")

    # 输出检查结果
    if errors:
        print("\n❌ 前置检查失败:")
        for e in errors:
            print(f"  - {e}")
        print()
        sys.exit(1)

    # 成功输出
    print("✅ 前置检查通过")
    print(f"  Python {sys.version.split()[0]}")
    if gh_path:
        status = "已登录" if gh_logged_in else "未登录"
        print(f"  gh CLI: {gh_path} ({status})")
    print(f"  依赖包: openai, requests")
    if api_key:
        masked = api_key[:6] + "..." + api_key[-4:] if len(api_key) > 10 else "已设置"
        print(f"  API Key: {masked}")
    if warnings:
        print("\n⚠️  警告:")
        for w in warnings:
            print(f"  - {w}")
    print()


def main():
    args = parse_args()

    check_prerequisites(args.api_key)

    run_diagnosis(
        job_url=args.url,
        skill_dir=args.skill_dir,
        api_key=args.api_key,
        model=args.model,
        max_turns=args.max_turns,
    )


if __name__ == "__main__":
    main()
