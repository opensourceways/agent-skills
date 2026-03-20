# pytest 测试模式参考

## 目录
1. [API 测试模式](#api)
2. [UI 测试模式 (Playwright)](#ui)
3. [conftest.py 模式](#conftest)
4. [常用断言](#assertions)
5. [运行命令速查](#commands)

---

## 1. API 测试模式 {#api}

### 基本结构
```python
import pytest
import requests

class TestLoginAPI:
    def test_login_success(self, session, base_url):
        url = f"{base_url}/api/v1/auth/login"
        payload = {"email": "test@example.com", "password": "Test@123"}
        response = session.post(url, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert data["code"] == 0
```

### 参数化测试（覆盖多场景）
```python
@pytest.mark.parametrize("email,password,expected_code", [
    ("valid@test.com", "Valid@123", 200),
    ("valid@test.com", "wrongpwd",  401),
    ("notanemail",     "anypass",   400),
])
def test_login_parametrize(self, session, base_url, email, password, expected_code):
    resp = session.post(f"{base_url}/api/v1/auth/login",
                        json={"email": email, "password": password})
    assert resp.status_code == expected_code
```

### 鉴权测试
```python
def test_unauthorized_access(self, base_url):
    # No auth header
    resp = requests.get(f"{base_url}/api/v1/profile")
    assert resp.status_code == 401

def test_expired_token(self, base_url):
    headers = {"Authorization": "Bearer expired_token_here"}
    resp = requests.get(f"{base_url}/api/v1/profile", headers=headers)
    assert resp.status_code in (401, 403)
```

### 边界值测试（字段长度）
```python
def test_username_max_length(self, session, base_url):
    payload = {"username": "a" * 256, "password": "Valid@123"}
    resp = session.post(f"{base_url}/api/v1/register", json=payload)
    assert resp.status_code == 400
    assert "username" in resp.json().get("message", "").lower()
```

---

## 2. UI 测试模式 (Playwright) {#ui}

### 基本结构
```python
import pytest
from playwright.sync_api import expect

class TestLoginPage:
    def test_page_loads(self, page, base_url):
        page.goto(f"{base_url}/login")
        page.wait_for_load_state("networkidle")
        expect(page.locator("input[name='email']")).to_be_visible()
        expect(page.locator("button[type='submit']")).to_be_visible()

    def test_login_success(self, page, base_url):
        page.goto(f"{base_url}/login")
        page.fill("input[name='email']", "test@example.com")
        page.fill("input[name='password']", "Test@123")
        page.click("button[type='submit']")
        page.wait_for_url("**/dashboard")
        expect(page.locator(".user-avatar")).to_be_visible()
```

### 截图与调试
```python
def test_with_screenshot(self, page, base_url):
    page.goto(f"{base_url}/login")
    page.screenshot(path="screenshots/login_page.png")
    # ... test steps
    page.screenshot(path="screenshots/after_login.png")
```

### 网络拦截（模拟接口）
```python
def test_with_mock_api(self, page, base_url):
    page.route("**/api/v1/auth/login", lambda route: route.fulfill(
        status=200,
        body='{"token": "mock_token", "code": 0}',
        headers={"Content-Type": "application/json"}
    ))
    page.goto(f"{base_url}/login")
    page.fill("input[name='email']", "any@test.com")
    page.click("button[type='submit']")
    expect(page.locator(".dashboard")).to_be_visible()
```

---

## 3. conftest.py 模式 {#conftest}

### API conftest
```python
import pytest, requests, os

@pytest.fixture(scope="session")
def base_url():
    return os.getenv("TEST_BASE_URL", "http://localhost:8080")

@pytest.fixture(scope="session")
def auth_token(base_url):
    resp = requests.post(f"{base_url}/api/v1/auth/login",
                         json={"email": "admin@test.com", "password": "Admin@123"})
    return resp.json()["token"]

@pytest.fixture(scope="session")
def session(auth_token):
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {auth_token}"})
    return s
```

### Playwright conftest
```python
import pytest
from playwright.sync_api import sync_playwright

@pytest.fixture(scope="session")
def browser():
    with sync_playwright() as p:
        yield p.chromium.launch(headless=True)

@pytest.fixture
def page(browser):
    context = browser.new_context(viewport={"width": 1280, "height": 720})
    page = context.new_page()
    yield page
    context.close()
```

---

## 4. 常用断言 {#assertions}

```python
# HTTP 状态码
assert response.status_code == 200
assert response.status_code in (200, 201)

# 响应体字段
data = response.json()
assert data["code"] == 0
assert "token" in data
assert data["user"]["email"] == "test@example.com"
assert len(data["items"]) > 0

# Playwright 元素
expect(page.locator("h1")).to_have_text("欢迎登录")
expect(page.locator(".error-msg")).to_be_visible()
expect(page.locator("input[name='email']")).to_be_enabled()
expect(page.locator(".loading")).not_to_be_visible()
```

---

## 5. 运行命令速查 {#commands}

```bash
# 安装依赖（API 测试）
pip install pytest requests pytest-json-report

# 安装依赖（UI 测试）
pip install pytest playwright pytest-json-report
playwright install chromium

# 运行全部测试
pytest tests/ -v

# 只运行某个优先级（需要给测试加 mark）
pytest tests/ -m "high_priority" -v

# 运行后生成 HTML 报告
python run_and_report.py tests/test_login.py report.html

# 设置环境变量
export TEST_BASE_URL=http://your-server:8080
export TEST_API_TOKEN=your_token_here
```
