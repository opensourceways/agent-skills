#!/usr/bin/env node
/**
 * collect-failed-runs.js - 收集 GitHub 仓库一段时间内失败的 CI，支持按 Job 名称过滤
 *
 * 用法:
 *   node scripts/collect-failed-runs.js --hours 24 --exclude-jobs lint
 *   node scripts/collect-failed-runs.js --from 2024-01-01 --to 2024-01-31
 *   node scripts/collect-failed-runs.js --hours 24 --exclude-jobs lint "check-style" --output custom.xlsx
 *
 * 依赖:
 *   npm install xlsx
 */

const XLSX = require('xlsx');
const https = require('https');
const fs = require('fs');
const path = require('path');

function parseArgs() {
  const args = process.argv.slice(2);
  const parsed = {
    repo: 'vllm-project/vllm-ascend',
    from_date: null,
    to_date: null,
    hours: null,
    exclude_jobs: [],
    output: null,
    token: process.env.GITHUB_TOKEN || '',
    per_page: 100,
  };

  let i = 0;
  while (i < args.length) {
    switch (args[i]) {
      case '--repo':
        parsed.repo = args[++i];
        break;
      case '--from':
        parsed.from_date = args[++i];
        break;
      case '--to':
        parsed.to_date = args[++i];
        break;
      case '--hours':
        parsed.hours = parseInt(args[++i], 10);
        break;
      case '--exclude-jobs':
        while (i + 1 < args.length && !args[i + 1].startsWith('--')) {
          parsed.exclude_jobs.push(args[++i]);
        }
        break;
      case '--output':
        parsed.output = args[++i];
        break;
      case '--token':
        parsed.token = args[++i];
        break;
      case '--per-page':
        parsed.per_page = parseInt(args[++i], 10);
        break;
      default:
        console.error(`未知参数: ${args[i]}`);
        process.exit(1);
    }
    i++;
  }

  return parsed;
}

function getTimeRange(args) {
  const now = new Date();

  if (args.from_date && args.to_date) {
    const since = new Date(args.from_date + 'T00:00:00Z');
    const until = new Date(args.to_date + 'T23:59:59Z');
    return { since: since.toISOString(), until: until.toISOString() };
  } else if (args.from_date) {
    const since = new Date(args.from_date + 'T00:00:00Z');
    return { since: since.toISOString(), until: now.toISOString() };
  } else if (args.hours) {
    const since = new Date(now.getTime() - args.hours * 60 * 60 * 1000);
    return { since: since.toISOString(), until: now.toISOString() };
  } else {
    const since = new Date(now.getTime() - 2 * 60 * 60 * 1000);
    return { since: since.toISOString(), until: now.toISOString() };
  }
}

function githubGet(urlPath, token) {
  return new Promise((resolve, reject) => {
    const url = new URL(urlPath, 'https://api.github.com');
    const options = {
      hostname: url.hostname,
      path: url.pathname + url.search,
      method: 'GET',
      headers: {
        Accept: 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28',
        'User-Agent': 'collect-failed-runs-script',
      },
    };

    if (token) {
      options.headers['Authorization'] = `Bearer ${token}`;
    }

    https.get(options, (res) => {
      let data = '';
      res.on('data', (chunk) => (data += chunk));
      res.on('end', () => {
        if (res.statusCode >= 200 && res.statusCode < 300) {
          try {
            resolve(JSON.parse(data));
          } catch (e) {
            reject(new Error(`Failed to parse JSON: ${e.message}`));
          }
        } else {
          reject(new Error(`HTTP ${res.statusCode}: ${data}`));
        }
      });
    }).on('error', reject);
  });
}

async function fetchFailedRuns(repo, since, until, token, perPage) {
  const allRuns = [];
  let page = 1;

  while (true) {
    const params = new URLSearchParams({
      status: 'failure',
      per_page: perPage.toString(),
      page: page.toString(),
      created: `${since}..${until}`,
    });

    const urlPath = `/repos/${repo}/actions/runs?${params.toString()}`;
    const data = await githubGet(urlPath, token);
    const runs = data.workflow_runs || [];

    if (runs.length === 0) break;

    allRuns.push(...runs);

    if (runs.length < perPage) break;
    page++;
  }

  return allRuns;
}

async function fetchRunJobs(repo, runId, token) {
  const allJobs = [];
  let page = 1;

  while (true) {
    const params = new URLSearchParams({
      per_page: '100',
      page: page.toString(),
    });

    const urlPath = `/repos/${repo}/actions/runs/${runId}/jobs?${params.toString()}`;
    const data = await githubGet(urlPath, token);
    const jobs = data.jobs || [];

    if (jobs.length === 0) break;

    allJobs.push(...jobs);

    if (jobs.length < 100) break;
    page++;
  }

  return allJobs;
}

function shouldExcludeRun(jobs, excludePatterns) {
  if (excludePatterns.length === 0) return false;

  const failedJobs = jobs.filter((j) => j.conclusion === 'failure');
  if (failedJobs.length === 0) return true;

  for (const job of failedJobs) {
    const jobName = job.name || '';
    const isExcluded = excludePatterns.some((pattern) =>
      new RegExp(pattern, 'i').test(jobName)
    );
    if (!isExcluded) return false;
  }

  return true;
}

function getExcludedJobNames(jobs, excludePatterns) {
  const excluded = [];
  for (const job of jobs) {
    if (job.conclusion !== 'failure') continue;
    const jobName = job.name || '';
    const isExcluded = excludePatterns.some((pattern) =>
      new RegExp(pattern, 'i').test(jobName)
    );
    if (isExcluded) excluded.push(jobName);
  }
  return excluded;
}

function calcDuration(isoStr1, isoStr2) {
  try {
    const d1 = new Date(isoStr1);
    const d2 = new Date(isoStr2);
    const diffMs = d2 - d1;
    const totalSeconds = Math.floor(diffMs / 1000);
    const hours = Math.floor(totalSeconds / 3600);
    const minutes = Math.floor((totalSeconds % 3600) / 60);
    const seconds = totalSeconds % 60;

    const parts = [];
    if (hours > 0) parts.push(`${hours}h`);
    if (minutes > 0) parts.push(`${minutes}m`);
    parts.push(`${seconds}s`);
    return parts.join(' ');
  } catch {
    return 'N/A';
  }
}

function formatTime(isoStr) {
  try {
    const d = new Date(isoStr);
    const pad = (n) => n.toString().padStart(2, '0');
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
  } catch {
    return isoStr;
  }
}

function writeXlsx(records, outputPath) {
  const data = [
    ['URL', 'Run ID', '创建时间', '失败时间', '运行时间', '工作流名称', '分支', '用户'],
  ];

  for (const r of records) {
    data.push([
      r.url,
      r.run_id,
      r.created_at,
      r.updated_at,
      r.duration,
      r.workflow_name,
      r.branch,
      r.user,
    ]);
  }

  const ws = XLSX.utils.aoa_to_sheet(data);

  const colWidths = [
    { wch: 60 },
    { wch: 18 },
    { wch: 22 },
    { wch: 22 },
    { wch: 15 },
    { wch: 30 },
    { wch: 25 },
    { wch: 20 },
  ];
  ws['!cols'] = colWidths;

  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, '失败记录');
  XLSX.writeFile(wb, outputPath);
}

async function main() {
  const args = parseArgs();

  if (!args.token) {
    console.log('警告: 未设置 GitHub Token，可能触发 API 限流。');
    console.log('请设置环境变量 GITHUB_TOKEN 或使用 --token 参数。');
  }

  const { since, until } = getTimeRange(args);
  console.log(`仓库: ${args.repo}`);
  console.log(`时间范围: ${since} ~ ${until}`);
  if (args.exclude_jobs.length > 0) {
    console.log(`排除 Job: ${args.exclude_jobs.join(', ')}`);
  }
  console.log();

  console.log('获取失败的 Runs...');
  const runs = await fetchFailedRuns(
    args.repo,
    since,
    until,
    args.token,
    args.per_page
  );
  console.log(`共获取到 ${runs.length} 个失败的 Run`);

  const records = [];
  let skippedCount = 0;
  const skippedReasons = [];

  for (let i = 0; i < runs.length; i++) {
    const run = runs[i];
    const runId = run.id;
    process.stdout.write(`  处理 [${i + 1}/${runs.length}] Run #${runId}... `);

    const jobs = await fetchRunJobs(args.repo, runId, args.token);

    if (shouldExcludeRun(jobs, args.exclude_jobs)) {
      const excludedNames = getExcludedJobNames(jobs, args.exclude_jobs);
      skippedCount++;
      skippedReasons.push(
        `Run #${runId} 被排除 (失败 Job: ${excludedNames.join(', ')})`
      );
      console.log('跳过 (被过滤)');
      continue;
    }

    const user = (run.triggering_actor && run.triggering_actor.login) || 'N/A';

    records.push({
      url: `https://github.com/${args.repo}/actions/runs/${runId}`,
      run_id: runId,
      created_at: formatTime(run.created_at),
      updated_at: formatTime(run.updated_at),
      duration: calcDuration(run.created_at, run.updated_at),
      workflow_name: run.name || 'N/A',
      branch: run.head_branch || 'N/A',
      user: user,
    });
    console.log('保留');
  }

  console.log();
  console.log(`保留 ${records.length} 条记录，跳过 ${skippedCount} 条`);

  if (skippedReasons.length > 0) {
    console.log('\n跳过的 Run:');
    for (const reason of skippedReasons) {
      console.log(`  - ${reason}`);
    }
  }

  if (records.length === 0) {
    console.log('\n没有符合条件的记录，不生成文件。');
    return;
  }

  let outputPath = args.output;
  if (!outputPath) {
    const outputDir = 'Fail_CI_Problem';
    if (!fs.existsSync(outputDir)) {
      fs.mkdirSync(outputDir, { recursive: true });
    }
    const today = new Date().toISOString().split('T')[0];
    outputPath = path.join(outputDir, `failed-runs-${today}.xlsx`);
  }

  writeXlsx(records, outputPath);
  console.log(`\n已写入: ${outputPath}`);
}

main().catch((err) => {
  console.error('错误:', err.message);
  process.exit(1);
});
