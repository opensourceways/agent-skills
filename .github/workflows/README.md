# Claude Code 工作流集成指南

在任意仓库中集成 Claude Code，通过 `@claude` 触发代码审查，或在 CI 中自动分析 PR。
API Key 集中存储在 `KadenZhang3321/agent-skills`，调用方无需配置。

## 前置条件（每个调用方仓库做一次）

1. 向 agent-skills 管理员申请一个 PAT（`repo` scope）
2. 在调用方仓库添加 Secret：  
   **Settings → Secrets and variables → Actions → New repository secret**  
   - Name: `DISPATCH_TOKEN`  
   - Value: 申请到的 PAT

---

## 快速开始

复制 [TEMPLATE-CALLER.yml](./TEMPLATE-CALLER.yml) 到目标仓库：

```bash
mkdir -p .github/workflows
curl -sSL https://raw.githubusercontent.com/KadenZhang3321/agent-skills/main/.github/workflows/TEMPLATE-CALLER.yml \
  -o .github/workflows/claude-bot.yml
git add .github/workflows/claude-bot.yml
git commit -m "ci: add Claude Bot workflow"
git push
```

`TEMPLATE-CALLER.yml` 已内置三种触发方式，按需保留即可：
- **手动触发**（`workflow_dispatch`）
- **PR 评论触发**（`issue_comment`，需包含 `@claude`）
- **PR 自动触发**（`pull_request`，opened/synchronize）

---

## 参数说明

在 caller 文件的 `with` 中配置以下参数：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `allow_code_change` | `false` | `true` 允许 Claude 修改文件并生成 patch artifact；`false` 只分析 |
| `skill_name` | `''` | 指定 Skill 名称（见下方说明），留空不使用 |
| `skill_url` | `''` | 远程 Skill 文件的 raw URL，优先级高于 skill_name |
| `model` | `'claude-sonnet-4-20250514'` | Claude 模型名称 |
| `caller_image` | `''` | 调用方提供的镜像，留空使用 `ubuntu:24.04` |
| `verify_command` | `''` | 验证命令，验证失败则 job 失败 |

### caller_image 示例

```yaml
# 调用方提供的镜像，镜像需要预装 Node.js、Git、依赖已安装
'caller_image': 'ghcr.io/caller/project:main',

# 使用 ubuntu:24.04（默认）
'caller_image': '',
```

### verify_command 示例

```yaml
# 验证命令，验证失败则 job 失败
'verify_command': 'npm run build && npm test',

# 不验证（默认）
'verify_command': '',
```

### allow_code_change 示例

```yaml
# 只审查，不改代码（推荐用于自动触发）
'allow_code_change': false,

# 允许改代码，生成 patch artifact
'allow_code_change': true,
```

### skill_name 示例

Skill 按以下顺序查找：

1. **远程 URL**：如果指定了 `skill_url`，从 URL 下载（优先级最高）
2. **调用方仓库（.github）**：`.github/skills/<skill_name>/SKILL.md`
3. **调用方仓库（.ai）**：`.ai/skills/<skill_name>/SKILL.md`
4. **agent-skills**：`skills/<skill_name>/SKILL.md`

```yaml
# 使用 agent-skills 内置 Skill
'skill_name': 'infrastructure/github-action-diagnose',
'skill_name': 'infrastructure/docker-image-pr-fix',

# 使用调用方仓库自定义 Skill（会按上述顺序查找）
'skill_name': 'my-skill',

# 不使用 Skill
'skill_name': '',
```

agent-skills 内置 Skill 列表见 [skills/](../../skills/)。

### skill_url 示例

使用远程仓库的 Skill 文件（优先于 skill_name）：

```yaml
# 使用远程 Skill（注意：URL 必须是 raw 内容链接）
'skill_url': 'https://raw.githubusercontent.com/owner/repo/main/.ai/skills/my-skill/SKILL.md',
```

> 提示：GitHub raw URL 格式为 `https://raw.githubusercontent.com/<owner>/<repo>/<branch>/<path>`

### model 示例

```yaml
# 默认（速度与能力均衡，推荐）
'model': 'claude-sonnet-4-20250514',

# 最强模型，适合复杂分析
'model': 'claude-opus-4-20251114',

# 最快，适合轻量任务
'model': 'claude-haiku-4-5-20251001',
```

---

## 白名单管理

允许访问的组织和仓库在 [../.github/allowed-callers.json](../allowed-callers.json) 中配置：

```json
{
  "allowed_orgs": [
    "opensourceways"
  ],
  "allowed_repos": [
    "KadenZhang3321/agent-skills",
    "KadenZhang3321/hello-world"
  ]
}
```

- `allowed_orgs`：整个组织下所有仓库都可以使用
- `allowed_repos`：单独授权某个仓库（不在上述组织内也可以）

新增仓库或组织，修改此文件并合并到 main 即可，无需其他改动。

---

## 工作原理

```
调用方仓库                         agent-skills
─────────────────                 ────────────────────────────────
PR 评论 / PR 事件 / 手动触发
  └─ TEMPLATE-CALLER.yml
       └─ workflow_call ───────────> _claude-code.yml
                                      1. 安装基础依赖（含 python3、gh）
                                      2. Checkout agent-skills
                                      3. 白名单校验
                                      4. 用户权限校验
                                      5. 安装 Claude Code
                                      6. Checkout 调用方仓库
                                      7. 拉取 PR Diff
                                      8. 构建 Prompt（含 Skill）
                                      9. 调用 Claude（使用集中的 API Key）
                                     10. verify_command 不为空？
                                            └─ 执行验证命令
                                     11. 生成 patch artifact（如有变更）
                                     12. 在原 PR/Issue 发布评论
```

---

## agent-skills 需配置的 Secrets

| Secret | 用途 |
|--------|------|
| `CLAUDE_API_KEY` | Anthropic API Key，用于调用 Claude |
| `DISPATCH_TOKEN` | PAT（`repo` scope），用于读写调用方仓库、发评论、创建 PR |

---

## 故障排查

**agent-skills Actions 没有触发**
- 检查 `DISPATCH_TOKEN` 是否配置了 `repo` scope（`public_repo` 不够）
- 确认 agent-skills 的 Actions 已开启

**白名单拒绝**
- 在 `allowed-callers.json` 中添加对应的 org 或 repo

**Claude 没有发评论**
- 检查 `DISPATCH_TOKEN` 是否有目标仓库的写权限
- 查看 agent-skills Actions 中该次 run 的 `Post comment` 步骤日志

**Token/Cost 显示 N/A**
- 检查 `CLAUDE_API_KEY` 是否正确配置
