#!/usr/bin/env python3
"""
Generate pytest automation test scripts from YAML test case files.

Usage:
    python generate_pytest.py <input.yaml> [output_dir]

Supports:
  - API tests  (type contains: 功能测试/异常测试/边界测试/安全测试/性能测试)
  - UI  tests  (type contains: UI测试/页面测试)

Auto-detects test mode from 'source' field:
  - Contains HTTP method (GET/POST/PUT/DELETE/PATCH) → API mode
  - Contains http:// or https:// URL → UI mode (Playwright)
  - Falls back to checking test case types

Output files:
  - test_<suite>.py       main pytest file
  - conftest.py           shared fixtures
"""

import sys, os, re, yaml
from datetime import datetime
from pathlib import Path


# ─────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────

def load_yaml(path):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def slugify(text):
    """Convert Chinese/mixed text to a valid Python identifier."""
    text = str(text)
    text = re.sub(r"[^\w\u4e00-\u9fff]", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text or "case"

def indent(text, n=4):
    pad = " " * n
    return "\n".join(pad + line for line in text.splitlines())

def format_steps_comment(steps):
    if not steps:
        return ""
    lines = []
    for i, s in enumerate(steps, 1):
        if isinstance(s, dict):
            action = s.get("action", s.get("step", ""))
            exp = s.get("expected", "")
            lines.append(f"# Step {i}: {action}")
            if exp:
                lines.append(f"#   -> expect: {exp}")
        else:
            lines.append(f"# Step {i}: {s}")
    return "\n".join(lines)

def format_precond_comment(preconditions):
    if not preconditions:
        return ""
    lines = ["# Preconditions:"]
    if isinstance(preconditions, list):
        for p in preconditions:
            lines.append(f"#   - {p}")
    else:
        lines.append(f"#   {preconditions}")
    return "\n".join(lines)


# ─────────────────────────────────────────────
#  Detect mode
# ─────────────────────────────────────────────

HTTP_METHODS = {"GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"}

def detect_mode(data):
    """Return 'api' or 'ui'."""
    source = str(data.get("source", "")).upper()
    # Check for HTTP method prefix (e.g. "POST /api/v1/login")
    first_word = source.split()[0] if source.split() else ""
    if first_word in HTTP_METHODS:
        return "api"
    # Check for URL
    src_lower = str(data.get("source", "")).lower()
    if src_lower.startswith("http://") or src_lower.startswith("https://"):
        return "ui"
    # Check case types
    all_types = " ".join(
        str(tc.get("type", "")) for tc in data.get("test_cases", [])
    )
    if "UI" in all_types or "页面" in all_types:
        return "ui"
    return "api"

def parse_api_info(source):
    """Parse 'POST /api/v1/users' → (method, path)."""
    parts = source.strip().split(None, 1)
    if len(parts) == 2 and parts[0].upper() in HTTP_METHODS:
        return parts[0].upper(), parts[1]
    return "GET", source


# ─────────────────────────────────────────────
#  API test generation
# ─────────────────────────────────────────────

API_CONFTEST = '''\
import pytest
import requests
import os

BASE_URL = os.getenv("TEST_BASE_URL", "http://localhost:8080")
API_TOKEN = os.getenv("TEST_API_TOKEN", "")

@pytest.fixture(scope="session")
def base_url():
    return BASE_URL.rstrip("/")

@pytest.fixture(scope="session")
def auth_headers():
    if API_TOKEN:
        return {"Authorization": f"Bearer {API_TOKEN}"}
    return {}

@pytest.fixture(scope="session")
def session(auth_headers):
    s = requests.Session()
    s.headers.update(auth_headers)
    return s
'''

def build_api_test_method(tc, method, path):
    tc_id    = tc.get("id", "")
    name     = tc.get("name", "")
    priority = tc.get("priority", "中")
    steps    = tc.get("steps", [])
    precond  = tc.get("preconditions", [])
    expected = tc.get("expected_result", "")

    func_name = f"test_{slugify(tc_id)}_{slugify(name)}"[:80]

    # Try to extract expected status code from steps or expected_result
    status_codes = re.findall(r"\b([1-5]\d{2})\b", str(steps) + str(expected))
    expected_status = status_codes[0] if status_codes else "200"

    lines = []
    lines.append(f"def {func_name}(self, session, base_url):")
    lines.append(f'    """')
    lines.append(f'    [{tc_id}] {name}')
    lines.append(f'    Priority: {priority}')
    if expected:
        lines.append(f'    Expected: {expected}')
    lines.append(f'    """')

    precond_comment = format_precond_comment(precond)
    if precond_comment:
        for line in precond_comment.splitlines():
            lines.append(f"    {line}")

    steps_comment = format_steps_comment(steps)
    if steps_comment:
        lines.append("    # --- Steps ---")
        for line in steps_comment.splitlines():
            lines.append(f"    {line}")

    lines.append(f"    url = f\"{{base_url}}{path}\"")

    # Build request body template from step action hints
    step_texts = " ".join(
        (s.get("action", "") if isinstance(s, dict) else str(s)) for s in steps
    )
    # Only treat as JSON if it contains key:value pairs (has a colon inside braces)
    json_match = re.search(r"\{[^{}]*:[^{}]*\}", step_texts)
    if json_match:
        lines.append(f"    payload = {json_match.group()}  # TODO: adjust payload")
    else:
        lines.append(f"    payload = {{}}  # TODO: fill request body")

    lines.append(f"    response = session.{method.lower()}(url, json=payload)")
    lines.append(f"    assert response.status_code == {expected_status}, \\")
    lines.append(f"        f\"Expected {expected_status}, got {{response.status_code}}: {{response.text}}\"")
    lines.append(f"    # TODO: add more assertions based on response body")
    lines.append(f"    return response")

    return "\n".join(lines)


def generate_api_tests(data, out_dir):
    suite_name = data.get("name", "TestSuite")
    source     = data.get("source", "")
    cases      = data.get("test_cases", [])
    method, path = parse_api_info(source)

    class_name = "Test" + re.sub(r"[^a-zA-Z0-9]", "", suite_name) or "TestSuite"
    slug       = slugify(suite_name).lower()
    out_file   = Path(out_dir) / f"test_{slug}.py"

    lines = []
    lines.append(f'"""')
    lines.append(f'Auto-generated API tests for: {suite_name}')
    lines.append(f'Source   : {source}')
    lines.append(f'Generated: {datetime.now().strftime("%Y-%m-%d %H:%M")}')
    lines.append(f'"""')
    lines.append("")
    lines.append("import pytest")
    lines.append("")
    lines.append("")
    lines.append(f"class {class_name}:")
    lines.append(f'    """Tests for {source}"""')
    lines.append("")

    for tc in cases:
        method_tc = tc.get("method", method)  # case-level method override
        path_tc   = tc.get("path", path)
        body = build_api_test_method(tc, method_tc, path_tc)
        for line in body.splitlines():
            lines.append("    " + line)
        lines.append("")

    content = "\n".join(lines)
    out_file.write_text(content, encoding="utf-8")
    return str(out_file)


# ─────────────────────────────────────────────
#  UI test generation (Playwright)
# ─────────────────────────────────────────────

UI_CONFTEST = '''\
import pytest
from playwright.sync_api import sync_playwright, Page
import os

BASE_URL = os.getenv("TEST_BASE_URL", "http://localhost:3000")

@pytest.fixture(scope="session")
def browser():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        yield browser
        browser.close()

@pytest.fixture
def page(browser) -> Page:
    context = browser.new_context()
    page = context.new_page()
    yield page
    context.close()

@pytest.fixture
def base_url():
    return BASE_URL.rstrip("/")
'''

def build_ui_test_method(tc, source_url):
    tc_id    = tc.get("id", "")
    name     = tc.get("name", "")
    priority = tc.get("priority", "中")
    steps    = tc.get("steps", [])
    precond  = tc.get("preconditions", [])
    expected = tc.get("expected_result", "")

    func_name = f"test_{slugify(tc_id)}_{slugify(name)}"[:80]

    lines = []
    lines.append(f"def {func_name}(self, page, base_url):")
    lines.append(f'    """')
    lines.append(f'    [{tc_id}] {name}')
    lines.append(f'    Priority: {priority}')
    if expected:
        lines.append(f'    Expected: {expected}')
    lines.append(f'    """')

    precond_comment = format_precond_comment(precond)
    if precond_comment:
        for line in precond_comment.splitlines():
            lines.append(f"    {line}")

    # Determine page path
    try:
        from urllib.parse import urlparse
        parsed = urlparse(source_url)
        page_path = parsed.path or "/"
    except Exception:
        page_path = "/"

    lines.append(f"    page.goto(f\"{{base_url}}{page_path}\")")
    lines.append(f"    page.wait_for_load_state('networkidle')")
    lines.append("")

    # Convert steps to Playwright actions
    for i, step in enumerate(steps, 1):
        if isinstance(step, dict):
            action  = step.get("action", "")
            exp     = step.get("expected", "")
        else:
            action, exp = str(step), ""

        lines.append(f"    # Step {i}: {action}")

        action_lower = action.lower()
        if any(k in action_lower for k in ["点击", "click", "按钮", "button"]):
            lines.append(f"    # page.click('selector')  # TODO: update selector")
        elif any(k in action_lower for k in ["输入", "填写", "fill", "input"]):
            lines.append(f"    # page.fill('selector', 'value')  # TODO: update selector & value")
        elif any(k in action_lower for k in ["选择", "select"]):
            lines.append(f"    # page.select_option('selector', 'value')  # TODO")
        elif any(k in action_lower for k in ["检查", "验证", "断言", "assert", "expect"]):
            lines.append(f"    # expect(page.locator('selector')).to_be_visible()  # TODO")
        else:
            lines.append(f"    pass  # TODO: implement step")

        if exp:
            lines.append(f"    # Expected: {exp}")
        lines.append("")

    lines.append(f"    # Final assertion: {expected}")
    lines.append(f"    # TODO: add assertions")

    return "\n".join(lines)


def generate_ui_tests(data, out_dir):
    suite_name = data.get("name", "TestSuite")
    source     = data.get("source", "")
    cases      = data.get("test_cases", [])

    class_name = "Test" + re.sub(r"[^a-zA-Z0-9]", "", suite_name) or "TestSuite"
    slug       = slugify(suite_name).lower()
    out_file   = Path(out_dir) / f"test_{slug}.py"

    lines = []
    lines.append(f'"""')
    lines.append(f'Auto-generated Playwright UI tests for: {suite_name}')
    lines.append(f'Source   : {source}')
    lines.append(f'Generated: {datetime.now().strftime("%Y-%m-%d %H:%M")}')
    lines.append(f'"""')
    lines.append("")
    lines.append("import pytest")
    lines.append("from playwright.sync_api import expect")
    lines.append("")
    lines.append("")
    lines.append(f"class {class_name}:")
    lines.append(f'    """UI tests for {source}"""')
    lines.append("")

    for tc in cases:
        body = build_ui_test_method(tc, source)
        for line in body.splitlines():
            lines.append("    " + line)
        lines.append("")

    content = "\n".join(lines)
    out_file.write_text(content, encoding="utf-8")
    return str(out_file)


# ─────────────────────────────────────────────
#  Main
# ─────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print("Usage: python generate_pytest.py <input.yaml> [output_dir]")
        sys.exit(1)

    yaml_path = sys.argv[1]
    out_dir   = sys.argv[2] if len(sys.argv) > 2 else str(Path(yaml_path).parent)
    Path(out_dir).mkdir(parents=True, exist_ok=True)

    data = load_yaml(yaml_path)
    mode = detect_mode(data)

    print(f"[INFO] Detected mode: {mode.upper()}")

    # Write conftest.py
    conftest_path = Path(out_dir) / "conftest.py"
    if not conftest_path.exists():
        conftest_content = API_CONFTEST if mode == "api" else UI_CONFTEST
        conftest_path.write_text(conftest_content, encoding="utf-8")
        print(f"[OK]   conftest.py  -> {conftest_path}")

    # Generate test file
    if mode == "api":
        test_file = generate_api_tests(data, out_dir)
    else:
        test_file = generate_ui_tests(data, out_dir)

    print(f"[OK]   Test file    -> {test_file}")
    print(f"\nInstall deps and run:")
    if mode == "api":
        print(f"  pip install pytest requests")
    else:
        print(f"  pip install pytest playwright && playwright install chromium")
    print(f"  pytest {test_file} -v --tb=short")
    print(f"  # Or use run_and_report.py for HTML report")


if __name__ == "__main__":
    main()
