# Agent-Skills 调用指南

本文档说明如何在业务仓库中使用中心 Claude Code 服务。

## 目录

- [架构概述](#架构概述)
- [前置条件](#前置条件)
- [同步调用（workflow_call）](#同步调用workflow_call)
- [参数说明](#参数说明)
- [输出说明](#输出说明)
- [错误处理](#错误处理)
- [常见问题](#常见问题)

## 架构概述

```
┌─────────────────────┐         ┌──────────────────────────┐
│   业务仓库           │         │  agent-skills 中心仓库    │
│                     │         │                          │
│  - 触发工作流        │ ──────> │  _claude-code.yml        │
│  - 传递参数          │         │  - 白名单校验             │
│  - 接收结果          │ <────── │  - 权限检查               │
│                     │         │  - 调用 Claude Code       │
└─────────────────────┘         │  - 返回结果               │
                                └──────────────────────────┘
```

**调用方式**：通过 `workflow_call` 同步调用，父工作流会等待 Claude 执行完毕。

## 前置条件

### 1. 配置 Secrets

在业务仓库的 Settings → Secrets and variables → Actions 中添加：

| Secret 名称 | 说明 | 权限要求 |
|-------------|------|----------|
| `DISPATCH_TOKEN` | GitHub Personal Access Token | `repo` 完整权限 |
| `CLAUDE_API_KEY` | Anthropic API Key | 无需额外权限 |

### 2. 添加白名单

联系 agent-skills 仓库管理员，将你的仓库添加到 `.github/allowed-callers.json`：

```json
{
  "allowed_orgs": ["your-org"],
  "allowed_repos": ["your-org/your-repo"]
}
```

## 同步调用（workflow_call）

### 基本用法

```yaml
jobs:
  claude:
    uses: KadenZhang3321/agent-skills/.github/workflows/_claude-code.yml@main
    with:
      caller_repo: ${{ github.repository }}
      custom_prompt: '请分析这个 PR 的代码变更'
      allow_code_change: false
      model: 'claude-sonnet-4-20250514'
    secrets:
      DISPATCH_TOKEN: ${{ secrets.DISPATCH_TOKEN }}
      CLAUDE_API_KEY: ${{ secrets.CLAUDE_API_KEY }}
```

### 完整示例

```yaml
jobs:
  claude:
    uses: KadenZhang3321/agent-skills/.github/workflows/_claude-code.yml@main
    with:
      # 必填：调用方仓库路径
      caller_repo: ${{ github.repository }}
      
      # Prompt 相关（三选一）
      custom_prompt: '请修复这个 bug：...'
      skill_name: 'github-action-diagnose'
      skill_url: 'https://example.com/skill.md'
      
      # 代码变更权限
      allow_code_change: false
      
      # 模型配置
      model: 'claude-sonnet-4-20250514'
      dangerously_skip_permissions: false
      allowed_tools: 'Bash(git *),Read,Write,Edit,Glob,Grep'
      show_full_output: true
      
      # PR/Issue 相关
      pr_number: '123'
      issue_number: '123'
      comment_author: ${{ github.actor }}
      comment_body: '请分析这个 PR'
      
      # 环境变量
      caller_env_vars: 'KEY1=value1\nKEY2=value2'
      
      # 容器镜像
      caller_image: 'ubuntu:24.04'
      
      # 验证命令
      verify_command: 'pytest tests/'
    secrets:
      DISPATCH_TOKEN: ${{ secrets.DISPATCH_TOKEN }}
      CLAUDE_API_KEY: ${{ secrets.CLAUDE_API_KEY }}

  # 使用 Claude 的输出
  post-process:
    needs: claude
    runs-on: ubuntu-latest
    steps:
      - name: Check result
        run: |
          echo "Changes: ${{ needs.claude.outputs.changes_detected }}"
          echo "Cost: ${{ needs.claude.outputs.cost_usd }}"
```

### PR 评论触发示例

```yaml
on:
  issue_comment:
    types: [created]

jobs:
  claude-on-comment:
    if: |
      github.event.issue.pull_request &&
      contains(github.event.comment.body, '@claude') &&
      !endsWith(github.actor, '[bot]') &&
      github.actor != 'dependabot'
    uses: KadenZhang3321/agent-skills/.github/workflows/_claude-code.yml@main
    with:
      caller_repo: ${{ github.repository }}
      pr_number: ${{ github.event.issue.number }}
      issue_number: ${{ github.event.issue.number }}
      comment_author: ${{ github.event.comment.user.login }}
      comment_body: ${{ github.event.comment.body }}
      allow_code_change: false
      model: 'claude-sonnet-4-20250514'
    secrets:
      DISPATCH_TOKEN: ${{ secrets.DISPATCH_TOKEN }}
      CLAUDE_API_KEY: ${{ secrets.CLAUDE_API_KEY }}
```

更多调用模板请参考 [.github/workflows/TEMPLATE-CALLER.yml](../.github/workflows/TEMPLATE-CALLER.yml)。

## 参数说明

### workflow_call inputs

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `caller_repo` | string | ✅ | - | 调用方仓库路径 (owner/repo) |
| `custom_prompt` | string | ❌ | `''` | 自定义 prompt 内容 |
| `skill_name` | string | ❌ | `''` | Skill 名称（从 agent-skills 加载） |
| `skill_url` | string | ❌ | `''` | Skill URL（从远程加载） |
| `allow_code_change` | boolean | ❌ | `false` | 是否允许 Claude 修改代码 |
| `model` | string | ❌ | `claude-sonnet-4-20250514` | Claude 模型名称 |
| `dangerously_skip_permissions` | boolean | ❌ | `false` | 跳过权限确认 |
| `allowed_tools` | string | ❌ | `''` | 允许的工具列表（逗号分隔） |
| `show_full_output` | boolean | ❌ | `false` | 显示完整输出 |
| `caller_env_vars` | string | ❌ | `''` | 调用方环境变量（`\n` 分隔） |
| `caller_image` | string | ❌ | `''` | 自定义容器镜像 |
| `verify_command` | string | ❌ | `''` | 验证命令 |
| `pr_number` | string | ❌ | `''` | PR 编号 |
| `issue_number` | string | ❌ | `''` | Issue 编号 |
| `comment_author` | string | ❌ | `'workflow'` | 评论作者 |
| `comment_body` | string | ❌ | `''` | 评论内容 |

### secrets

| Secret | 必填 | 说明 |
|--------|------|------|
| `DISPATCH_TOKEN` | ✅ | GitHub PAT（repo 权限） |
| `CLAUDE_API_KEY` | ✅ | Anthropic API Key |

## 输出说明

### workflow_call outputs

| 输出 | 类型 | 说明 |
|------|------|------|
| `changes_detected` | boolean | 是否检测到代码变更 |
| `commit_sha` | string | 提交 SHA（如有变更） |
| `pr_url` | string | 创建的 PR URL（如有） |
| `cost_usd` | number | API 调用成本（USD） |
| `input_tokens` | number | 输入 token 数 |
| `output_tokens` | number | 输出 token 数 |
| `response_summary` | string | Claude 回复摘要（前 500 字符） |
| `error_message` | string | 错误信息（如有） |

### 使用示例

```yaml
jobs:
  claude:
    uses: KadenZhang3321/agent-skills/.github/workflows/_claude-code.yml@main
    with:
      caller_repo: ${{ github.repository }}
      custom_prompt: '修复这个 bug'
      allow_code_change: true
    secrets:
      DISPATCH_TOKEN: ${{ secrets.DISPATCH_TOKEN }}
      CLAUDE_API_KEY: ${{ secrets.CLAUDE_API_KEY }}

  process-result:
    needs: claude
    runs-on: ubuntu-latest
    steps:
      - name: Check if code changed
        if: needs.claude.outputs.changes_detected == 'true'
        run: |
          echo "Claude made changes!"
          echo "Commit: ${{ needs.claude.outputs.commit_sha }}"
          echo "Cost: ${{ needs.claude.outputs.cost_usd }} USD"
      
      - name: Handle error
        if: needs.claude.outputs.error_message != ''
        run: |
          echo "Error: ${{ needs.claude.outputs.error_message }}"
          exit 1
```

## 错误处理

### 重试机制

Claude 调用失败时会自动重试（最多 3 次，指数退避：10s → 20s → 30s）。

### 错误输出

如果最终失败，`error_message` 输出会包含错误信息：

```yaml
- name: Handle error
  if: needs.claude.outputs.error_message != ''
  run: |
    echo "Claude failed: ${{ needs.claude.outputs.error_message }}"
```

### 常见错误

| 错误 | 原因 | 解决方案 |
|------|------|----------|
| `Caller not in whitelist` | 仓库未在白名单中 | 联系管理员添加 |
| `Insufficient permission` | 用户权限不足 | 确保用户有 write/admin 权限 |
| `Claude Code failed after 3 attempts` | API 调用失败 | 检查 API Key 和网络 |
| `JSON parse error` | 输出解析失败 | 检查模型配置 |

## 常见问题

### Q: 同步调用和异步调用应该选哪个？

**A**: 当前只支持 `workflow_call` 同步调用。父工作流会等待 Claude 执行完成，适合需要立即获取结果、后续步骤依赖 Claude 输出的场景。

### Q: 如何允许 Claude 修改代码？

**A**: 设置 `allow_code_change: true`，Claude 会修改文件并生成 patch artifact，可从 Actions 下载应用。

### Q: 如何自定义容器镜像？

**A**: 设置 `caller_image: 'your-image:tag'`，可以跳过依赖安装步骤，加速执行。

### Q: 如何传递环境变量给 Claude？

**A**: 使用 `caller_env_vars`，格式为 `KEY1=value1\nKEY2=value2`。

### Q: Claude 修改的代码如何获取？

**A**: 同步调用时，通过 artifact 下载 `claude-changes-patch`。

### Q: 如何指定 Claude 使用的模型？

**A**: 设置 `model` 参数，如 `model: 'claude-sonnet-4-20250514'`。

### Q: 白名单如何配置？

**A**: 在 agent-skills 仓库的 `.github/allowed-callers.json` 中添加：
- `allowed_orgs`: 整个组织的仓库都可以调用
- `allowed_repos`: 单独指定仓库
