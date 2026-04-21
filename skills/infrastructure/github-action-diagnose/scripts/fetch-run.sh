#!/usr/bin/env bash
# scripts/fetch-run.sh  <run_id> [owner/repo]
#
# 用途：一次性抓取 CI Run 所有失败 Job 的 runner 信息和关键日志
#       将每个 Job 原始日志（可达数百行）压缩至 ~20 行关键错误行
#       在 LLM 进行 Step 2+ 推理之前完成所有数据收集，节省 token
#
# 用法：
#   bash scripts/fetch-run.sh 22935910341                    # Run ID
#   bash scripts/fetch-run.sh 22935910341 owner/repo         # Run ID + repo
#   bash scripts/fetch-run.sh --job 67875153370 owner/repo   # 单个 Job ID
#
# 输出：
#   - Run 概览（Job 状态列表 + Annotations）
#   - 每个失败 Job：runner 名称 + 预过滤的关键日志（~20 行）
#   - cancelled Job：提示去看 Annotations（queue 抢占等无需读日志）
#
# 依赖：gh CLI（已登录）

set -uo pipefail

# 解析参数
JOB_ID=""
RUN_ID=""
REPO="vllm-project/vllm-ascend"

# 解析参数：支持 "--job <id> [repo]" 或 "<run_id> [repo]"
if [[ "$1" == "--job" ]]; then
  JOB_ID="$2"
  REPO="${3:-vllm-project/vllm-ascend}"
else
  RUN_ID="${1:-}"
  REPO="${2:-vllm-project/vllm-ascend}"
fi

if [[ -n "$JOB_ID" ]]; then
  # 单 Job 模式
  echo "════════════════════════════════════════════"
  echo " Single Job Mode | $REPO"
  echo "════════════════════════════════════════════"

  # ── Step A：基本信息（Runner / 时间 / 结论）──────────────────────────────────
  JOB_META=$(gh api "repos/$REPO/actions/jobs/$JOB_ID" 2>/dev/null)
  echo "$JOB_META" | \
    python3 -c "
import json,sys
d=json.load(sys.stdin)
print(f'── [{d[\"conclusion\"].upper()}] {d[\"name\"]}')
print(f'   Runner : {d.get(\"runner_name\") or \"(unknown)\"}')
print(f'   时间   : {d.get(\"started_at\",\"?\")} ~ {d.get(\"completed_at\",\"?\")}')
steps=[s for s in d.get('steps',[]) if s.get('conclusion') not in ('success','skipped',None)]
if steps:
    print('   ── 失败步骤')
    for s in steps:
        print(f'      [{s[\"conclusion\"].upper():8}] Step {s[\"number\"]}: {s[\"name\"]}')
"

  # ── Step B：PR 上下文 ─────────────────────────────────────────────────────────
  RUN_ID_FOR_JOB=$(echo "$JOB_META" | python3 -c "import json,sys; print(json.load(sys.stdin)['run_id'])" 2>/dev/null || echo "")
  if [[ -n "$RUN_ID_FOR_JOB" ]]; then
    RUN_META=$(gh api "repos/$REPO/actions/runs/$RUN_ID_FOR_JOB" 2>/dev/null)
    PR_NUM=$(echo "$RUN_META" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['pull_requests'][0]['number'] if d.get('pull_requests') else '')" 2>/dev/null || echo "")
    RUN_TITLE=$(echo "$RUN_META" | python3 -c "import json,sys; print(json.load(sys.stdin).get('display_title',''))" 2>/dev/null || echo "")
    RUN_BRANCH=$(echo "$RUN_META" | python3 -c "import json,sys; print(json.load(sys.stdin).get('head_branch',''))" 2>/dev/null || echo "")
    echo "   PR     : ${PR_NUM:+#$PR_NUM }${RUN_TITLE} (${RUN_BRANCH})"
    if [[ -n "$PR_NUM" ]]; then
      echo "   ── PR 变更文件（分类参考）"
      gh pr diff "$PR_NUM" --repo "$REPO" --name-only 2>/dev/null | head -20 | sed 's/^/      /'
    fi
  fi

  # ── Step C：Annotations（通常直接揭示根因，如 ETIMEDOUT / exit code）─────────
  echo ""
  echo "   ── Annotations"
  ANNOTATIONS=$(gh api "repos/$REPO/check-runs/$JOB_ID/annotations" 2>/dev/null)
  ANN_COUNT=$(echo "$ANNOTATIONS" | python3 -c "import json,sys; print(len(json.load(sys.stdin)))" 2>/dev/null || echo "0")
  if [[ "$ANN_COUNT" -gt 0 ]]; then
    echo "$ANNOTATIONS" | python3 -c "
import json,sys
for a in json.load(sys.stdin):
    print(f'      [{a.get(\"annotation_level\",\"?\").upper()}] {a.get(\"message\",\"\").splitlines()[0]}')
"
  else
    echo "      （无 Annotations）"
  fi

  # ── Step D：判断是否需要拉完整日志 ───────────────────────────────────────────
  # Annotations 中包含明确错误信号时，跳过日志拉取（节省时间）
  ANN_TEXT=$(echo "$ANNOTATIONS" | python3 -c "import json,sys; print(' '.join(a.get('message','') for a in json.load(sys.stdin)))" 2>/dev/null || echo "")
  NEEDS_LOG=true
  if echo "$ANN_TEXT" | grep -qiE 'ETIMEDOUT|timeout|failed to create artifact|network|connection refused'; then
    echo ""
    echo "   ── Annotations 已明确根因（网络/超时类），跳过完整日志拉取"
    NEEDS_LOG=false
  fi

  if $NEEDS_LOG; then
    FULL_LOG=$(gh api "repos/$REPO/actions/jobs/$JOB_ID/logs" 2>&1)

    echo ""
    echo "   ── 运行时错误（高优先级）"
    echo "$FULL_LOG" \
      | grep -iE 'RuntimeError|OutOfMemoryError|NPU out of memory|AssertionError|EngineDeadError|EngineCore encountered|shm_broadcast.*60 seconds|No available shared memory broadcast|Process completed with exit code [1-9]|exit code 255|synchronized memcpy failed|NPU function error|error code is [0-9]|httpcore\.(ReadError|ConnectError)|httpx\.(ReadError|ConnectError)|RemoteProtocolError' \
      | grep -v -E 'ops_error\.h|error_check\.h' \
      | head -15

    RUNTIME_COUNT=$(echo "$FULL_LOG" | grep -cE 'RuntimeError|OutOfMemoryError|NPU out of memory|AssertionError|EngineDeadError|shm_broadcast.*60 seconds' || true)
    if [[ "$RUNTIME_COUNT" -eq 0 ]]; then
      echo "   ── 编译/安装错误（次优先级）"
      echo "$FULL_LOG" \
        | grep -iE 'error:.*failed|error:.*exit|fatal error|ERROR.*install|No solution found|unsatisfiable|ERROR.*Build|dubious ownership' \
        | grep -v -E '##\[group\]|##\[endgroup\]|warning.*format|ops_error\.h|error_check\.h|tiling func|tiling failed' \
        | head -5
    fi

    echo "   ── 最后输出（定位失败阶段）"
    echo "$FULL_LOG" \
      | grep -E '^[^[:space:]]+[[:space:]]+(UNKNOWN STEP|Run python|bash|pytest)' \
      | tail -5
  fi

  exit 0
fi

if [[ -z "$RUN_ID" ]]; then
  echo "用法: fetch-run.sh <run_id> [owner/repo]"
  echo "   或: fetch-run.sh --job <job_id> [owner/repo]"
  exit 1
fi

SEP="════════════════════════════════════════════"

# ── 1. Run 概览（Job 列表 + Annotations）────────────────────────────────────
echo "$SEP"
echo " Run $RUN_ID | $REPO"
echo "$SEP"
gh run view "$RUN_ID" --repo "$REPO"
echo ""

# ── PR 上下文（用于分类时区分代码 Bug 与基础设施）──────────────────────────
PR_NUM=$(gh api "repos/$REPO/actions/runs/$RUN_ID" \
  --jq '.pull_requests[0].number // empty' 2>/dev/null || echo "")
if [[ -n "$PR_NUM" ]]; then
  echo "$SEP"
  echo " PR #$PR_NUM 变更文件（分类参考）"
  echo "$SEP"
  gh pr diff "$PR_NUM" --repo "$REPO" --name-only 2>/dev/null | head -20
  echo ""
fi

# ── 2. 获取失败 / 取消的 Job ID ──────────────────────────────────────────────
FAILED_IDS=$(gh api "repos/$REPO/actions/runs/$RUN_ID/jobs?per_page=100" \
  --jq '.jobs[] | select(.conclusion == "failure" or .conclusion == "cancelled") | .id')

if [[ -z "$FAILED_IDS" ]]; then
  echo "（未发现失败或取消的 Job）"
  exit 0
fi

TOTAL=$(echo "$FAILED_IDS" | wc -l | tr -d ' ')
echo "$SEP"
echo " 失败 / 取消 Job 详情（共 ${TOTAL} 个）"
echo "$SEP"

# ── 3. 逐 Job 输出 runner 信息 + 关键日志 ────────────────────────────────────
for JOB_ID in $FAILED_IDS; do
  echo ""

  # Runner 信息（一次 API 调用，获取名称 / 结论 / 时间）
  gh api "repos/$REPO/actions/jobs/$JOB_ID" \
    --jq '"── [\(.conclusion | ascii_upcase)] \(.name)\n   Runner : \(.runner_name // "(unknown)")\n   时间   : \(.started_at // "?") ~ \(.completed_at // "?")"'

  CONCLUSION=$(gh api "repos/$REPO/actions/jobs/$JOB_ID" --jq '.conclusion')

  if [[ "$CONCLUSION" == "failure" ]]; then
    FULL_LOG=$(gh run view --job "$JOB_ID" --log --repo "$REPO" 2>&1)

    echo "   ── 运行时错误（高优先级）"
    # 同时捕获 CANN 底层错误（aclrtMemcpy/error code），便于区分硬件 vs 代码兼容性
    echo "$FULL_LOG" \
      | grep -iE 'RuntimeError|OutOfMemoryError|NPU out of memory|AssertionError|EngineDeadError|EngineCore encountered|shm_broadcast.*60 seconds|No available shared memory broadcast|Process completed with exit code [1-9]|exit code 255|synchronized memcpy failed|NPU function error|error code is [0-9]|httpcore\.(ReadError|ConnectError)|httpx\.(ReadError|ConnectError)|RemoteProtocolError' \
      | grep -v -E 'ops_error\.h|error_check\.h' \
      | head -15

    RUNTIME_COUNT=$(echo "$FULL_LOG" | grep -cE 'RuntimeError|OutOfMemoryError|NPU out of memory|AssertionError|EngineDeadError|shm_broadcast.*60 seconds' || true)
    if [[ "$RUNTIME_COUNT" -eq 0 ]]; then
      echo "   ── 编译/安装错误（次优先级）"
      echo "$FULL_LOG" \
        | grep -iE 'error:.*failed|error:.*exit|fatal error|ERROR.*install|No solution found|unsatisfiable|ERROR.*Build|dubious ownership' \
        | grep -v -E '##\[group\]|##\[endgroup\]|warning.*format|ops_error\.h|error_check\.h|tiling func|tiling failed' \
        | head -5
    fi

    # 显示 Job 最后阶段的关键标识
    echo "   ── 最后输出（定位失败阶段）"
    echo "$FULL_LOG" \
      | grep -E '^[^[:space:]]+[[:space:]]+(UNKNOWN STEP|Run python|bash|pytest)' \
      | tail -5

  else
    echo "   （cancelled — 根因见 Run 概览中的 ANNOTATIONS，通常为 queue 抢占）"
  fi
done

echo ""
echo "$SEP"
echo " 补充命令（按需使用）："
echo "   完整日志 : gh run view --job <id> --log --repo $REPO"
echo "   PR diff  : gh pr diff <pr> --repo $REPO --name-only"
echo "   kubectl  : kubectl get pods --all-namespaces | grep <runner_name>"
echo "$SEP"
