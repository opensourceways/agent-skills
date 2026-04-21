---
name: github-action-diagnose
description: GitHub Action CI 失败自动诊断，专为昇腾（Ascend）NPU 集群（ARC/K8s）基础设施设计。当用户提到 CI 失败、流水线挂掉、CI 报错、构建失败、测试失败、PR CI 不过、CI 排队超时、nightly 失败、runner 异常等情况时立即触发。自动分析日志、定位物理节点、分类根因（基础设施/代码Bug/精度回归）、识别责任方，将诊断报告写入文件。即使用户只是粘贴了一段错误日志或 CI 链接，也应触发此 skill。
compatibility:
  tools:
    - Bash
    - Read
    - Write
    - Glob
    - Grep
---

# CI 故障自动诊断 Skill

## 使用场景

- Ascend NPU 集群（ARC/K8s）上的 GitHub Actions 运行失败
- PR CI 不过、nightly 任务失败、runner 异常等需要快速定位根因的场景
- 区分故障责任方：基础设施团队（环境/硬件）vs PR 作者（代码/精度）

## 前置要求

- `gh` CLI 已安装并已完成 GitHub 认证（`gh auth login`）
- 有目标仓库的读权限（用于拉取 run 日志）
- `kubectl` 已配置（用于物理节点溯源，无权限时跳过该步骤）

## 核心原则

- **静默执行**：直接运行所有只读操作（`gh` CLI、日志读取、`kubectl` 查询），不要逐步询问权限
- **先跑后说**：收集完所有信息后，一次性生成完整报告
- **直接输出**：诊断结果直接在对话中输出，不写入文件（Action Plan JSON 除外）
- **责任明确**：每个问题必须标注责任方（基础设施团队 / PR 作者）
- **仅在变更操作前确认**：修改代码、提交 commit、执行 `kubectl delete/patch` 才需询问

---

## Step 0：解析用户输入并确定诊断范围

根据用户输入确定诊断范围：

| 输入类型 | 示例 | 诊断范围 |
|---------|------|---------|
| Run ID | `23282406275` | 诊断 Run 中所有失败的 Job |
| Run URL | `github.com/.../actions/runs/23282406275` | 诊断 Run 中所有失败的 Job |
| Job URL | `github.com/.../actions/runs/.../jobs/xxx` | **只诊断这一个 Job** |

> **重要**：如果用户提供了具体的 Job URL，**只分析这一个 Job**，不要去拉取整个 Run 的其他 Job 日志。这是为了节省时间和 token。

---

## Step 1：静默收集上下文

### 1a. 确定诊断范围

- **如果用户提供了 Job URL**：直接使用该 Job ID，跳过 Run 级别分析
- **如果用户提供了 Run ID/URL**：分析该 Run 中所有失败的 Job

### 1b. 收集日志

**必须使用脚本获取日志**，不要直接用 `gh run view --job <id> --log`，原因：
1. 日志可能很大（几百MB），导致 API 超时或工具调用被中断
2. tiling 编译警告会淹没真正的根因错误
3. 脚本已内置预过滤逻辑，只输出关键错误行

**Job URL 场景（只诊断单个 Job）**：
```bash
bash <skill目录>/scripts/fetch-run.sh --job <job_id> [owner/repo]
# 例如：bash scripts/fetch-run.sh --job 68954806226 vllm-project/vllm-ascend
# 或（无 bash 环境时）：python scripts/fetch_run.py --job 68954806226 vllm-project/vllm-ascend
```

**Run ID/URL 场景（诊断所有失败 Job）**：
```bash
bash <skill目录>/scripts/fetch-run.sh <run_id> [owner/repo]
# 例如：bash scripts/fetch-run.sh 23326177540
# 或（无 bash 环境时）：python scripts/fetch_run.py --run 23326177540
# 默认 repo 为 vllm-project/vllm-ascend
```

**Run ID/URL 场景（诊断所有失败 Job）**：
```bash
python <skill目录>/scripts/fetch_run.py --run <run_id> [owner/repo]
# 例如：python scripts/fetch_run.py --run 23326177540
# 或：   bash scripts/fetch-run.sh 23326177540
# 默认 repo 为 vllm-project/vllm-ascend
```

**脚本输出内容**：
- Runner 名称、起止时间、结论
- 失败步骤列表（哪个 step 挂了）
- Annotations（通常直接揭示根因，如 ETIMEDOUT / exit code）
- Annotations 已明确根因时自动跳过日志拉取
- 预过滤的运行时错误（RuntimeError/AssertionError/EngineDeadError/OOM 等）
- 预过滤的编译/安装错误（依赖冲突、git dubious ownership 等）
- PR 变更文件列表

脚本位置：`<skill目录>/scripts/fetch_run.py`（Python，跨平台）或 `<skill目录>/scripts/fetch-run.sh`（Bash）

**Step 1c：依赖解析错误优先检查（Install 阶段失败时必做）**

脚本日志不足以定位根因时，**优先使用 Step 1d 中的依赖专用命令**搜索依赖解析错误，这是最容易被遗漏的根因：

**为什么重要**：依赖不可用（如 `modelscope==1.35.1` 不存在）会导致后续所有步骤连锁失败，日志中会出现大量 "error"、"failed"，但真正的根因只在依赖解析步骤的开头。

### Step 1d. 按需补充的命令（脚本输出不足以定位根因时才用）

> **脚本已内置以下逻辑，90% 场景无需手动补充命令：**
> - 失败步骤列表（哪个 step 挂了）
> - Annotations（ETIMEDOUT / exit code 等直接结论）
> - Annotations 已明确根因时自动跳过日志拉取
> - PR 变更文件列表

仅在脚本输出仍不足以定位根因时，才手动补充：

```bash
# 依赖解析错误专用
gh run view --job <job_id> --log --repo <owner/repo> | grep -iE "unsatisfiable|No solution found|no version of|modelscope.*error"
```

### Step 1e. 集群日志查询（MCP，当 GitHub 日志不足时）

当 GitHub Actions 日志不足以定位根因（如只显示 exit code 1 但无具体错误），可使用 MCP 查询 LTS 集群日志：

```bash
# 一键获取 Runner Pod 日志
mcp_get_runner_logs(runner_name="linux-aarch64-a3-0-ggwx6-runner-qbq72", start="2026-03-27 21:20:00", end="2026-03-27 22:00:00")

# 或分步调用：
mcp_list_pods(namespace="vllm-project", start="...", end="...")
mcp_export_logs(namespace="vllm-project", pod_name="...", keywords="RuntimeError|OOM", start="...", end="...")
mcp_get_export(export_id="...")
```

**MCP 服务地址**：`http://150.158.143.223:30089/mcp`
**默认日志源**：`ascend-ci-log`
**默认 namespace**：`vllm-project`（与仓库名对应）

---

## Step 2：生命周期快速分诊

根据**失败发生的步骤**做初步判断：

| 失败步骤 | 初步定性 |
|---------|---------|
| `Set up job` | 基础设施 — Runner 调度失败 |
| `Initialize containers` | 基础设施 — 容器运行时异常 |
| `Checkout` / `Install dependencies` | 基础设施 — 网络/挂载/权限 |
| `Run test` / `Build` | **需同时执行 Step 3 和 Step 4**，不可只做其中之一 |

> **重要**：失败在 `Run test` / `Build` 阶段时，必须同时检查环境故障（Step 3）和代码问题（Step 4），不因"看起来是代码问题"而跳过环境检查，也不因"多 Job 同时失败"而跳过代码检查。

**多个 Job 同步以相同步骤失败 → 强烈的基础设施信号**，但仍需完成代码侧的快速排查。

---

## Step 3：物理节点溯源（A 类必做，Run step 失败时也应尝试）

### 3a. 获取 runner_name

从 `Set up job` 日志或 API 获取，格式通常为：
```
linux-aarch64-a3-2-x51bm-runner-ksnwc
         ↑节点池  ↑物理机编号   ↑pod随机后缀
```

### 3b. 定位 Namespace

```bash
# 自动发现 runner pod 所在 namespace（不确定时使用）
kubectl get pods --all-namespaces | grep <runner_name>
```

### 3c. 查物理节点（区分两种场景）

**Pod 未销毁**：
```bash
kubectl get pod <runner_name> -n <namespace> \
  -o custom-columns=NODE:.spec.nodeName
```

**Pod 已销毁**：从完整日志中搜索调度记录：
```bash
# 先拉完整日志
gh run view --job <job_id> --log --repo <owner/repo> > full.log
grep "Successfully assigned <runner_name> to" full.log
# 或在 Loki/ELK 中搜索相同关键词
```

### 3d. 多机任务 — 优先定位 Master 节点（Rank 0）

当任务涉及多机（multi-node）且某节点报 `Timeout` 时，**不要孤立分析报错节点**，先找 Rank 0：

```bash
# 方法一：从日志中找 MASTER_ADDR 环境变量
grep "MASTER_ADDR" full.log

# 方法二：从 RANK_TABLE_FILE 中找 rank_id=0 对应的 device_ip
grep -A5 '"rank_id": "0"' <rank_table_file>
```

找到 Master 节点后，优先检查其日志：
- 是否有 `Unexpected Exit`
- 是否有 NPU 驱动报错（`ERR99999`、`error code 507035`）
- 是否有进程崩溃（exit `-9`、`Bus error`）

Master 有问题 → 从节点只是连锁超时，根因在 Master。

### 3e. 确认 NPU 健康

```bash
npu-smi info  # 在对应节点上执行
kubectl get nodes --kubeconfig=<集群kubeconfig>
```

---

## Step 4：根因分类

### 类型 A：基础设施 / 环境故障
信号：容器启动失败、网络超时、NPU 硬件报错（`ERR99999`）、OOM（`Bus error` / `Killed` / exit `-9`）、exit code 255（K8s 强制终止）、ModelScope 下载超时、多机 Timeout（见 Step 3d）、`shm_broadcast` 超时 + `EngineDeadError`（Nightly 资源调度不稳定，见 `references/common-patterns.md`）

**责任方**：基础设施团队

### 类型 B：代码 Bug（PR 引入）
信号：exit code 1、Python 异常堆栈（`UnboundLocalError` / `AssertionError` / `AttributeError`）、失败与 PR diff 直接对应、重跑仍失败、UT 卡死

**责任方**：PR 作者

### 类型 C：精度回归
信号：`Accuracy of ... is X, lower than Y`、精度跌幅 > 5%

**责任方**：PR 作者（需与算法团队确认）

### 类型 D：YAML / 配置错误
信号：`undefined variable "False"`、workflow 语法报错

**责任方**：PR 作者 / CI 维护者

### 类型 E：疑难 / 概率性问题
信号：偶发挂死（如 triton ascend 概率挂）、无明确异常堆栈、重跑有时通过

**常见错误模式速查**：`references/common-patterns.md`
**vllm-ascend 专项**：`references/vllm-ascend.md`

---

## Step 5：输出报告

直接在对话中输出诊断结果，格式如下（每个失败 Job 一节）：

```
# CI 故障诊断报告

**Run**: [Workflow名称] #[Run ID]
**PR**: [仓库/PR号] ([分支名])
**时间**: [开始] ~ [结束]

---

## 故障一：[Job 名称]

- **定性**: [环境问题 / 代码Bug / 精度回归 / 配置错误 / 疑难]
- **根因**: [一句话直接原因，如"K8s 容器运行时在测试阶段强制终止，exit code 255"]
- **关键标识**: `[最关键的一行错误，如 ERR99999 / AssertionError / exit code 255]`
- **责任方**: [基础设施团队 / PR 作者]
- **建议**: [重跑 / 修改 XX 文件 XX 行 / 上报运维 / 检查 Master 节点 XX]
- **节点**: [仅硬件故障时填写：Runner Pod名 → 物理节点名，其他类型省略]

---

[其他 Job 以同样格式继续]
```

**输出精简原则**：
- 不粘贴大段原始日志，只引用最关键的一行错误标识
- 不描述诊断过程（不写"我们检查了A，发现B"），直接给结论
- 节点池、物理机等环境信息仅在硬件故障时填写，其他类型省略
- 若同一 Run 中多个 Job 根因相同，可合并为一条说明
- **不输出步骤分析表格，不输出汇总表格**

---

## Step 6：等待人工确认

输出诊断结果后停止，等待确认：
- "确认" / "没问题" → 生成 Action Plan（仅类型 B/C/D）
- 提出修正 → 在对话中重新输出修订后的诊断结果；若修正揭示了漏判或误判的模式，同步更新 `references/` 中对应的参考文件，防止下次重犯
- 基础设施问题 → 提供操作建议后结束，不执行代码修改

> **重要**：不要跳过 Step 6 等待确认，直接进入 Step 7

---

## Step 7：生成 Action Plan

用户确认后，生成结构化 Action Plan JSON 文件供后续 AI 修复使用。

> **注意**：只有代码 Bug/配置错误/精度回归 需要生成 Action Plan，基础设施问题不需要。

### Step 7.1：检查是否需要生成

| 问题类型 | 是否生成 Action Plan | 说明 |
|---------|-------------------|------|
| 类型 B（代码Bug） | ✅ 是 | PR 引入的 Bug，需要修改代码 |
| 类型 C（精度回归） | ✅ 是 | 需要调整参数或回滚 |
| 类型 D（YAML/配置错误） | ✅ 是 | 需要修改配置 |
| 类型 A（环境/基础设施） | ❌ 否 | 基础设施问题，不涉及代码修改 |
| 类型 E（疑难） | ❌ 否 | 偶发问题，重跑尝试 |

### Step 7.2：生成 JSON 文件

```
输出文件：<skill目录>/reports/action-plan-<run_id>.json
```

```json
{
  "run_id": "<run_id>",
  "pr": "<repo>#<pr_number>",
  "jobs_to_fix": [
    {
      "job_id": "<job_id>",
      "job_name": "<job name>",
      "issue_type": "code_bug|config_error|accuracy_regression",
      "root_cause": "<一句话描述>",
      "fix_actions": [
        {
          "type": "code_change",
          "file": "<文件路径>",
          "action": "modify|add|remove",
          "location": "<文件:行号 或 函数名>",
          "original": "<原内容（可选）>",
          "replacement": "<新内容>",
          "reason": "<为什么这么改>"
        }
      ],
      "verification": {
        "command": "<验证命令>",
        "expected": "<预期结果>"
      }
    }
  ]
}
```

### Step 7.3：验证 Action Plan

生成后，在对话中输出：
- Action Plan 已写入文件路径
- 总结每个 fix_action（文件、修改内容）

用户确认后执行实际代码修改。

---

## 参考资料

- **常见错误模式速查**：`references/common-patterns.md`（网络超时/容器崩溃/UT卡死/triton挂/NPU硬件等）
- **vllm-ascend 专用**：`references/vllm-ascend.md`（Runner 类型、内部服务、workflow 触发逻辑）
- **分类判断详细逻辑**：`references/classification-guide.md`

---

## 常见误判与规避

### 1. tiling 编译警告 ≠ 测试失败根因

**现象**：日志中大量 `Register tiling func failed`、`Get op tiling func failed`  
**实际情况**：这是 CANN SDK 在编译 optiling 时的 DEBUG 输出，属于正常行为  
**规避**：grep 时排除 tiling 相关模式，优先捕获 `RuntimeError`、`AssertionError`、`exit code 255`

### 2. 日志"淹没"问题

**现象**：高volume日志（如 tiling DEBUG）掩盖低volume但真正的根因  
**规避**：先按错误类型/阶段分离日志输出，高优先级错误（OOM/AssertionError）先展示

### 3. exit code 255 = K8s 终止

**现象**：测试实际已失败，但日志最后是 `command terminated with exit code 255`
**实际情况**：exit code 255 通常是 K8s 强制终止，说明测试进程已崩溃
**分析**：往前搜索 `RuntimeError`、`AssertionError` 找到真正失败原因

---

## 使用示例

### 示例 1：通过 GitHub Actions Run URL 诊断

```
/github-action-diagnose https://github.com/my-org/my-repo/actions/runs/12345678901
```

Skill 会自动提取 `owner/repo` 和 `run_id`，执行 `gh run view --log-failed`，进入完整诊断流程。

### 示例 2：通过 Run ID 诊断（在 repo 目录下）

```
/github-action-diagnose 12345678901
```

从当前目录推断 repo，然后执行诊断。

### 示例 3：直接粘贴日志内容

```
/github-action-diagnose
2024-01-15T10:23:45.123Z [error] npu-smi info: ERR99999 Device not found
2024-01-15T10:23:45.456Z [error] error code 507035
```

---

## 注意事项

- 本 skill 仅做故障**定性与根因分析**，不输出修复建议或操作手册
- 所有只读操作（`gh` CLI、`kubectl` 查询、日志读取）直接执行，无需用户确认
- 诊断报告中的物理节点信息依赖 `kubectl` 访问权限，无权限时跳过节点溯源步骤
- 参考资料位于 `references/` 目录，包括常见错误模式、vllm-ascend 专项说明、Ascend NPU 故障排查手册

## 相关 Skills

- [claude-bot](../claude-bot/claude.md) — GitHub Issues/PR 中的 AI 助手，可触发本诊断流程

---

## 更新日志

### v2.0.0 (2026-03-31)
- 重构诊断流程：扩展至 7 步（原 5 步），增加精度回归、代码 Bug、Action Plan 生成阶段
- 新增责任方标注（基础设施团队 / PR 作者）
- 新增 `references/` 参考资料目录（common-patterns、vllm-ascend、classification-guide、ascend-troubleshooting）
- 输出格式由纯报告改为结构化 Action Plan JSON（代码问题时）
- 新增常见误判规避说明（tiling 警告、日志淹没、exit code 255）

### v1.0.0 (2026-03-16)
- 初始版本：5 步诊断流程（输入识别 → 生命周期分诊 → 节点溯源 → 非环境判定 → 输出报告）
- 支持 URL / Run ID / 粘贴日志三种输入方式
- 支持基础设施故障（情况A）和非基础设施问题（情况B）两种输出模式

---

## 作者

- v1.0.0: @hdsong2
- v2.0.0: @zhangyang

## 最后更新

2026-03-31
