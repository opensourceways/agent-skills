---
name: github-action-diagnose
description: 诊断昇腾（Ascend）NPU 集群上 GitHub Actions 执行失败的原因，定位基础设施故障与根因分析
allowed-tools: Bash(gh run view:*), Bash(gh run list:*), Bash(gh api:*), Bash(kubectl get:*), Bash(kubectl describe:*), Bash(kubectl logs:*), Bash(kubectl config:*), Read, Grep
---

## Your task

诊断昇腾（Ascend）NPU 集群上 GitHub Actions 的执行失败。仅做故障定性和根因分析，不提供修复建议。
所有只读操作（gh CLI、kubectl 查询、日志读取）直接执行，无需用户确认。

本技能采用 5 步诊断流程：Step 0 输入识别 + 4 步诊断逻辑（生命周期分诊 → 物理节点溯源与环境故障定位 → 非环境问题判定 → 输出报告）。

### Step 0: 识别输入并获取日志

分析用户提供的输入，自动识别类型：

- **GitHub Actions Run URL**（包含 `/actions/runs/`）：提取 owner/repo 和 run_id，执行 `gh run view <run_id> --repo <owner/repo> --log-failed` 获取失败日志。
- **Run ID**（纯数字）：需要用户确认 repo 或从当前目录推断，然后执行 `gh run view <run_id> --log-failed`。
- **粘贴的日志内容**（非 URL 非纯数字）：直接作为日志内容进行分析。

如果 `--log-failed` 信息不足，自动尝试 `gh run view <run_id> --log` 获取完整日志。
同时获取 run 的元信息：`gh run view <run_id> --repo <owner/repo> --json jobs,name,status,conclusion,headBranch,event`。

### Step 1: 生命周期分诊

根据失败发生的步骤进行初步分类：

| 失败步骤 | 初步定性 | 说明 |
|----------|---------|------|
| Set up job | 环境问题 | Runner 无法拉起/调度失败 |
| Initialize containers | 环境问题 | 容器运行时异常/镜像拉取失败 |
| Checkout / Setup Environment | 环境问题 | 网络/挂载/权限故障 |
| Run steps（pytest/lint 等） | 需进一步分析 | Runner 已就绪，进入 Step 2-3 细分 |

如果失败在前三类步骤，直接标记为环境问题并进入 Step 2。
如果失败在 Run steps，需要同时执行 Step 2 和 Step 3 来区分环境故障与代码问题。

### Step 2: 物理节点溯源 + 环境故障深度定位

#### 2a. 物理节点溯源
当判定为环境故障或怀疑硬件问题时，定位物理节点：

1. 从 `Set up job` 日志或 `gh api` 获取 `runner_name`（即 Pod 名称）。
2. 从 `runner_name` 前缀或 Job Labels 识别节点池（如 `a3-0`）。
3. 自动发现 namespace：`kubectl get pods --all-namespaces --no-headers | grep <runner_name>` 提取 namespace。
4. 反查物理机：
   - Pod 未销毁：`kubectl get pod <runner_name> -n <namespace> -o custom-columns=NODE:.spec.nodeName --no-headers`
   - Pod 已销毁：在日志中搜索 `Successfully assigned <runner_name> to <node_name>`。

#### 2b. 环境故障深度定位
检查以下故障模式：

- **驱动/硬件失效**：`npu-smi info` 报错、`ERR99999`、`error code 507035`、`Device not found`。
- **资源溢出 (OOM)**：系统级 `Killed` 信号、`Bus error`（SHM 不足）、`No space left on device`。
- **多机连锁超时**：多机任务中某节点报 `Timeout`，优先识别并检查 Master 节点。Master 节点识别方法：
  - 检查 `RANK_TABLE_FILE` 中 `rank_id=0` 对应的节点
  - 或在日志中搜索 `master_addr` / `MASTER_ADDR` 环境变量指向的节点
  - 确认 Master 节点是否有 `Unexpected Exit` 或驱动报错

### Step 3: 非环境问题判定

如果 Step 2 未发现环境/硬件故障，检查以下非环境因素：

- **YAML 语法错误**：如 `undefined variable "False"`（应为小写 `false`）。
- **业务逻辑报错**：`AssertionError`、Python Traceback 指向业务源码、测试用例失败。
- **依赖问题**：pip/npm 安装失败但非网络原因（版本冲突、包不存在）。

### Step 4: 输出诊断报告

根据诊断结果选择输出模式：

#### 情况 A：确认为基础设施/硬件故障

严格按照以下格式输出：

```
# GitHub Action 故障诊断报告

## 1. 故障概览
- **任务名称**: [Job Name]
- **Run ID**: [Run ID]
- **故障定性**: 环境问题 / 硬件故障 / 集群调度异常
- **判定依据**: [驱动报错/调度异常/硬件死锁/OOM 等]

## 2. 详细诊断
- **失败步骤**: [Set up job / Initialize containers / Run steps 等]
- **报错原文**: [引用关键日志片段]
- **物理节点**: [Runner 名] -> [Pod] -> [物理机/节点池]
- **根因分析**: [深层原因说明]
```

#### 情况 B：环境正常，非基础设施问题

采用自然语言简要反馈：
1. **结论**：直接告知"未发现环境/基础设施故障"。
2. **依据**：简述分析了哪些环节（调度、镜像拉取、NPU 挂载等均正常）。

注意：两种情况均不输出修复建议或操作手册。
