#!/usr/bin/env python3
"""
collect_failed_runs.py - 收集 GitHub 仓库一段时间内失败的 CI，支持按 Job 名称过滤

用法:
  python scripts/collect_failed_runs.py --hours 24 --exclude-jobs lint
  python scripts/collect_failed_runs.py --from 2024-01-01 --to 2024-01-31
  python scripts/collect_failed_runs.py --hours 24 --exclude-jobs lint check-style --output custom.xlsx

依赖:
  pip install openpyxl requests
"""

import argparse
import os
import sys
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import requests
from openpyxl import Workbook
from openpyxl.styles import Font


def parse_args():
    parser = argparse.ArgumentParser(description="收集 GitHub 仓库一段时间内失败的 CI")
    parser.add_argument(
        "--repo",
        default="vllm-project/vllm-ascend",
        help="GitHub 仓库，格式 owner/repo",
    )
    parser.add_argument("--from", dest="from_date", help="起始日期 YYYY-MM-DD")
    parser.add_argument("--to", dest="to_date", help="结束日期 YYYY-MM-DD")
    parser.add_argument("--hours", type=int, help="过去多少小时")
    parser.add_argument(
        "--exclude-jobs",
        nargs="*",
        default=[],
        help="排除的 Job 名称（支持正则）",
    )
    parser.add_argument("--output", help="输出文件路径")
    parser.add_argument(
        "--token",
        default=os.environ.get("GITHUB_TOKEN", ""),
        help="GitHub Token",
    )
    parser.add_argument(
        "--per-page",
        type=int,
        default=100,
        help="每页数量",
    )
    return parser.parse_args()


def get_time_range(args):
    now = datetime.now(timezone.utc)

    if args.from_date and args.to_date:
        since = datetime.strptime(
            args.from_date + "T00:00:00Z", "%Y-%m-%dT%H:%M:%SZ"
        ).replace(tzinfo=timezone.utc)
        until = datetime.strptime(
            args.to_date + "T23:59:59Z", "%Y-%m-%dT%H:%M:%SZ"
        ).replace(tzinfo=timezone.utc)
    elif args.from_date:
        since = datetime.strptime(
            args.from_date + "T00:00:00Z", "%Y-%m-%dT%H:%M:%SZ"
        ).replace(tzinfo=timezone.utc)
        until = now
    elif args.hours:
        since = now - timedelta(hours=args.hours)
        until = now
    else:
        since = now - timedelta(hours=2)
        until = now

    return since.isoformat().replace("+00:00", "Z"), until.isoformat().replace(
        "+00:00", "Z"
    )


def github_get(url_path, token, params=None):
    url = f"https://api.github.com{url_path}"
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "collect-failed-runs-script",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    resp = requests.get(url, headers=headers, params=params)
    resp.raise_for_status()
    return resp.json()


def fetch_failed_runs(repo, since, until, token, per_page):
    all_runs = []
    page = 1

    while True:
        params = {
            "status": "failure",
            "per_page": per_page,
            "page": page,
            "created": f"{since}..{until}",
        }

        url_path = f"/repos/{repo}/actions/runs"
        data = github_get(url_path, token, params)
        runs = data.get("workflow_runs", [])

        if not runs:
            break

        all_runs.extend(runs)

        if len(runs) < per_page:
            break
        page += 1

    return all_runs


def fetch_run_jobs(repo, run_id, token):
    all_jobs = []
    page = 1

    while True:
        params = {
            "per_page": 100,
            "page": page,
        }

        url_path = f"/repos/{repo}/actions/runs/{run_id}/jobs"
        data = github_get(url_path, token, params)
        jobs = data.get("jobs", [])

        if not jobs:
            break

        all_jobs.extend(jobs)

        if len(jobs) < 100:
            break
        page += 1

    return all_jobs


def should_exclude_run(jobs, exclude_patterns):
    if not exclude_patterns:
        return False

    failed_jobs = [j for j in jobs if j.get("conclusion") == "failure"]
    if not failed_jobs:
        return True

    for job in failed_jobs:
        job_name = job.get("name", "")
        is_excluded = any(
            re.search(pattern, job_name, re.IGNORECASE) for pattern in exclude_patterns
        )
        if not is_excluded:
            return False

    return True


def get_excluded_job_names(jobs, exclude_patterns):
    excluded = []
    for job in jobs:
        if job.get("conclusion") != "failure":
            continue
        job_name = job.get("name", "")
        is_excluded = any(
            re.search(pattern, job_name, re.IGNORECASE) for pattern in exclude_patterns
        )
        if is_excluded:
            excluded.append(job_name)
    return excluded


def calc_duration(iso_str1, iso_str2):
    try:
        d1 = datetime.fromisoformat(iso_str1.replace("Z", "+00:00"))
        d2 = datetime.fromisoformat(iso_str2.replace("Z", "+00:00"))
        diff_seconds = int((d2 - d1).total_seconds())
        hours = diff_seconds // 3600
        minutes = (diff_seconds % 3600) // 60
        seconds = diff_seconds % 60

        parts = []
        if hours > 0:
            parts.append(f"{hours}h")
        if minutes > 0:
            parts.append(f"{minutes}m")
        parts.append(f"{seconds}s")
        return " ".join(parts)
    except Exception:
        return "N/A"


def format_time(iso_str):
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return iso_str


def write_xlsx(records, output_path):
    wb = Workbook()
    ws = wb.active
    ws.title = "失败记录"

    headers = [
        "Job URL",
        "Run ID",
        "创建时间",
        "失败时间",
        "运行时间",
        "工作流名称",
        "分支",
        "用户",
    ]
    ws.append(headers)

    for r in records:
        for job in r["failed_jobs"]:
            ws.append(
                [
                    job["url"],
                    r["run_id"],
                    r["created_at"],
                    r["updated_at"],
                    r["duration"],
                    r["workflow_name"],
                    r["branch"],
                    r["user"],
                ]
            )

    col_widths = [80, 18, 22, 22, 15, 30, 25, 20]
    for i, width in enumerate(col_widths, 1):
        ws.column_dimensions[
            chr(64 + i) if i <= 26 else "A" + chr(64 + i - 26)
        ].width = width

    wb.save(output_path)


def main():
    args = parse_args()

    if not args.token:
        print("警告: 未设置 GitHub Token，可能触发 API 限流。")
        print("请设置环境变量 GITHUB_TOKEN 或使用 --token 参数。")

    since, until = get_time_range(args)
    print(f"仓库: {args.repo}")
    print(f"时间范围: {since} ~ {until}")
    if args.exclude_jobs:
        print(f"排除 Job: {', '.join(args.exclude_jobs)}")
    print()

    print("获取失败的 Runs...")
    runs = fetch_failed_runs(args.repo, since, until, args.token, args.per_page)
    print(f"共获取到 {len(runs)} 个失败的 Run")

    records = []
    skipped_count = 0
    skipped_reasons = []

    for i, run in enumerate(runs, 1):
        run_id = run["id"]
        print(f"  处理 [{i}/{len(runs)}] Run #{run_id}... ", end="", flush=True)

        jobs = fetch_run_jobs(args.repo, run_id, args.token)

        if should_exclude_run(jobs, args.exclude_jobs):
            excluded_names = get_excluded_job_names(jobs, args.exclude_jobs)
            skipped_count += 1
            skipped_reasons.append(
                f"Run #{run_id} 被排除 (失败 Job: {', '.join(excluded_names)})"
            )
            print("跳过 (被过滤)")
            continue

        user = run.get("triggering_actor", {}).get("login", "N/A")
        failed_jobs = [
            {
                "url": f"https://github.com/{args.repo}/actions/runs/{run_id}/job/{j['id']}",
            }
            for j in jobs
            if j.get("conclusion") == "failure"
        ]

        records.append(
            {
                "url": f"https://github.com/{args.repo}/actions/runs/{run_id}",
                "run_id": run_id,
                "created_at": format_time(run["created_at"]),
                "updated_at": format_time(run["updated_at"]),
                "duration": calc_duration(run["created_at"], run["updated_at"]),
                "workflow_name": run.get("name", "N/A"),
                "branch": run.get("head_branch", "N/A"),
                "user": user,
                "failed_jobs": failed_jobs,
            }
        )
        print("保留")

    print()
    print(f"保留 {len(records)} 条记录，跳过 {skipped_count} 条")

    if skipped_reasons:
        print("\n跳过的 Run:")
        for reason in skipped_reasons:
            print(f"  - {reason}")

    if not records:
        print("\n没有符合条件的记录，不生成文件。")
        return

    output_path = args.output
    if not output_path:
        output_dir = "Fail_CI_Problem"
        os.makedirs(output_dir, exist_ok=True)
        today = datetime.now().strftime("%Y-%m-%d")
        output_path = os.path.join(output_dir, f"failed-runs-{today}.xlsx")

    write_xlsx(records, output_path)
    print(f"\n已写入: {output_path}")


if __name__ == "__main__":
    main()
