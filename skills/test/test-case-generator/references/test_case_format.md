# 测试用例格式规范

## YAML 格式结构

### 顶层结构

```yaml
name: "用例集名称"
version: "1.0"
created_at: "2024-01-01"
source: "来源（URL / 文档名）"
test_cases:
  - ...
```

### 单条用例字段

| 字段 | 必填 | 说明 |
|------|------|------|
| `id` | 是 | 用例ID，如 TC-001 |
| `module` | 是 | 所属模块/功能模块 |
| `name` | 是 | 用例名称，简洁描述测试点 |
| `type` | 是 | 用例类型（见下方枚举） |
| `priority` | 是 | 优先级：高/中/低 |
| `automatable` | 是 | 是否可自动化：是/否/部分（见下方判断规则） |
| `preconditions` | 否 | 前置条件列表 |
| `steps` | 是 | 测试步骤列表 |
| `expected_result` | 是 | 预期结果 |
| `actual_result` | 否 | 实际结果（执行后填写） |
| `status` | 否 | 执行状态，默认"未执行" |
| `remarks` | 否 | 备注 |

### 自动化可行性判断规则

根据用例类型和测试内容，按以下规则填写 `automatable`：

| 值 | 适用场景 |
|----|----------|
| `是` | API 接口测试、功能测试（有明确输入输出）、边界/异常测试、冒烟测试、集成测试、性能测试（脚本化） |
| `否` | 需人工主观判断的 UI 视觉验证、易用性/体验评估、探索性测试、验证码/人机验证、需实物操作的测试 |
| `部分` | 兼容性测试（自动跑流程 + 人工看视觉）、安全测试（自动扫描 + 人工渗透）、含主观判断步骤的 UI 测试 |

**快速判断口诀**：能写断言就填"是"，靠肉眼感觉填"否"，两者都有填"部分"。

### 用例类型枚举

- `功能测试` - 功能点正常/异常流程
- `边界测试` - 边界值、临界值
- `异常测试` - 异常输入、错误码验证
- `性能测试` - 响应时间、并发量
- `安全测试` - 权限、鉴权、注入攻击
- `兼容性测试` - 多端/多浏览器
- `UI测试` - 页面展示、交互
- `集成测试` - 接口联调
- `冒烟测试` - 核心流程快速验证

### 优先级说明

- `高` (P0/P1) - 核心功能、主流程、必须通过
- `中` (P2) - 重要功能、常见场景
- `低` (P3) - 边缘场景、次要功能

---

## 完整示例

### REST API 接口测试用例示例

```yaml
name: "用户登录接口测试"
version: "1.0"
created_at: "2024-01-15"
source: "POST /api/v1/auth/login"
test_cases:
  - id: TC-001
    module: "用户认证"
    name: "正常登录-用户名密码正确"
    type: "功能测试"
    priority: "高"
    automatable: "是"
    preconditions:
      - "系统服务正常运行"
      - "测试账号 test@example.com 已存在且状态正常"
    steps:
      - step: 1
        action: "发送 POST /api/v1/auth/login 请求，Body: {\"email\":\"test@example.com\",\"password\":\"Test@123\"}"
        expected: "HTTP 200 OK"
      - step: 2
        action: "检查响应体"
        expected: "包含 token 字段，code=0，message=\"success\""
    expected_result: "返回 HTTP 200，响应包含有效 JWT token，用户信息正确"
    status: "未执行"

  - id: TC-002
    module: "用户认证"
    name: "密码错误-返回401"
    type: "异常测试"
    priority: "高"
    automatable: "是"
    preconditions:
      - "系统服务正常运行"
    steps:
      - step: 1
        action: "发送 POST /api/v1/auth/login，密码填写错误值 wrongpassword"
        expected: "HTTP 401"
      - step: 2
        action: "检查响应体"
        expected: "code=401，message 包含'密码错误'或'认证失败'"
    expected_result: "返回 HTTP 401，不返回 token"
    status: "未执行"

  - id: TC-003
    module: "用户认证"
    name: "邮箱格式不合法"
    type: "边界测试"
    priority: "中"
    automatable: "是"
    steps:
      - step: 1
        action: "发送请求，email 字段传 'notanemail'"
        expected: "HTTP 400"
    expected_result: "返回 400，提示邮箱格式错误"
    status: "未执行"
```

### 页面/UI 测试用例示例

```yaml
name: "用户注册页面测试"
version: "1.0"
source: "https://example.com/register"
test_cases:
  - id: TC-001
    module: "注册页面"
    name: "页面正常加载"
    type: "UI测试"
    priority: "高"
    automatable: "是"
    steps:
      - step: 1
        action: "访问 /register 页面"
        expected: "页面加载完成，无报错"
      - step: 2
        action: "检查页面元素"
        expected: "显示用户名、密码、确认密码、邮箱输入框及注册按钮"
    expected_result: "页面正常渲染，所有必要元素可见"
    status: "未执行"
```

---

## 测试用例设计原则

### 覆盖维度

对每个接口/页面，确保覆盖以下维度：

1. **正向用例** - 合法输入，验证功能正常
2. **异常/负向用例** - 非法输入、缺少必填字段、类型错误
3. **边界值用例** - 最大值、最小值、临界值（如字符串长度限制）
4. **权限用例** - 未登录、越权访问、token 过期
5. **并发/性能用例**（如有性能要求）

### 接口测试重点

- 请求参数：必填/选填、类型、长度、格式
- 响应码：2xx/4xx/5xx 各场景
- 响应体：字段完整性、数据类型、业务逻辑
- 鉴权：token 有效/无效/过期/权限不足
- 幂等性：重复请求行为
- 分页接口：第一页/最后一页/越界页码

### 页面测试重点

- 页面加载与渲染
- 表单校验（前端校验）
- 按钮交互与状态变化
- 跳转逻辑
- 异常状态（网络错误、空数据）
- 响应式布局（如需）
