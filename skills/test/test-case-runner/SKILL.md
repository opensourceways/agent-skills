---
name: test-case-runner
description: 读取测试用例文件（YAML格式），自动生成 Python pytest 自动化测试脚本，执行测试并输出 HTML 格式的可视化测试报告。适用场景：(1) 给定测试用例 YAML 文件，生成 pytest 自动化脚本；(2) 执行已有 pytest 测试文件并生成 HTML 报告；(3) 端到端完成：YAML 用例 → pytest 脚本 → 执行 → HTML 报告。触发词：执行测试用例、运行测试、生成测试脚本、自动化测试脚本、生成测试报告、pytest、HTML报告、test report。支持 API 接口测试（requests）和 UI 页面测试（Playwright），自动识别类型。
---

# 测试用例执行器

## 工作模式

根据用户提供的内容选择对应模式：

| 输入 | 执行路径 |
|------|----------|
| YAML 测试用例文件 | 生成 pytest 脚本 → 执行 → HTML 报告（完整流程） |
| 已有 pytest .py 文件 | 直接执行 → HTML 报告 |
| 仅需生成脚本 | 只运行 Step 1，不执行测试 |

---

## Step 1: 生成 pytest 脚本

**从 YAML 测试用例文件生成 pytest 脚本：**

```bash
python <skill目录>/scripts/generate_pytest.py <test_cases.yaml> [output_dir]
```

脚本自动识别测试类型：
- **API 模式**：`source` 字段以 HTTP 方法开头（`POST /api/v1/...`）→ 使用 `requests`
- **UI 模式**：`source` 字段为 URL（`https://...`）或用例 type 含 "UI" → 使用 `Playwright`

**输出文件：**
- `test_<套件名>.py` — 主测试类文件
- `conftest.py` — 共享 fixture（仅在不存在时生成，避免覆盖）

> 生成的测试文件含 `# TODO` 注释，提示用户补充 payload、选择器等具体值。
> 若用户需要填充细节，读取 `references/pytest_patterns.md` 获取代码模式。

---

## Step 2: 执行测试并生成 HTML 报告

```bash
python <skill目录>/scripts/run_and_report.py <test_file_or_dir> [report.html]
```

**执行流程：**
1. 自动安装 `pytest-json-report`（用于捕获结构化结果）
2. 运行 pytest，收集 pass/fail/error/skip 结果
3. 生成自包含 HTML 报告（无需额外依赖可直接浏览器打开）

**报告内容：**
- 统计卡片：总数、通过、失败、错误、跳过
- 彩色进度条（通过率可视化）
- 每条用例的状态、耗时、失败详情（可展开）
- 控制台输出（带颜色高亮）

---

## Step 3: 完整流程示例

```bash
# 1. 生成测试脚本
python test-case-runner/scripts/generate_pytest.py ./login_test_cases.yaml ./tests/

# 2. 安装依赖（API 测试）
pip install pytest requests

# 3. 配置环境（设置被测服务地址）
export TEST_BASE_URL=http://your-server:8080

# 4. 执行测试 + 生成 HTML 报告
python test-case-runner/scripts/run_and_report.py ./tests/ ./test_report.html
```

完成后告知用户：
- pytest 脚本文件的完整路径
- HTML 报告的完整路径
- 测试结果摘要（总数/通过/失败）

---

## 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `TEST_BASE_URL` | 被测服务基础地址 | `http://localhost:8080` |
| `TEST_API_TOKEN` | API 鉴权 token（API 测试用） | 空 |

---

## 依赖安装

```bash
# API 测试
pip install pytest requests pytest-json-report

# UI 测试（Playwright）
pip install pytest playwright pytest-json-report
playwright install chromium
```

## 参考资料

- pytest 代码模式、参数化、conftest 写法：见 `references/pytest_patterns.md`
