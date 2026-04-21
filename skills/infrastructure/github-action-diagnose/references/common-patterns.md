# 常见 CI 错误模式速查（昇腾 NPU / ARC / K8s 环境）

## 基础设施类

### NPU 硬件错误（⚠️ 注意 error code 范围）
```
ERR99999
error code 507035
npu-smi info: device X not found
```
- **定性**：类型 A，硬件层故障
- **分析**：用 `npu-smi info` 确认 NPU 状态；查看是否是特定节点的问题
- **处理**：标记该节点为 SchedulingDisabled，上报硬件团队
- **⚠️ 易误判**：`NPU function error: aclrtMemcpy, error code is 107xxx`（如 107030）**不是硬件错误**，是 CANN runtime 参数非法；若发生在 `model init` 阶段且 PR 是版本升级/main2main → 定性为**类型 B**（代码兼容性），参见 classification-guide.md 场景 D

### 容器启动超时（Initialize containers 阶段）
```
[error] Executing the custom container implementation failed.
Please contact your self hosted runner administrator.
```
日志在 `12:50:13` 开始执行 `k8s/index.js` 但 1 小时后无任何进展：
- **定性**：类型 A
- **可能原因**：镜像拉取超时（网络抖动/仓库限流）、NPU 资源争用（节点上 NPU 全被占用）、K8s 容器编排脚本卡死（API Server 响应慢）
- **溯源**：查 Runner Pod 状态，反查物理节点，确认镜像拉取是否有失败事件

### 网络代理绕过（Install dependencies 阶段）
```
Connecting to github.com|20.205.243.166|:443... connected.
Unable to establish SSL connection.
Error: command terminated with exit code 4
```
```
ERROR 618: jwt:expired.
Error: command terminated with exit code 8
```
- **定性**：类型 A，基础设施/网络
- **根因**：安装脚本用 `wget` 直连 `github.com`，未经集群内代理（如 `gh-proxy.test.osinfra.cn`）转发，导致 SSL 失败 / JWT 签名 URL 过期
- **触发位置**：通常在 `scripts/ci/npu/npu_ci_install_dependency.sh`
- **修复方案 A（推荐）**：将下载 URL 替换为代理地址：
  ```bash
  GH_PROXY="https://gh-proxy.test.osinfra.cn"
  wget "${GH_PROXY}/https://github.com/..."
  ```
- **修复方案 B**：将依赖预缓存到内部 cache-service，彻底脱离 GitHub 实时依赖

### OOM / 内存不足
```
Bus error  (核心已转储)
Killed
exit code -9
```
- **定性**：类型 A
- **Bus error**：通常是 SHM（共享内存）不足，多机/多卡训练时常见
- **Killed / exit code -9**：系统 OOM Killer 终止进程
- **处理**：检查 Pod 的内存 limit 配置；检查是否有其他 Pod 占用了节点内存

### 多机任务连锁超时
```
[Rank X] Timeout waiting for ...
```
- **定性**：类型 A，但需找主节点（Master / Rank 0）
- **分析**：某 Rank 报 Timeout 不一定是该 Rank 的问题——优先检查 **Master 节点**日志，是否有 `Unexpected Exit` 或驱动报错

### Nightly 资源调度不稳定（Worker 进程挂死）
```
No available shared memory broadcast block found in 60 seconds.
EngineDeadError: EngineCore encountered an issue.
```
- **定性**：类型 A，基础设施 / 资源调度不稳定
- **背景**：Nightly 多机任务中，Worker 进程被调度抢占或 NPU 资源争用导致卡死，`shm_broadcast` 60s 超时连续触发，最终 EngineCore 死亡。`EngineDeadError` 本身不是根因，是连锁结果
- **判断依据**：`shm_broadcast` 超时日志连续出现（每 60s 一次）；任务为 Nightly（非 PR CI）；早期推理吞吐日志正常，说明模型加载成功
- **与代码 Bug 的区分**：代码 Bug 通常在启动阶段或首次推理即失败，且有明确的 Python 异常堆栈；此模式为运行一段时间后才崩溃，且无代码层异常
- **处理**：直接重跑；若持续复现，检查对应节点的 NPU 调度竞争情况

### Runner 调度失败（Set up job 阶段）
```
Waiting for runner... (timeout)
No runners available
```
- **定性**：类型 A
- **分析**：查看 ARC Scale Set 是否有 listener Pod 在运行；查看 Pending Pod 数量；检查节点是否有 `SchedulingDisabled`

---

## 代码类错误

### UnboundLocalError（典型陷阱）
```
UnboundLocalError: cannot access local variable 'xxx' where it is not associated with a value
```
- **定性**：类型 B，代码 Bug
- **典型模式**：`try: import lib except ImportError: pass`，之后直接使用 `lib` 变量，在 except 路径中 `lib` 未被赋值
- **修复模式**：
  ```python
  try:
      import huggingface_hub
      _HF_HUB_AVAILABLE = True
  except ImportError:
      _HF_HUB_AVAILABLE = False

  # 使用时：
  if _HF_HUB_AVAILABLE:
      try:
          ...
      except huggingface_hub.errors.LocalEntryNotFoundError:
          ...
  ```

### 精度回归
```
AssertionError: 0.515 not greater than or equal to 0.59
Accuracy of /root/.cache/.../ModelName is 0.515, is lower than 0.59
```
```
FAILED tests/e2e/singlecard/test_quantization.py::test_qwen3_w8a8_quant - AssertionError: Test0:
tests/e2e/model_utils.py:53: AssertionError
```
- **定性**：类型 C，精度回归
- **分析方向**：找 PR 中对推理路径的改动（量化/反量化逻辑、speculative decoding、token 采样、接受逻辑）
- **注意**：`AssertionError: TestN:` 来自 `model_utils.py` 的输出正确性断言，也是精度回归，不是功能性代码 Bug；跌幅 > 5-13% 通常是功能性回归，不是随机波动

### YAML 语法错误
```
undefined variable "False"
```
- **定性**：类型 D
- **根因**：YAML 中 `True`/`False` 应为小写 `true`/`false`

### 测试断言失败
```
AssertionError
FAIL: TestXxx
Expected: xxx, Got: yyy
```
- **分析步骤**：
  1. 判断是测试写错（预期值不合理）还是被测逻辑错
  2. 对比 PR diff 找到变更点
  3. 重跑确认是否 flaky

---

### ModelScope 网络不稳定（Run test 阶段）
```
Downloading model from modelscope...
ConnectionError: ('Connection aborted.', RemoteDisconnected('...'))
urllib3.exceptions.ReadTimeoutError
HTTPSConnectionPool: Read timed out
```
- **定性**：类型 A，网络/基础设施
- **背景**：vllm-ascend 测试使用 ModelScope 下载模型（`VLLM_USE_MODELSCOPE=True`），模型缓存在 `/root/.cache/modelscope/`。网络抖动会导致下载中断，表现为 Run test 阶段报网络超时而非代码异常
- **判断依据**：失败在 Run test 早期（模型加载前），错误为网络类而非 Python 异常；其他 Job / 其他时间重跑可通过
- **处理**：直接重跑。如频繁出现，检查集群到 ModelScope CDN 的网络质量；考虑将常用模型预缓存到节点本地，避免每次实时下载

### UT 卡死 / 超时（主线合入脏代码）
```
# 无明显报错，Job 运行 2-3 小时后超时取消
Canceling since a higher priority waiting request ... exists
# 或超时被 K8s 强制终止
command terminated with exit code 255
```
- **定性**：类型 B，代码 Bug（通常是主线合入了有问题的代码）
- **背景**：UT 正常运行时间约 30-60 分钟。如果 UT 运行超过 2 小时仍无进展，通常是某个测试死锁或无限等待，而非基础设施问题
- **与基础设施超时的区分**：基础设施超时发生在 `Initialize containers` 阶段；UT 卡死发生在 `Run unit test` 阶段，且 Job 已正常启动并运行了较长时间
- **排查步骤**：
  1. 查看 UT 日志的最后输出，定位卡在哪个测试文件/函数
  2. 检查最近合入 main 的 commit，是否包含涉及锁、进程通信、分布式初始化的改动
  3. 本地运行该测试用例（单独运行，加超时）复现
- **处理**：定位并 revert 引入死锁的 commit，或修复相关代码

### CPU Offload 概率性挂死
```
# 无异常堆栈，进程在 Run e2e test 阶段静默挂起
Error executing in Docker Container: 1
Executing the custom container implementation failed.
```
- **定性**：类型 E，疑难/概率性问题
- **背景**：CPU offload 功能在特定配置下存在概率性死锁，进程不报错但不返回，被容器超时机制终止，表现为 exit code 1
- **与真实测试失败的区分**：
  - 概率挂：日志在测试中途截断，无 `FAILED` / `AssertionError` 等 pytest 汇总行
  - 真实失败：有明确的 `FAILED tests/xxx.py::test_xxx` + 异常堆栈
- **处理**：先重跑 1-2 次确认概率性；能通过则上报 CPU offload 模块追踪死锁路径

### 依赖解析失败（Install 阶段）
```
× No solution found when resolving dependencies:
╰─▶ Because there is no version of modelscope==1.35.1 and you require
    modelscope==1.35.1, we can conclude that your requirements are unsatisfiable.
```
```
ERROR: Could not find a version that satisfies the requirement xxx
ERROR: No matching distribution found for xxx
```
- **定性**：类型 A，依赖源配置问题
- **背景**：依赖版本在 PyPI / 镜像源中不存在，导致依赖解析失败，后续步骤连锁失败
- **⚠️ 常见误判**：依赖解析失败后会产生大量 "error"、"failed" 级联日志（如 `find: '/usr/lib/python3': No such file`），容易被误判为 Python 环境问题或镜像缺失
- **关键诊断**：搜索 `unsatisfiable|No solution found|no version of|requirements are unsatisfiable`
- **处理**：检查版本号是否正确、依赖是否已发布到配置的镜像源

### vllm-ascend 安装失败（Install 阶段 build error）
```
Installing build dependencies: finished with status 'error'
error: subprocess-exited-with-error
× installing build dependencies did not run successfully. exit code: 1
ERROR: Failed to build 'file:///__w/vllm-ascend/vllm-ascend/vllm-empty'
```
- **定性**：类型 A 或 B，需区分
- **背景**：`Install vllm-project/vllm-ascend` 或 `Install vllm from source` 阶段，csrc 编译或 build dependency 安装失败
- **⚠️ 常见误判**：同步出现的 apt `403 Forbidden`（针对 `jammy-backports`/`jammy-security`）是次要现象，不是根因，这两个仓库为可选安全更新源，403 不影响核心依赖安装
- **区分根因**：
  - 检查 PR 是否修改了 csrc/CMakeLists/setup.py → 可能是 PR 引入（类型 B）
  - 与最近主线无关、其他 PR 同期也失败 → 可能是环境依赖版本问题（类型 A）
- **处理**：在对应硬件（310p/A3）环境本地复现；检查 build dependency 版本兼容性

### CANN tiling 编译警告（⚠️ 不是根因）
```
[ERROR][xxx] Register tiling func failed, please check the class name.
[ERROR][xxx] Get op tiling func failed, please check the soc version %d
[ERROR][xxx] Do op tiling failed, cannot find soc version.
```
- **定性**：编译阶段正常输出，**不是测试失败根因**
- **背景**：这些日志来自 CANN SDK 的 tiling 注册过程，属于 DEBUG 级别的编译输出，不代表运行时失败
- **⚠️ 常见误判**：这些日志数量大（可达数百行），容易被 grep 脚本捕获后误认为是根因
- **识别方法**：
  - 时间戳：在 `Install vllm-ascend` 阶段（编译期）出现
  - 日志级别：DEBUG 或普通 ERROR，无 Traceback
  - 真正的根因需要往后找 `RuntimeError`、`AssertionError`、`exit code 255`
- **处理**：忽略 tiling 警告，继续分析测试阶段的运行时错误

### Git dubious ownership（Install 阶段）
```
git introspection failed: fatal: detected dubious ownership in repository at '/__w/xxx/xxx'
```
- **定性**：类型 A，基础设施 — Git 安全检查阻止构建
- **背景**：Git 仓库所有者与当前用户不匹配，通常发生在容器内运行 CI Job 时
- **关键诊断**：搜索 `dubious ownership`
- **处理**：在 workflow 或容器启动脚本中添加 `git config --global --add safe.directory '*'`

### Triton Ascend 概率性挂死
```
# 无异常堆栈，进程静默挂起
# 或：
Traceback (most recent call last):
  ...
RuntimeError: [Triton] ...
# 或 Job 超时，无有意义的错误信息
```
- **定性**：类型 E，疑难/概率性问题
- **背景**：triton_ascend 在特定算子或配置下存在概率性挂死，表现为进程不报错但永远不返回，最终被超时机制终止
- **判断依据**：
  - 重跑有时通过、有时挂
  - 失败点随机（不固定在某个测试）
  - 日志截断，无完整的 Python 异常堆栈
  - 涉及 triton_ascend 编译或 kernel 执行阶段
- **处理**：
  1. 先重跑 1-2 次确认是否概率性（能通过则大概率是此类问题）
  2. 记录卡死时最后执行的算子/测试，上报 triton_ascend 团队
  3. 短期可跳过该测试或降低并发度规避；长期需 triton_ascend 侧修复

---

## Runner Pod 命名规范

ARC/K8s 环境中 Runner Pod 名称的结构：
```
linux-aarch64-a3-2-x51bm-runner-ksnwc
     ↑架构      ↑节点池  ↑      ↑随机后缀
                  a3-2 = 节点池编号
                       x51bm = 物理机标识（有时）
```

常见节点池：`a3-0`、`a3-2`、`a3-4` 等，对应不同的 ARC Runner Scale Set 和物理机组。
