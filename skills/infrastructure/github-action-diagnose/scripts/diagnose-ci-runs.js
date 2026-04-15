#!/usr/bin/env node
/**
 * diagnose-ci-runs.js - 从 xlsx 提取 CI URL，调用 fetch-run.sh 获取日志，
 *                       使用 Alibaba 大模型分析并写回诊断结果
 *
 * 用法:
 *   node scripts/diagnose-ci-runs.js
 *   node scripts/diagnose-ci-runs.js --input Fail_CI_Problem/failed-runs-2026-04-10.xlsx
 *   node scripts/diagnose-ci-runs.js --input file.xlsx --model qwen3-coder-plus --batch-size 5
 *
 * 依赖:
 *   npm install xlsx
 *   gh CLI 已安装并登录
 */

const XLSX = require('xlsx');
const https = require('https');
const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

// ── 配置 ──────────────────────────────────────────────────────────────────────

const ALIBABA_API_KEY = process.env.ALIBABA_API_KEY || '';
const DEFAULT_MODEL = 'qwen3.6-plus';
const DEFAULT_BATCH_SIZE = 5;
const DEFAULT_REPO = 'vllm-project/vllm-ascend';

// ── 参数解析 ──────────────────────────────────────────────────────────────────

function parseArgs() {
  const args = process.argv.slice(2);
  const parsed = {
    input: null,
    model: DEFAULT_MODEL,
    batchSize: DEFAULT_BATCH_SIZE,
    limit: null,
    repo: DEFAULT_REPO,
    apiKey: ALIBABA_API_KEY,
  };

  let i = 0;
  while (i < args.length) {
    switch (args[i]) {
      case '--input':
        parsed.input = args[++i];
        break;
      case '--model':
        parsed.model = args[++i];
        break;
      case '--batch-size':
        parsed.batchSize = parseInt(args[++i], 10);
        break;
      case '--limit':
        parsed.limit = parseInt(args[++i], 10);
        break;
      case '--repo':
        parsed.repo = args[++i];
        break;
      case '--api-key':
        parsed.apiKey = args[++i];
        break;
      default:
        console.error(`未知参数: ${args[i]}`);
        process.exit(1);
    }
    i++;
  }

  return parsed;
}

// ── 查找最新的 xlsx 文件 ─────────────────────────────────────────────────────

function findLatestXlsx() {
  const outputDir = path.join(__dirname, '..', 'Fail_CI_Problem');
  if (!fs.existsSync(outputDir)) {
    console.error('错误: 未找到 Fail_CI_Problem 目录，请先运行 collect-failed-runs.js');
    process.exit(1);
  }

  const files = fs.readdirSync(outputDir)
    .filter(f => f.endsWith('.xlsx') && f.startsWith('failed-runs-'))
    .sort()
    .reverse();

  if (files.length === 0) {
    console.error('错误: Fail_CI_Problem 目录中没有找到 failed-runs-*.xlsx 文件');
    process.exit(1);
  }

  return path.join(outputDir, files[0]);
}

// ── 读取 xlsx ─────────────────────────────────────────────────────────────────

function readXlsx(filePath) {
  const wb = XLSX.readFile(filePath);
  const ws = wb.Sheets[wb.SheetNames[0]];
  const data = XLSX.utils.sheet_to_json(ws);
  return { wb, ws, data, filePath };
}

// ── 提取 run_id 从 URL ────────────────────────────────────────────────────────

function extractRunId(url) {
  const match = url.match(/\/runs\/(\d+)/);
  return match ? match[1] : null;
}

// ── 使用 fetch-run.sh 获取日志（SKILL.md Step 1b 要求） ──────────────────────

const SKILL_DIR = path.join(__dirname, '..', 'skills', 'infrastructure', 'github-action-diagnose');
const FETCH_RUN_SCRIPT = path.join(SKILL_DIR, 'scripts', 'fetch-run.sh');
const GIT_BASH = 'C:\\Program Files\\Git\\bin\\bash.exe';

function fetchRunLogs(runId, repo) {
  try {
    // 使用 fetch-run.sh 脚本获取日志（SKILL.md Step 1b 要求）
    // 原因：1) 日志可能很大导致 API 超时  2) 脚本内置预过滤逻辑  3) 排除 tiling 警告
    const scriptPath = FETCH_RUN_SCRIPT.replace(/\\/g, '/');
    const output = execSync(
      `"${GIT_BASH}" "${scriptPath}" ${runId} ${repo}`,
      { encoding: 'utf8', timeout: 120000, maxBuffer: 50 * 1024 * 1024 }
    );

    // 如果脚本输出为空或太短，尝试直接获取
    if (!output || output.trim().length < 100) {
      return fetchRunLogsFallback(runId, repo);
    }

    return output;
  } catch (err) {
    console.error(`  fetch-run.sh 失败: ${err.message}`);
    console.log('  使用备用方式获取日志...');
    return fetchRunLogsFallback(runId, repo);
  }
}

// 备用方案：直接使用 gh CLI 获取日志
function fetchRunLogsFallback(runId, repo) {
  try {
    const runView = execSync(
      `gh run view ${runId} --repo ${repo} 2>&1`,
      { encoding: 'utf8', timeout: 60000, maxBuffer: 10 * 1024 * 1024 }
    );

    let failedLogs = '';
    try {
      const logFailed = execSync(
        `gh run view ${runId} --log-failed --repo ${repo} 2>&1`,
        { encoding: 'utf8', timeout: 120000, maxBuffer: 50 * 1024 * 1024 }
      );

      const lines = logFailed.split('\n');
      const keyPatterns = [
        /RuntimeError|OutOfMemoryError|NPU out of memory|AssertionError|EngineDeadError/i,
        /exit code [1-9]|exit code 255|Process completed with exit code/i,
        /error code [0-9]+|ERR[0-9]+/i,
        /ETIMEDOUT|Connection refused|Network is unreachable/i,
        /OOM|Killed|Bus error|Segmentation fault/i,
        /unsatisfiable|No solution found|dependency.*failed/i,
        /Accuracy.*lower than|precision.*drop/i,
        /undefined variable|syntax error|yaml.*error/i,
      ];
      const excludePatterns = [
        /tiling func|Register tiling|ops_error\.h|error_check\.h/i,
        /##\[group\]|##\[endgroup\]/i,
        /^\s*$/,
      ];

      const keyLines = lines.filter(line => {
        if (excludePatterns.some(p => p.test(line))) return false;
        return keyPatterns.some(p => p.test(line));
      }).slice(0, 50);

      failedLogs = keyLines.join('\n');

      if (keyLines.length < 10) {
        const lastLines = lines.slice(-20).join('\n');
        failedLogs += '\n\n=== Last 20 lines of log ===\n' + lastLines;
      }
    } catch (e) {
      // 忽略
    }

    return `=== Run Overview ===\n${runView}\n\n=== Failed Job Logs (filtered) ===\n${failedLogs}`;
  } catch (err) {
    console.error(`  获取 Run #${runId} 日志失败: ${err.message}`);
    return null;
  }
}

// ── 调用 Alibaba API ──────────────────────────────────────────────────────────

function callAlibabaAPI(messages, model, apiKey) {
  return new Promise((resolve, reject) => {
    const payload = JSON.stringify({
      model: model,
      messages: messages,
      temperature: 0.1,
      max_tokens: 4096,
    });

    const options = {
      hostname: 'dashscope.aliyuncs.com',
      path: '/compatible-mode/v1/chat/completions',
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${apiKey}`,
        'Content-Length': Buffer.byteLength(payload),
      },
    };

    const req = https.request(options, (res) => {
      let data = '';
      res.on('data', (chunk) => (data += chunk));
      res.on('end', () => {
        if (res.statusCode >= 200 && res.statusCode < 300) {
          try {
            const json = JSON.parse(data);
            const content = json.choices?.[0]?.message?.content || '';
            const usage = json.usage || {};
            resolve({ content, usage });
          } catch (e) {
            reject(new Error(`Failed to parse response: ${e.message}`));
          }
        } else {
          reject(new Error(`HTTP ${res.statusCode}: ${data}`));
        }
      });
    });

    req.on('error', reject);
    req.write(payload);
    req.end();
  });
}

// ── 构建诊断 prompt ───────────────────────────────────────────────────────────

const REFERENCE_RULES = `## 诊断参考规则（精简版）

### 分类判断树
1. **失败阶段判断**:
   - Set up job / Initialize containers → 类型 A（直接定性）
   - Checkout / Install dependencies → 倾向 A，确认是网络还是版本号
   - Run test / Build → 同时排查 A 和 B

2. **类型 A vs B 区分**:
   - A 信号: 多 PR 同时失败、重跑通过、网络/硬件/OOM/exit 255、无 Python 堆栈
   - B 信号: 明确 Python 异常堆栈、稳定复现、与 PR diff 对应

### 常见错误模式速查
- **NPU 硬件**: ERR99999 / error code 507xxx → 类型 A
- **NPU 兼容性**: error code 107xxx（如 107030）→ 不是硬件！CANN runtime 参数非法，PR 版本升级时 → 类型 B
- **容器启动**: "custom container implementation failed" → 类型 A（镜像拉取/资源争用/K8s 编排卡死）
- **OOM**: Bus error → SHM 不足；Killed / exit -9 → OOM Killer
- **多机超时**: 不要孤立分析报错节点，先找 Master/Rank 0
- **Nightly 调度**: shm_broadcast 60s 超时 + EngineDeadError → 类型 A（资源调度不稳定，非代码问题）
- **依赖解析**: "No solution found" / "unsatisfiable" → 类型 A（版本不存在），注意不要误判为 Python 环境问题
- **vllm-ascend 安装**: csrc 编译失败 → 检查 PR 是否改了 setup.py/CMakeLists（类型 B），否则环境依赖（类型 A）
- **依赖下载**: wget github.com 直连失败 → 脚本未走 gh-proxy → 脚本配置问题
- **cache-service 超时**: 集群内网问题 → 类型 A
- **ModelScope 下载超时**: 网络抖动 → 类型 A，直接重跑
- **UT 卡死**: 无明显报错但运行 2-3h 超时 → 类型 B（主线脏代码死锁）
- **CPU offload 挂死**: 日志截断无 FAILED 行 → 类型 E（概率性）
- **Triton 挂死**: 重跑随机通过/失败 → 类型 E

### 精度回归判断
- AssertionError: Test0: / model_utils.py → 类型 C（精度回归，非功能 Bug）
- 跌幅 < 3%: 先重跑确认是否 flaky
- 跌幅 > 5%: PR 引入功能性回归

### 易混淆场景
- AssertionError 可能是精度回归（类型 C）或代码 Bug（类型 B），看来源
- NPU function error 107xxx 不是硬件故障
- EngineDeadError 伴随 shm_broadcast 超时 → 类型 A，启动阶段即崩溃 → 类型 B
- exit code 255 = K8s 强制终止，往前找真正根因
- tiling 编译警告（Register tiling func failed）= 正常 DEBUG，忽略

### vllm-ascend 环境
- 包管理器: uv（不是 pip）
- 模型来源: ModelScope（VLLM_USE_MODELSCOPE=True），路径 /root/.cache/modelscope/
- CANN 环境需 shell -el 激活
- Lint runner: linux-amd64-cpu-8-hk（CPU，无 NPU）`;

function buildDiagnosisPrompt(runId, runInfo, logs) {
  return `你是一个 CI 故障诊断专家，专门分析 GitHub Actions 在昇腾（Ascend）NPU 集群上的失败问题。

请根据以下 CI Run 的日志信息，进行根因分析并输出诊断报告。

## CI Run 信息
- Run ID: ${runId}
- 工作流: ${runInfo.workflow_name || 'N/A'}
- 分支: ${runInfo.branch || 'N/A'}
- 创建时间: ${runInfo.created_at || 'N/A'}
- 失败时间: ${runInfo.updated_at || 'N/A'}
- 用户: ${runInfo.user || 'N/A'}

## 日志信息
\`\`\`
${logs}
\`\`\`

${REFERENCE_RULES}

## 输出要求
请按照以下格式输出诊断结果（每个失败 Job 一节）：

\`\`\`
## 故障一：[Job 名称]
- **定性**: [环境问题 / 代码Bug / 精度回归 / 配置错误 / 疑难]
- **根因**: [一句话直接原因]
- **关键标识**: [最关键的一行错误]
- **责任方**: [基础设施团队 / PR 作者]
- **建议**: [重跑 / 修改 XX / 上报运维]
\`\`\`

## 注意事项
- 不粘贴大段原始日志，只引用最关键的一行错误
- 不描述诊断过程，直接给结论
- 使用上述参考规则进行精准分类

请输出诊断结果：`;
}

// ── 主函数 ────────────────────────────────────────────────────────────────────

async function main() {
  const args = parseArgs();

  // 查找输入文件
  const inputPath = args.input || findLatestXlsx();
  if (!fs.existsSync(inputPath)) {
    console.error(`错误: 文件不存在: ${inputPath}`);
    process.exit(1);
  }

  console.log(`输入文件: ${inputPath}`);
  console.log(`模型: ${args.model}`);
  console.log(`批量大小: ${args.batchSize}`);
  console.log();

  // 检查 API Key
  if (!args.apiKey) {
    console.error('错误: 未设置 Alibaba API Key');
    console.error('请设置环境变量 ALIBABA_API_KEY 或使用 --api-key 参数');
    process.exit(1);
  }



  // 读取 xlsx
  const { wb, ws, data, filePath } = readXlsx(inputPath);

  // 过滤出没有诊断结果的记录
  const recordsToDiagnose = data.filter(r => !r['诊断结果'] || r['诊断结果'].trim() === '');
  const alreadyDiagnosed = data.length - recordsToDiagnose.length;

  if (alreadyDiagnosed > 0) {
    console.log(`跳过 ${alreadyDiagnosed} 条已诊断记录`);
  }

  if (recordsToDiagnose.length === 0) {
    console.log('所有记录已诊断，无需处理。');
    return;
  }

  console.log(`待诊断记录: ${recordsToDiagnose.length} 条`);
  if (args.limit) {
    console.log(`限制诊断数量: ${args.limit} 条`);
  }
  console.log();

  let diagnosedCount = 0;
  let errorCount = 0;
  let totalInputTokens = 0;
  let totalOutputTokens = 0;
  const maxRecords = args.limit || recordsToDiagnose.length;

  for (let i = 0; i < Math.min(recordsToDiagnose.length, maxRecords); i++) {
    const record = recordsToDiagnose[i];
    const runId = extractRunId(record['URL'] || '');

    if (!runId) {
      console.log(`[${i + 1}/${recordsToDiagnose.length}] 跳过: 无法提取 Run ID`);
      continue;
    }

    console.log(`[${i + 1}/${recordsToDiagnose.length}] 诊断 Run #${runId}...`);

    // 获取日志
    console.log('  获取日志...');
    const logs = fetchRunLogs(runId, args.repo);

    if (!logs || logs.trim().length === 0) {
      console.log('  日志为空，跳过');
      errorCount++;
      continue;
    }

    // 调用大模型
    console.log('  调用大模型分析...');
    const prompt = buildDiagnosisPrompt(runId, record, logs);

    try {
      const result = await callAlibabaAPI(
        [{ role: 'user', content: prompt }],
        args.model,
        args.apiKey
      );

      // 更新记录
      record['诊断结果'] = result.content;
      diagnosedCount++;

      // 统计 token
      const inputTokens = result.usage?.prompt_tokens || 0;
      const outputTokens = result.usage?.completion_tokens || 0;
      totalInputTokens += inputTokens;
      totalOutputTokens += outputTokens;

      console.log(`  诊断完成 (输入: ${inputTokens} tokens, 输出: ${outputTokens} tokens)`);

      // 每处理 batchSize 条保存一次
      if (diagnosedCount % args.batchSize === 0) {
        console.log(`  保存进度 (${diagnosedCount} 条)...`);
        saveProgress(wb, ws, data, filePath);
      }
    } catch (err) {
      console.error(`  诊断失败: ${err.message}`);
      record['诊断结果'] = `错误: ${err.message}`;
      errorCount++;
    }

    // 避免 API 限流，等待 1 秒
    if (i < recordsToDiagnose.length - 1) {
      await new Promise(resolve => setTimeout(resolve, 1000));
    }
  }

  // 最终保存
  console.log('\n保存最终结果...');
  saveProgress(wb, ws, data, filePath);

  console.log();
  console.log(`诊断完成: ${diagnosedCount} 条成功, ${errorCount} 条失败`);
  console.log(`结果已写入: ${filePath}`);

  // 输出 Token 统计
  const totalTokens = totalInputTokens + totalOutputTokens;
  const avgInput = diagnosedCount > 0 ? Math.round(totalInputTokens / diagnosedCount) : 0;
  const avgOutput = diagnosedCount > 0 ? Math.round(totalOutputTokens / diagnosedCount) : 0;
  console.log();
  console.log('═══════════════════════════════════════════');
  console.log(' Token 消耗统计');
  console.log('═══════════════════════════════════════════');
  console.log(`  总输入 Token:  ${totalInputTokens.toLocaleString()}`);
  console.log(`  总输出 Token:  ${totalOutputTokens.toLocaleString()}`);
  console.log(`  总 Token:      ${totalTokens.toLocaleString()}`);
  console.log(`  平均输入/条:   ${avgInput.toLocaleString()}`);
  console.log(`  平均输出/条:   ${avgOutput.toLocaleString()}`);
  console.log(`  预估费用:      ¥${(totalInputTokens / 1e6 * 10 + totalOutputTokens / 1e6 * 30).toFixed(2)}`);
  console.log('═══════════════════════════════════════════');
}

function saveProgress(wb, ws, data, filePath) {
  // 创建新的 workbook 来避免文件锁定问题
  const newWb = XLSX.utils.book_new();
  const newWs = XLSX.utils.json_to_sheet(data);
  XLSX.utils.book_append_sheet(newWb, newWs, '失败记录');

  // 设置列宽
  newWs['!cols'] = [
    { wch: 60 }, { wch: 18 }, { wch: 22 }, { wch: 22 },
    { wch: 15 }, { wch: 30 }, { wch: 25 }, { wch: 20 }, { wch: 80 }
  ];

  // 写入临时文件（使用 .xlsx 扩展名），然后替换
  const tempPath = filePath + '.temp.xlsx';
  XLSX.writeFile(newWb, tempPath);

  // 删除原文件并重命名临时文件
  if (fs.existsSync(filePath)) {
    fs.unlinkSync(filePath);
  }
  fs.renameSync(tempPath, filePath);
}

main().catch(err => {
  console.error('错误:', err.message);
  process.exit(1);
});
