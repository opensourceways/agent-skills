# vllm-ascend 仓库专用参考

仓库：`vllm-project/vllm-ascend`
这是 vLLM 在华为昇腾（Ascend）NPU 上的适配层，基于 ARC/K8s + GitHub Actions。

---

## Runner 类型与节点池

vllm-ascend 有两种 runner，溯源方式不同：

### 静态 Runner（固定节点，长期运行）
| Runner 名 | 硬件 | 用途 |
|-----------|------|------|
| `linux-aarch64-a2b3-0` | Atlas 800 A2B3 | 轻量 job（trigger 解析、变更检测） |
| `linux-aarch64-a2b3-1` | Atlas 800 A2B3 | E2E singlecard 测试 |
| `linux-aarch64-a3-2` | Atlas 800 A3 | A3 单机测试 |
| `linux-aarch64-a3-4` | Atlas 800 A3 | A3 4 卡测试 |
| `linux-aarch64-310p-1` | Atlas 300I Pro (310P) | 310P 单卡测试 |
| `linux-aarch64-310p-4` | Atlas 300I Pro (310P) | 310P 4 卡测试 |
| `linux-amd64-cpu-8-hk` | x86 CPU（香港） | lint / pre-commit（无 NPU） |

静态 runner 出问题：pod 不会销毁，可直接 `kubectl get pod` 查节点。

### ARC 动态 Runner（K8s 弹性扩容）
用于 nightly 等高并发场景，pod 名格式：
```
linux-aarch64-a3-2-x51bm-runner-ksnwc
      ↑架构      ↑节点池       ↑随机后缀
```
节点池编号（`a3-0`、`a3-2` 等）对应不同物理机组。
动态 runner 任务完成后 pod 会销毁，需从日志系统（Loki/ELK）查调度记录。

---

## 内部服务

这些是集群内部地址，出现在 workflow 日志中属于正常配置，**如果访问失败则是基础设施问题**：

| 服务 | 地址 | 用途 |
|------|------|------|
| PyPI 缓存 | `http://cache-service.nginx-pypi-cache.svc.cluster.local/pypi/simple` | 所有 `uv pip install` 走这里 |
| apt 镜像 | `cache-service.nginx-pypi-cache.svc.cluster.local:8081` | apt 源替换 |
| GitHub 代理 | `https://gh-proxy.test.osinfra.cn` | git clone / wget GitHub 资源 |
| Ascend PyPI | `https://mirrors.huaweicloud.com/ascend/repos/pypi` | Ascend 专用包（CANN 等） |

**关键诊断规则：**
- `Install dependencies` 失败 + 报 `cache-service` 连接超时 → **基础设施/集群内网问题**，不是代码问题
- `wget github.com` 直连失败 → 脚本未走 `gh-proxy` → **脚本配置问题**（代码/CI维护者）
- `git clone github.com` 失败 → 检查是否配置了 `url insteadOf gh-proxy`

---

## 主要 Workflow 及触发条件

| Workflow | 触发 | Runner | 说明 |
|---------|------|--------|------|
| `pr_test_light.yaml` | 每个 PR 到 main/*-dev/releases/v* | a2b3-1 + amd64 | lint + e2e-singlecard-light |
| `pr_test_full.yaml` | PR 打 label 或手动触发 | a2b3-1 + a3-2/4 | 完整测试套件 |
| `schedule_nightly_test_a3.yaml` | 每天 23:45 北京时间 | a3 动态 runner | nightly 全量测试 |
| `_pre_commit.yml` | 被上述 workflow 调用 | `linux-amd64-cpu-8-hk` | lint：actionlint / markdownlint / mypy |

**PR CI 触发变更检测逻辑（重要）：**
PR CI 中有一个 `changes` job，用 `dorny/paths-filter` 判断哪些测试需要跑：
- 改了 `vllm_ascend/**`、`tests/e2e/**`、`CMakeLists.txt`、`setup.py` 等 → 触发 e2e 测试
- 只改了 `tests/ut/**` → 只触发 unit test
- 只改了文档等 → 只跑 lint

因此：**如果测试没有被触发，先检查变更文件是否命中了对应的 path filter**，不要误判为 CI 基础设施问题。

---

## 测试套件结构

测试用 `run_suite.py` 统一调度，套件定义在 `.github/workflows/scripts/config.yaml`：

| 套件名 | 说明 |
|--------|------|
| `e2e-singlecard-light` | PR CI 默认跑的轻量单卡测试 |
| `e2e-singlecard` | 完整单卡测试 |
| `e2e-2card-light` | 2 卡轻量测试 |
| `e2e-multicard-2-cards` | 2 卡多卡测试 |
| `e2e-multicard-4-cards` | 4 卡多卡测试 |

测试文件路径：`tests/e2e/singlecard/`、`tests/e2e/multicard/`、`tests/ut/`

**定位具体失败用例：**
```bash
# 从 gh 日志中找到失败的具体 test 文件和函数名
gh run view --job <job_id> --log-failed --repo vllm-project/vllm-ascend | grep -E "FAILED|ERROR|assert"
```

---

## 环境与依赖特殊说明

### 包管理器：uv（不是 pip）
所有依赖安装用 `uv pip install`，报错格式与 pip 略有不同：
```
# uv 典型报错
error: Distribution ... not found (no matching distribution)
error: Failed to download ... Connection refused
```

### 模型来源：ModelScope（不是 HuggingFace）
所有测试环境设置了：
```
VLLM_USE_MODELSCOPE: True
HF_HUB_OFFLINE: 1
```
模型缓存在 runner 节点的 `/root/.cache/modelscope/`（不是 `~/.cache/huggingface/`）。
精度回归分析时，模型路径格式为：
```
/root/.cache/modelscope/hub/xxx/ModelName
```

### CANN 环境激活
Workflow 统一配置了：
```yaml
defaults:
  run:
    shell: bash -el {0}
```
这是因为 CANN toolkit 的环境变量需要通过 shell profile 激活。如果某个 step 没有用这个 shell 配置，可能导致 NPU 驱动不可用。

---

## 常见 PR CI 失败场景速查

### Lint 失败（pre-commit job）
- **Runner**：`linux-amd64-cpu-8-hk`（CPU，无 NPU，不需要节点溯源）
- **常见错误**：mypy 类型检查失败、markdownlint 格式问题、actionlint workflow 语法问题
- **责任方**：PR 作者
- **修复**：本地运行 `pre-commit run --all-files` 复现

### Install dependencies 失败
- 先判断是哪个依赖源出问题：`cache-service`（基础设施）还是 GitHub 直连（脚本配置）
- `uv pip install` 从 `cache-service` 失败 → 基础设施问题，重跑
- `wget`/`git clone` 从 `github.com` 直连失败 → 检查 gh-proxy 配置

### 测试精度回归
vllm-ascend 的精度测试会检查模型推理结果是否达到阈值，常见断言：
```python
assert accuracy >= threshold, f"Accuracy of {model_path} is {accuracy}, is lower than {threshold}"
```
- 跌幅 < 3%：可能是随机性，先确认是否 flaky（重跑）
- 跌幅 > 5%：PR 引入了功能性回归，检查 speculative decoding、采样逻辑、kernel 改动

### 多机任务失败（nightly multi-node）
- nightly A3 的多机测试中，Rank N timeout 不代表 Rank N 出问题
- 排查顺序：Master（Rank 0）→ 其他 Rank
- 检查 Master 的日志：`Unexpected Exit`、驱动报错、`ERR99999`
