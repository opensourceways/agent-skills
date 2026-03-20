#!/usr/bin/env python3
"""
Run pytest tests and generate a rich HTML test report.

Usage:
    python run_and_report.py <test_file_or_dir> [report.html]

Features:
  - Runs pytest programmatically and captures results
  - Generates a styled, self-contained HTML report
  - Shows pass/fail/error/skip stats with charts
  - Includes test output, duration, and failure details
"""

import sys
import os
import json
import subprocess
import tempfile
import re
from datetime import datetime
from pathlib import Path


# ─────────────────────────────────────────────
#  Run pytest with JSON output
# ─────────────────────────────────────────────

def run_pytest(test_target: str) -> dict:
    """Run pytest and return parsed JSON results."""
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as tf:
        json_path = tf.name

    cmd = [
        sys.executable, "-m", "pytest",
        test_target,
        "--tb=short",
        "-v",
        f"--json-report",
        f"--json-report-file={json_path}",
        "--no-header",
    ]

    # Try with pytest-json-report; fall back to custom collection
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")

    # Check if JSON report was created
    if Path(json_path).exists():
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            os.unlink(json_path)
            data["_stdout"] = result.stdout
            data["_stderr"] = result.stderr
            data["_returncode"] = result.returncode
            return data
        except Exception:
            pass

    # Fallback: parse stdout
    os.unlink(json_path)
    return _parse_pytest_stdout(result.stdout, result.stderr, result.returncode)


def _parse_pytest_stdout(stdout: str, stderr: str, returncode: int) -> dict:
    """Parse pytest -v output into structured data when JSON plugin unavailable."""
    tests = []
    lines = stdout.splitlines()

    for line in lines:
        # Match lines like:  test_foo.py::TestClass::test_bar PASSED   [ 10%]
        m = re.match(
            r"^([\w/\\.\-]+::[\w:]+)\s+(PASSED|FAILED|ERROR|SKIPPED|XFAIL|XPASS)"
            r"(?:\s+\[[\s\d]+%\])?",
            line.strip()
        )
        if m:
            node_id, outcome = m.group(1), m.group(2)
            tests.append({
                "nodeid": node_id,
                "outcome": outcome.lower(),
                "duration": 0.0,
                "longrepr": "",
            })

    # Extract failure details
    fail_section = False
    current_fail = None
    fail_lines = []
    for line in lines:
        if line.startswith("FAILED") or line.startswith("ERROR"):
            fail_section = True
        if re.match(r"_{5,}", line):
            if current_fail and fail_lines:
                for t in tests:
                    if t["nodeid"] == current_fail:
                        t["longrepr"] = "\n".join(fail_lines)
            fail_lines = []
            current_fail = None
        if fail_section:
            m2 = re.match(r"_{5,}\s+([\w/\\.\-]+::[\w:]+)\s+_{5,}", line)
            if m2:
                current_fail = m2.group(1)
            else:
                fail_lines.append(line)

    # Summary stats
    passed = sum(1 for t in tests if t["outcome"] == "passed")
    failed = sum(1 for t in tests if t["outcome"] in ("failed", "error"))
    skipped = sum(1 for t in tests if t["outcome"] == "skipped")

    return {
        "tests": tests,
        "summary": {
            "passed": passed,
            "failed": failed,
            "error": 0,
            "skipped": skipped,
            "total": len(tests),
        },
        "_stdout": stdout,
        "_stderr": stderr,
        "_returncode": returncode,
        "_fallback": True,
    }


# ─────────────────────────────────────────────
#  HTML Report Generator
# ─────────────────────────────────────────────

HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>测试报告 - {title}</title>
<style>
  :root {{
    --pass:  #22c55e; --fail: #ef4444; --skip: #f59e0b;
    --error: #f97316; --bg: #f8fafc; --card: #ffffff;
    --border: #e2e8f0; --text: #1e293b; --muted: #64748b;
    --blue: #3b82f6; --blue-dark: #1d4ed8;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: 'Segoe UI', Arial, sans-serif; background: var(--bg);
         color: var(--text); padding: 24px; }}
  h1 {{ font-size: 22px; font-weight: 700; margin-bottom: 4px; color: var(--blue-dark); }}
  .meta {{ color: var(--muted); font-size: 13px; margin-bottom: 20px; }}

  /* Summary cards */
  .cards {{ display: flex; gap: 14px; flex-wrap: wrap; margin-bottom: 24px; }}
  .card {{
    flex: 1; min-width: 120px; padding: 16px 20px;
    border-radius: 10px; background: var(--card);
    border: 1px solid var(--border); text-align: center;
    box-shadow: 0 1px 3px rgba(0,0,0,.06);
  }}
  .card .num {{ font-size: 32px; font-weight: 800; line-height: 1.1; }}
  .card .lbl {{ font-size: 12px; color: var(--muted); margin-top: 4px; }}
  .card.total .num {{ color: var(--blue); }}
  .card.passed .num {{ color: var(--pass); }}
  .card.failed .num {{ color: var(--fail); }}
  .card.skipped .num {{ color: var(--skip); }}
  .card.error .num  {{ color: var(--error); }}

  /* Progress bar */
  .progress-wrap {{ margin-bottom: 28px; }}
  .progress-bar {{
    height: 10px; border-radius: 99px;
    background: var(--border); overflow: hidden;
    display: flex;
  }}
  .progress-bar .seg {{ transition: width .3s; }}
  .seg-pass  {{ background: var(--pass); }}
  .seg-fail  {{ background: var(--fail); }}
  .seg-skip  {{ background: var(--skip); }}
  .seg-error {{ background: var(--error); }}
  .progress-label {{
    font-size: 13px; color: var(--muted); margin-top: 6px;
    display: flex; gap: 16px;
  }}
  .progress-label span {{ display: flex; align-items: center; gap: 5px; }}
  .dot {{ width: 10px; height: 10px; border-radius: 50%; display: inline-block; }}

  /* Table */
  table {{ width: 100%; border-collapse: collapse; font-size: 13px;
           background: var(--card); border-radius: 10px;
           overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,.06); }}
  thead th {{
    background: #1e3a5f; color: #fff; padding: 10px 14px;
    text-align: left; font-weight: 600; font-size: 12px;
    letter-spacing: .5px; text-transform: uppercase;
  }}
  tbody tr {{ border-bottom: 1px solid var(--border); }}
  tbody tr:hover {{ background: #f1f5f9; }}
  td {{ padding: 9px 14px; vertical-align: top; }}
  .badge {{
    display: inline-block; padding: 2px 9px; border-radius: 99px;
    font-size: 11px; font-weight: 700; letter-spacing: .3px;
  }}
  .pass  {{ background: #dcfce7; color: #166534; }}
  .fail  {{ background: #fee2e2; color: #991b1b; }}
  .skip  {{ background: #fef3c7; color: #92400e; }}
  .error {{ background: #ffedd5; color: #9a3412; }}

  .test-id {{ font-family: monospace; font-size: 12px; color: var(--muted);
              max-width: 380px; word-break: break-all; }}
  .duration {{ white-space: nowrap; color: var(--muted); }}

  /* Failure detail */
  .detail-btn {{
    cursor: pointer; font-size: 11px; color: var(--blue);
    background: none; border: none; padding: 0; text-decoration: underline;
  }}
  .detail-box {{
    display: none; margin-top: 6px;
    background: #1e1e1e; color: #d4d4d4;
    padding: 10px; border-radius: 6px;
    font-family: monospace; font-size: 11px;
    white-space: pre-wrap; max-height: 250px; overflow-y: auto;
  }}

  /* Console output */
  .console-section {{ margin-top: 28px; }}
  .console-section h2 {{ font-size: 15px; margin-bottom: 8px; color: var(--blue-dark); }}
  .console-box {{
    background: #1e1e1e; color: #d4d4d4;
    padding: 14px; border-radius: 8px;
    font-family: monospace; font-size: 12px;
    white-space: pre-wrap; max-height: 360px; overflow-y: auto;
    line-height: 1.5;
  }}
  .pass-line  {{ color: #86efac; }}
  .fail-line  {{ color: #fca5a5; }}
  .error-line {{ color: #fdba74; }}
</style>
</head>
<body>
<h1>自动化测试报告</h1>
<p class="meta">测试目标：{title} &nbsp;|&nbsp; 执行时间：{run_time} &nbsp;|&nbsp; 耗时：{duration}s</p>

<div class="cards">
  <div class="card total">  <div class="num">{total}</div>  <div class="lbl">总用例</div>  </div>
  <div class="card passed"> <div class="num">{passed}</div> <div class="lbl">通过</div>   </div>
  <div class="card failed"> <div class="num">{failed}</div> <div class="lbl">失败</div>   </div>
  <div class="card error">  <div class="num">{error}</div>  <div class="lbl">错误</div>   </div>
  <div class="card skipped"><div class="num">{skipped}</div><div class="lbl">跳过</div>   </div>
</div>

<div class="progress-wrap">
  <div class="progress-bar">
    <div class="seg seg-pass"  style="width:{pct_pass}%"></div>
    <div class="seg seg-fail"  style="width:{pct_fail}%"></div>
    <div class="seg seg-error" style="width:{pct_error}%"></div>
    <div class="seg seg-skip"  style="width:{pct_skip}%"></div>
  </div>
  <div class="progress-label">
    <span><span class="dot" style="background:var(--pass)"></span>通过 {pct_pass:.1f}%</span>
    <span><span class="dot" style="background:var(--fail)"></span>失败 {pct_fail:.1f}%</span>
    <span><span class="dot" style="background:var(--error)"></span>错误 {pct_error:.1f}%</span>
    <span><span class="dot" style="background:var(--skip)"></span>跳过 {pct_skip:.1f}%</span>
  </div>
</div>

<table>
<thead>
  <tr>
    <th>#</th>
    <th>测试节点</th>
    <th>状态</th>
    <th>耗时(s)</th>
    <th>详情</th>
  </tr>
</thead>
<tbody>
{rows}
</tbody>
</table>

{console_section}

<script>
function toggle(id) {{
  var el = document.getElementById(id);
  el.style.display = el.style.display === 'block' ? 'none' : 'block';
}}
</script>
</body>
</html>
"""

ROW_TEMPLATE = """\
<tr>
  <td>{idx}</td>
  <td class="test-id">{nodeid}</td>
  <td><span class="badge {css}">{label}</span></td>
  <td class="duration">{duration}</td>
  <td>{detail}</td>
</tr>"""

OUTCOME_MAP = {
    "passed":  ("pass",  "通过"),
    "failed":  ("fail",  "失败"),
    "error":   ("error", "错误"),
    "skipped": ("skip",  "跳过"),
    "xfail":   ("skip",  "预期失败"),
    "xpass":   ("pass",  "意外通过"),
}


def _colorize_console(text):
    """Add CSS spans to console output lines."""
    result = []
    for line in text.splitlines():
        if " PASSED" in line or "passed" in line.lower():
            result.append(f'<span class="pass-line">{_esc(line)}</span>')
        elif " FAILED" in line or " ERROR" in line:
            result.append(f'<span class="fail-line">{_esc(line)}</span>')
        elif "Warning" in line or "warning" in line:
            result.append(f'<span class="error-line">{_esc(line)}</span>')
        else:
            result.append(_esc(line))
    return "\n".join(result)


def _esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def build_html_report(pytest_data: dict, target: str, duration: float) -> str:
    summary = pytest_data.get("summary", {})
    tests   = pytest_data.get("tests", [])

    total   = summary.get("total",   len(tests))
    passed  = summary.get("passed",  0)
    failed  = summary.get("failed",  0)
    error   = summary.get("error",   0)
    skipped = summary.get("skipped", 0)

    # Recalculate from tests list if needed
    if total == 0 and tests:
        total   = len(tests)
        passed  = sum(1 for t in tests if t.get("outcome") == "passed")
        failed  = sum(1 for t in tests if t.get("outcome") in ("failed",))
        error   = sum(1 for t in tests if t.get("outcome") == "error")
        skipped = sum(1 for t in tests if t.get("outcome") == "skipped")

    safe_total = total if total > 0 else 1
    pct_pass   = passed  / safe_total * 100
    pct_fail   = failed  / safe_total * 100
    pct_error  = error   / safe_total * 100
    pct_skip   = skipped / safe_total * 100

    rows = []
    for i, t in enumerate(tests, 1):
        outcome  = t.get("outcome", "unknown")
        css, label = OUTCOME_MAP.get(outcome, ("skip", outcome))
        dur      = t.get("duration", 0)
        dur_str  = f"{dur:.3f}" if dur else "-"
        longrepr = t.get("longrepr", "") or t.get("call", {}).get("longrepr", "")

        if longrepr:
            detail = (
                f'<button class="detail-btn" onclick="toggle(\'d{i}\')">查看详情</button>'
                f'<div id="d{i}" class="detail-box">{_esc(str(longrepr))}</div>'
            )
        else:
            detail = ""

        rows.append(ROW_TEMPLATE.format(
            idx=i,
            nodeid=_esc(t.get("nodeid", "")),
            css=css, label=label,
            duration=dur_str,
            detail=detail,
        ))

    stdout = pytest_data.get("_stdout", "")
    if stdout.strip():
        console_section = (
            '<div class="console-section">'
            '<h2>控制台输出</h2>'
            f'<div class="console-box">{_colorize_console(stdout)}</div>'
            '</div>'
        )
    else:
        console_section = ""

    return HTML_TEMPLATE.format(
        title=_esc(target),
        run_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        duration=f"{duration:.1f}",
        total=total, passed=passed, failed=failed,
        error=error, skipped=skipped,
        pct_pass=pct_pass, pct_fail=pct_fail,
        pct_error=pct_error, pct_skip=pct_skip,
        rows="\n".join(rows),
        console_section=console_section,
    )


# ─────────────────────────────────────────────
#  Main
# ─────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print("Usage: python run_and_report.py <test_file_or_dir> [report.html]")
        sys.exit(1)

    target    = sys.argv[1]
    out_html  = sys.argv[2] if len(sys.argv) > 2 else None

    if not Path(target).exists():
        print(f"[ERROR] Path not found: {target}")
        sys.exit(1)

    if out_html is None:
        base = Path(target)
        if base.is_dir():
            out_html = str(base / "test_report.html")
        else:
            out_html = str(base.parent / "test_report.html")

    # Install pytest-json-report if available
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "pytest-json-report", "-q"],
        capture_output=True
    )

    print(f"[INFO] Running tests: {target}")
    start = datetime.now()
    results = run_pytest(target)
    duration = (datetime.now() - start).total_seconds()

    summary = results.get("summary", {})
    total   = summary.get("total", len(results.get("tests", [])))
    passed  = summary.get("passed", 0)
    failed  = summary.get("failed", 0) + summary.get("error", 0)

    print(f"[INFO] Results: {total} total, {passed} passed, {failed} failed "
          f"({duration:.1f}s)")

    html = build_html_report(results, target, duration)
    Path(out_html).write_text(html, encoding="utf-8")
    print(f"[OK]   HTML report -> {out_html}")

    return 0 if results.get("_returncode", 1) == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
