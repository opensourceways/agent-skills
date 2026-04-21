#!/usr/bin/env python3
"""
fetch_run.py - 一次性抓取 CI Run/Job 的 runner 信息和关键日志

用途：将每个 Job 原始日志（可达数百行）压缩至 ~20 行关键错误行
      在 LLM 进行 Step 2+ 推理之前完成所有数据收集，节省 token

用法：
  python fetch_run.py --run <run_id> [owner/repo]
  python fetch_run.py --job <job_id> [owner/repo]

依赖：gh CLI（已登录）
"""

import argparse
import json
import os
import re
import subprocess
import sys
import io
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")


DEFAULT_REPO = "vllm-project/vllm-ascend"

RUNTIME_PATTERNS = (
    r"RuntimeError|OutOfMemoryError|NPU out of memory|AssertionError|"
    r"AttributeError|UnboundLocalError|TypeError|ValueError|ImportError|"
    r"EngineDeadError|EngineCore encountered|shm_broadcast.*60 seconds|"
    r"No available shared memory broadcast|"
    r"Process completed with exit code [1-9]|exit code 255|"
    r"synchronized memcpy failed|NPU function error|error code is [0-9]|"
    r"httpcore\.(ReadError|ConnectError)|httpx\.(ReadError|ConnectError)|"
    r"RemoteProtocolError"
)

COMPILE_PATTERNS = (
    r"error:.*failed|error:.*exit|fatal error|ERROR.*install|"
    r"No solution found|unsatisfiable|ERROR.*Build|dubious ownership"
)

NETWORK_PATTERNS = (
    r"ETIMEDOUT|timeout|failed to create artifact|network|connection refused"
)

EXCLUDE_PATTERNS = r"ops_error\.h|error_check\.h"

COMPILE_EXCLUDE = (
    r"##\[group\]|##\[endgroup\]|warning.*format|"
    r"ops_error\.h|error_check\.h|tiling func|tiling failed"
)


def find_gh() -> str:
    """查找 gh.exe 路径"""
    env_path = os.environ.get("GH_PATH", "")
    if env_path and Path(env_path).exists():
        return env_path

    candidates = [
        r"C:\Program Files\GitHub CLI\gh.exe",
        r"C:\Program Files (x86)\GitHub CLI\gh.exe",
    ]
    for c in candidates:
        if Path(c).exists():
            return c

    try:
        result = subprocess.run(
            "where gh.exe",
            shell=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if result.stdout.strip():
            return result.stdout.strip().split("\n")[0]
    except Exception:
        pass

    return "gh"


def run_gh(args: list, repo: str = "") -> str:
    """执行 gh 命令，返回 stdout"""
    gh = find_gh()
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
    except subprocess.TimeoutExpired:
        return "(命令超时)"
    except Exception as e:
        return f"(执行错误: {e})"


def gh_api(endpoint: str, repo: str = "") -> dict:
    """调用 gh api，返回解析后的 JSON"""
    output = run_gh(["api", endpoint], repo=repo)
    try:
        return json.loads(output)
    except json.JSONDecodeError:
        return {}


def grep_lines(
    text: str, include_pattern: str, exclude_pattern: str = "", max_lines: int = 0
) -> str:
    """按正则过滤行"""
    lines = text.splitlines()
    matched = []
    inc_re = re.compile(include_pattern, re.IGNORECASE)
    exc_re = re.compile(exclude_pattern, re.IGNORECASE) if exclude_pattern else None

    for line in lines:
        if inc_re.search(line):
            if exc_re and exc_re.search(line):
                continue
            matched.append(line)
            if max_lines and len(matched) >= max_lines:
                break

    return "\n".join(matched)


def fetch_job_meta(repo: str, job_id: str) -> dict:
    """获取 Job 元数据"""
    return gh_api(f"repos/{repo}/actions/jobs/{job_id}")


def fetch_run_meta(repo: str, run_id: str) -> dict:
    """获取 Run 元数据"""
    return gh_api(f"repos/{repo}/actions/runs/{run_id}")


def fetch_annotations(repo: str, job_id: str) -> list:
    """获取 Annotations"""
    data = gh_api(f"repos/{repo}/check-runs/{job_id}/annotations")
    return data if isinstance(data, list) else []


def fetch_pr_diff(repo: str, pr_number: str) -> list:
    """获取 PR 变更文件列表"""
    output = run_gh(["pr", "diff", pr_number, "--name-only"], repo=repo)
    return [f for f in output.strip().splitlines() if f]


def fetch_job_logs(repo: str, job_id: str) -> str:
    """获取 Job 完整日志"""
    gh = find_gh()
    log_file = f"_fetch_run_job_{job_id}.log"
    try:
        # Use powershell to redirect with UTF-8 encoding
        subprocess.run(
            f'cmd /c chcp 65001 >nul & "{gh}" run view --job {job_id} --log --repo {repo} > "{log_file}" 2>nul',
            shell=True,
            capture_output=True,
            timeout=120,
        )
        content = Path(log_file).read_text(encoding="utf-8", errors="replace")
        Path(log_file).unlink(missing_ok=True)
        return content
    except Exception:
        try:
            Path(log_file).unlink(missing_ok=True)
        except Exception:
            pass
        return ""


def has_network_root_cause(annotations: list) -> bool:
    """判断 Annotations 是否已明确网络/超时类根因"""
    for a in annotations:
        msg = a.get("message", "")
        if re.search(NETWORK_PATTERNS, msg, re.IGNORECASE):
            return True
    return False


def format_job_header(meta: dict) -> str:
    """格式化 Job 头部信息"""
    conclusion = (meta.get("conclusion") or "unknown").upper()
    name = meta.get("name", "N/A")
    runner = meta.get("runner_name") or "(unknown)"
    started = meta.get("started_at", "?")
    completed = meta.get("completed_at", "?")

    lines = [f"── [{conclusion}] {name}"]
    lines.append(f"   Runner : {runner}")
    lines.append(f"   时间   : {started} ~ {completed}")

    steps = [
        s
        for s in meta.get("steps", [])
        if s.get("conclusion") not in ("success", "skipped", None)
    ]
    if steps:
        lines.append("   ── 失败步骤")
        for s in steps:
            lines.append(
                f"      [{s['conclusion'].upper():8}] Step {s['number']}: {s['name']}"
            )

    return "\n".join(lines)


def format_annotations(annotations: list) -> str:
    """格式化 Annotations"""
    if not annotations:
        return "      （无 Annotations）"
    lines = []
    for a in annotations:
        level = a.get("annotation_level", "?").upper()
        msg = a.get("message", "").splitlines()[0]
        lines.append(f"      [{level}] {msg}")
    return "\n".join(lines)


def diagnose_single_job(repo: str, job_id: str) -> str:
    """诊断单个 Job"""
    output = []
    output.append("=" * 40)
    output.append(f" Single Job Mode | {repo}")
    output.append("=" * 40)

    # Step A: 基本信息
    job_meta = fetch_job_meta(repo, job_id)
    if not job_meta:
        output.append(f"错误: 无法获取 Job {job_id} 的信息")
        return "\n".join(output)

    output.append(format_job_header(job_meta))

    # Step B: PR 上下文
    run_id = job_meta.get("run_id", "")
    if run_id:
        run_meta = fetch_run_meta(repo, str(run_id))
        prs = run_meta.get("pull_requests", [])
        pr_num = prs[0].get("number") if prs else None
        title = run_meta.get("display_title", "")
        branch = run_meta.get("head_branch", "")

        pr_str = f"#{pr_num} " if pr_num else ""
        output.append(f"   PR     : {pr_str}{title} ({branch})")

        if pr_num:
            output.append("   ── PR 变更文件（分类参考）")
            diff_files = fetch_pr_diff(repo, str(pr_num))
            for f in diff_files[:20]:
                output.append(f"      {f}")

    # Step C: Annotations
    output.append("")
    output.append("   ── Annotations")
    annotations = fetch_annotations(repo, job_id)
    output.append(format_annotations(annotations))

    # Step D: 判断是否需要拉日志
    if has_network_root_cause(annotations):
        output.append("")
        output.append("   ── Annotations 已明确根因（网络/超时类），跳过完整日志拉取")
        return "\n".join(output)

    # Step E: 拉取并过滤日志
    full_log = fetch_job_logs(repo, job_id)
    if not full_log:
        output.append("")
        output.append("   ── 无法获取日志")
        return "\n".join(output)

    # 运行时错误
    runtime_lines = grep_lines(
        full_log, RUNTIME_PATTERNS, EXCLUDE_PATTERNS, max_lines=15
    )
    output.append("")
    output.append("   ── 运行时错误（高优先级）")
    if runtime_lines:
        output.append(runtime_lines)
    else:
        # 编译/安装错误
        compile_lines = grep_lines(
            full_log, COMPILE_PATTERNS, COMPILE_EXCLUDE, max_lines=5
        )
        output.append("   ── 编译/安装错误（次优先级）")
        if compile_lines:
            output.append(compile_lines)
        else:
            output.append("   （未发现关键错误行）")

    # 最后输出
    last_lines = grep_lines(
        full_log, r"^[^\s]+\s+(UNKNOWN STEP|Run python|bash|pytest)", max_lines=5
    )
    output.append("   ── 最后输出（定位失败阶段）")
    if last_lines:
        output.append(last_lines)

    return "\n".join(output)


def diagnose_run(repo: str, run_id: str) -> str:
    """诊断整个 Run 的所有失败 Job"""
    output = []
    sep = "=" * 40
    output.append(sep)
    output.append(f" Run {run_id} | {repo}")
    output.append(sep)

    # Run 概览
    run_view = run_gh(["run", "view", run_id], repo=repo)
    output.append(run_view.strip())
    output.append("")

    # PR 上下文
    run_meta = fetch_run_meta(repo, run_id)
    prs = run_meta.get("pull_requests", [])
    pr_num = prs[0].get("number") if prs else None
    if pr_num:
        output.append(sep)
        output.append(f" PR #{pr_num} 变更文件（分类参考）")
        output.append(sep)
        diff_files = fetch_pr_diff(repo, str(pr_num))
        for f in diff_files[:20]:
            output.append(f)
        output.append("")

    # 获取失败/取消的 Job
    jobs_data = gh_api(f"repos/{repo}/actions/runs/{run_id}/jobs?per_page=100")
    jobs = jobs_data.get("jobs", [])
    failed_jobs = [j for j in jobs if j.get("conclusion") in ("failure", "cancelled")]

    if not failed_jobs:
        output.append("（未发现失败或取消的 Job）")
        return "\n".join(output)

    output.append(sep)
    output.append(f" 失败 / 取消 Job 详情（共 {len(failed_jobs)} 个）")
    output.append(sep)

    for job in failed_jobs:
        job_id = job["id"]
        output.append("")
        output.append(format_job_header(job))

        conclusion = job.get("conclusion", "")
        if conclusion == "failure":
            full_log = fetch_job_logs(repo, str(job_id))

            runtime_lines = grep_lines(
                full_log, RUNTIME_PATTERNS, EXCLUDE_PATTERNS, max_lines=15
            )
            output.append("   ── 运行时错误（高优先级）")
            if runtime_lines:
                output.append(runtime_lines)
            else:
                compile_lines = grep_lines(
                    full_log, COMPILE_PATTERNS, COMPILE_EXCLUDE, max_lines=5
                )
                output.append("   ── 编译/安装错误（次优先级）")
                if compile_lines:
                    output.append(compile_lines)
                else:
                    output.append("   （未发现关键错误行）")

            last_lines = grep_lines(
                full_log,
                r"^[^\s]+\s+(UNKNOWN STEP|Run python|bash|pytest)",
                max_lines=5,
            )
            output.append("   ── 最后输出（定位失败阶段）")
            if last_lines:
                output.append(last_lines)
        else:
            output.append(
                "   （cancelled — 根因见 Run 概览中的 ANNOTATIONS，通常为 queue 抢占）"
            )

    output.append("")
    output.append(sep)
    output.append(" 补充命令（按需使用）：")
    output.append(f"   完整日志 : gh run view --job <id> --log --repo {repo}")
    output.append(f"   PR diff  : gh pr diff <pr> --repo {repo} --name-only")
    output.append(
        f"   kubectl  : kubectl get pods --all-namespaces | grep <runner_name>"
    )
    output.append(sep)

    return "\n".join(output)


def main():
    parser = argparse.ArgumentParser(description="获取 CI Run/Job 的关键日志")
    parser.add_argument("--run", help="Run ID")
    parser.add_argument("--job", help="Job ID")
    parser.add_argument("repo", nargs="?", default=DEFAULT_REPO, help="Owner/repo")
    args = parser.parse_args()

    repo = args.repo
    if args.job:
        print(diagnose_single_job(repo, args.job))
    elif args.run:
        print(diagnose_run(repo, args.run))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
