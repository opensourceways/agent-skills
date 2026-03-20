---
name: test-case-generator
description: 根据网址、需求文档或接口文档，自动分析并生成完整测试用例集，输出 YAML 和 Excel 两种格式文件。适用场景：(1) 给定 URL 地址，分析页面功能并生成 UI/功能测试用例；(2) 给定 REST API / Swagger / OpenAPI 文档，生成接口测试用例；(3) 给定需求文档（PRD / 功能描述），拆解功能点并生成测试用例集。触发词：生成测试用例、写测试用例、测试用例文档、test case、接口测试、页面测试用例、用例集。
---

# 测试用例生成器

## 工作流程

```
输入（URL / 需求文档 / 接口文档）
    ↓
Step 1: 分析输入，提取所有功能点/接口
    ↓
Step 2: 按模块组织，设计测试用例（覆盖正向/异常/边界/权限）
    ↓
Step 3: 输出 YAML 文件（test_cases.yaml）
    ↓
Step 4: 运行脚本，生成 Excel 文件（test_cases.xlsx）
```

---

## Step 1: 分析输入

### 输入类型识别

| 输入类型 | 分析重点 |
|----------|----------|
| **URL（页面）** | 访问页面，识别表单、按钮、列表、交互元素，抓取页面结构 |
| **REST API 文档** | 逐接口分析：method、path、请求参数、响应码、业务逻辑 |
| **Swagger/OpenAPI** | 解析所有 endpoint，提取 schema、required 字段、enum 值 |
| **需求文档/PRD** | 拆解功能点，识别核心流程、异常流程、业务规则 |

若给定 URL，使用浏览器工具访问页面获取实际内容后再设计用例。

---

## Step 2: 设计测试用例

**每个功能点/接口必须覆盖以下维度（酌情取舍）：**

1. **正向** - 合法输入，验证功能正常
2. **异常/负向** - 非法参数、缺少必填、类型错误
3. **边界值** - 最大/最小值、临界长度
4. **权限** - 未登录、token 过期、越权访问
5. **业务规则** - 状态流转、业务约束条件

**每条用例必须标注 `automatable` 字段**，判断规则如下：

| 值 | 含义 | 适用场景 |
|----|------|----------|
| `是` | 可完全自动化 | API 接口测试、有明确输入输出的功能测试、边界/异常测试、冒烟测试、集成测试 |
| `否` | 必须手动执行 | 需人工判断的 UI 视觉验证、易用性/体验评估、探索性测试、验证码/人机验证 |
| `部分` | 部分可自动化 | 兼容性测试（自动化跑流程+人工验视觉）、安全测试（自动化扫描+人工渗透）、含主观判断步骤的 UI 测试 |

格式规范和示例：详见 `references/test_case_format.md`

---

## Step 3: 输出 YAML 文件

将所有用例按以下结构输出为 `.yaml` 文件，并保存到当前工作目录：

```yaml
name: "<测试套件名称>"
version: "1.0"
created_at: "<今日日期>"
source: "<输入来源>"
test_cases:
  - id: TC-001
    module: "<模块名>"
    name: "<用例名称>"
    type: "<用例类型>"        # 功能测试/边界测试/异常测试/UI测试/安全测试等
    priority: "<优先级>"      # 高/中/低
    automatable: "<是/否/部分>"  # 是=可自动化，否=需手动，部分=部分可自动化
    preconditions:
      - "<前置条件>"
    steps:
      - step: 1
        action: "<操作步骤>"
        expected: "<步骤预期>"
    expected_result: "<整体预期结果>"
    actual_result: ""
    status: "未执行"
    remarks: ""
```

文件名建议：`<功能名称>_test_cases.yaml`

---

## Step 4: 生成 Excel 文件

YAML 文件输出完成后，立即运行以下脚本生成 Excel：

```bash
python <skill目录>/scripts/generate_excel.py <yaml文件路径> [excel输出路径]
```

**示例：**
```bash
python test-case-generator/scripts/generate_excel.py ./user_login_test_cases.yaml
```

脚本会自动在同目录生成同名 `.xlsx` 文件，包含两个 sheet：
- **测试用例**：所有用例详情，含颜色标注优先级、隔行底色
- **统计汇总**：按优先级、类型、模块的数量统计

> **依赖**：脚本会自动安装 `openpyxl` 和 `pyyaml`（如未安装）

---

## 输出规范

- YAML 和 Excel **保存到用户当前工作目录**（或用户指定目录）
- 文件名前缀反映被测对象，如 `login_api_test_cases.yaml`
- 完成后告知用户两个文件的**完整路径**
- **用例数量**：根据功能复杂度自动判断，通常每个接口/功能点至少 3-5 条用例
- 优先保证核心流程覆盖，再补充边缘场景

## 参考资料

- 测试用例字段格式、类型枚举、完整示例：见 `references/test_case_format.md`
