# 问题分类判断树

分类体系与 SKILL.md 保持一致：**类型 A**（基础设施）/ **类型 B**（代码Bug）/ **类型 C**（精度回归）/ **类型 D**（配置错误）/ **类型 E**（疑难）

---

## 第一步：失败发生在哪个阶段？

| 失败步骤 | 初步定性 |
|---------|---------|
| `Set up job` / `Initialize containers` | **类型 A** — 直接归基础设施，无需看日志 |
| `Checkout` / `Install dependencies` | **倾向类型 A**，但需确认是网络还是版本号写错（见场景 B） |
| `Stream logs` / `Upload logs` | **类型 A** — 测试本身可能已通过，是 Runner 与 GitHub 通信失败 |
| `Run test` / `Build` | **需同时排查 A 和 B**，不可只做其中之一 |

---

## 第二步：是类型 A 还是类型 B？（Run test/Build 阶段失败时）

**倾向类型 A（基础设施）的信号：**
- 多个 PR / 多个 Job 同时失败，且根因相同
- 重跑后通过
- 错误指向网络、存储、NPU 硬件（`ERR99999`）、OOM、exit code 255
- `shm_broadcast` 超时 + `EngineDeadError`（Nightly 调度不稳定）
- 无 Python 异常堆栈，进程被外部终止

**倾向类型 B（代码 Bug）的信号：**
- 有明确 Python 异常堆栈，且指向 PR 新增/修改的代码
- 重跑仍然失败（稳定复现）
- 其他 PR 没有同样的失败
- PR diff 与失败路径直接对应

**两者都有信号时 → 先排查 A，再排查 B**（基础设施问题可以掩盖代码问题，反之不成立）

---

## 第三步：细分类型

### 类型 C：精度回归
- 有明确精度数值报错：`Accuracy of ... is X, lower than Y`
- 跌幅 < 3%：先重跑确认是否 flaky
- 跌幅 > 5%：PR 引入功能性回归，检查推理路径改动

### 类型 D：配置/YAML 错误
- `undefined variable "False"`（YAML 大小写）
- workflow 语法报错（actionlint）
- 路径/权限配置错误

### 类型 E：疑难 / 概率性
- 无明确异常堆栈，进程静默挂死
- 重跑有时通过、有时挂
- 常见：triton ascend 概率挂、CPU offload 死锁

---

## 常见混淆场景

**场景 A：`AssertionError` 是代码 Bug 还是精度回归？**
- `AssertionError: Test0:` / `model_utils.py` 断言 → **类型 C**，精度回归
- `AssertionError` 指向功能逻辑（如形状不匹配、返回值错误）→ **类型 B**，代码 Bug

**场景 B：依赖失败 — 网络问题还是版本号写错？**
- `No solution found` / `no version of xxx==Y.Y.Y` → **类型 A**，版本不存在于镜像源（或写错）
- `connection refused` / 超时 → **类型 A**，网络/基础设施

**场景 C：NPU function error — 硬件还是代码兼容性？**
- `error code 507xxx` / `ERR99999` → **类型 A**，硬件/驱动故障
- `error code 107xxx`（如 107030）→ CANN runtime 参数非法，**不是硬件信号**；若发生在 `model init` 且 PR 是版本升级/main2main → **类型 B**（新版本 init 路径与 torch_npu 不兼容）

**场景 D：`EngineDeadError` — 代码 Bug 还是环境？**
- 伴随 `shm_broadcast` 60s 超时连续出现，且为 Nightly 任务 → **类型 A**，资源调度不稳定
- 启动阶段即崩溃，有明确 Python 堆栈 → **类型 B**

**场景 E：exit code 255**
- 通常是 K8s 强制终止，本身不是根因
- 往前找 `RuntimeError`、`AssertionError` 才是真正失败原因
