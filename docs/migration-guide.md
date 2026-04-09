# 使用 Agent-Skills 替换直接 CC 调用

本文档说明如何将 `main2main_auto.yaml` 中直接调用 Claude Code 的方式，替换为调用 Agent-Skills。

## 架构对比

### 方案 A：直接调用（原方案）
```yaml
- uses: anthropics/claude-code-action/base-action@v1
  with:
    anthropic_api_key: ${{ secrets.ANTHROPIC_AUTH_TOKEN }}
    prompt: "..."
    claude_args: "..."
```

**优点**：
- 简单直接，一步完成
- GitHub Action 自动处理认证

**缺点**：
- 需要在每个调用方仓库配置 API key
- 无法集中管理 CC 版本和配置

### 方案 B：通过 Agent-Skills（新方案）
```yaml
- name: Trigger agent-skills
  run: |
    curl -X POST \
      -H "Authorization: Bearer ${{ secrets.PAT_TOKEN }}" \
      "https://api.github.com/repos/<org>/agent-skills/dispatches" \
      -d '{
        "event_type": "claude-request",
        "client_payload": {
          "caller_repo": "owner/repo",
          "custom_prompt": "...",
          "model": "claude-sonnet-4-20250514"
        }
      }'
```

**优点**：
- API key 集中管理在 agent-skills
- 可统一升级 CC 版本
- 支持白名单权限控制

**缺点**：
- 流程更复杂（触发→等待→下载→应用）
- 需要处理异步调用
- 容器内不能使用 `--dangerously-skip-permissions`

## 迁移步骤

### 1. 准备工作

#### Agent-Skills 端配置
1. 在 `allowed-callers.json` 中添加调用方仓库
2. 确保 `CLAUDE_API_KEY` secret 已设置
3. 确保 `AGENT_PAT` secret 已设置（用于检出调用方仓库）

#### 调用方仓库配置
1. 在仓库 Settings → Secrets 添加 `PAT_TOKEN`：
   - 需要有 `repo` 和 `workflow` 权限
   - 需要能触发 agent-skills 仓库的 workflow

### 2. 修改 Workflow

将原来的 CC 调用步骤替换为以下三个步骤：

```yaml
# 步骤 1: 触发 Agent-Skills
- name: Trigger agent-skills workflow
  id: trigger
  env:
    GH_TOKEN: ${{ secrets.PAT_TOKEN }}
  run: |
    # 构建 JSON payload
    PAYLOAD=$(cat <<EOF
    {
      "event_type": "claude-request",
      "client_payload": {
        "caller_repo": "owner/repo",                    # 被修改的仓库
        "custom_prompt": "...",                         # 给 CC 的 prompt
        "model": "claude-sonnet-4-20250514",           # 模型名称
        "allow_code_change": true,                      # 是否允许修改代码
        "dangerously_skip_permissions": false,          # 容器内必须设为 false
        "allowed_tools": "Bash(git *),Read,Write,...", # 允许的工具
        "show_full_output": true,
        "caller_env_vars": "KEY1=value1\nKEY2=value2", # 环境变量（可选）
        "comment_author": "${{ github.actor }}",
        "comment_body": "..."
      }
    }
    EOF
    )
    
    # 发送请求
    curl -X POST \
      -H "Authorization: Bearer $GH_TOKEN" \
      -H "Accept: application/vnd.github+json" \
      -H "X-GitHub-Api-Version: 2022-11-28" \
      "https://api.github.com/repos/<org>/agent-skills/dispatches" \
      -d "$PAYLOAD"
    
    sleep 15  # 等待 workflow 启动

# 步骤 2: 获取 Workflow Run ID 并等待完成
- name: Wait for agent-skills completion
  id: wait
  env:
    GH_TOKEN: ${{ secrets.PAT_TOKEN }}
  run: |
    # 获取最新的 workflow run
    RUN_ID=$(gh run list \
      --repo "<org>/agent-skills" \
      --workflow _claude-code.yml \
      -L 1 \
      --json databaseId \
      --jq '.[0].databaseId')
    
    # 轮询等待完成
    for i in {1..180}; do
      STATUS=$(gh run view "$RUN_ID" \
        --repo "<org>/agent-skills" \
        --json conclusion \
        --jq '.conclusion')
      
      if [[ "$STATUS" == "success" || "$STATUS" == "failure" ]]; then
        break
      fi
      sleep 10
    done

# 步骤 3: 下载 patch 并应用
- name: Download and apply patch
  run: |
    # 下载 artifact
    gh run download "$RUN_ID" \
      --repo "<org>/agent-skills" \
      --name claude-changes-patch \
      --dir /tmp/patch
    
    # 应用 patch
    git apply /tmp/patch/claude-changes.patch
```

### 3. 参数映射表

| 原参数 | 新参数 | 说明 |
|--------|--------|------|
| `anthropic_api_key` | 无需传递 | 由 agent-skills 管理 |
| `prompt` | `custom_prompt` | 直接传递 prompt 内容 |
| `claude_args` | `model`, `allowed_tools` 等 | 拆分为独立参数 |
| 环境变量 | `caller_env_vars` | 多行字符串格式 |

### 4. 注意事项

#### 关于 `--dangerously-skip-permissions`
- **原方案**：可以使用（GitHub Action 内部处理）
- **新方案**：容器内使用 root 用户，**必须设为 false**
- 影响：CC 会提示权限确认，但测试显示可以正常工作

#### 关于环境变量
原方案通过 `env:` 直接设置：
```yaml
env:
  KEY: value
```

新方案通过 `caller_env_vars` 传递（多行字符串）：
```yaml
"caller_env_vars": "KEY1=value1\nKEY2=value2"
```

#### 关于模型
- 原方案可以使用任意模型（包括第三方如 minimax）
- 新方案使用 Anthropic 官方模型（如 `claude-sonnet-4-20250514`）

## 测试建议

在实际迁移前，建议：
1. 先创建测试 workflow（类似 test-cc-phase1.yml）
2. 验证参数传递是否正确
3. 验证 patch 能成功下载和应用
4. 确认无误后再修改 main2main

## 回滚方案

如果新方案有问题，可以快速回滚：
1. 恢复原来的 `uses: anthropics/claude-code-action/base-action@v1` 步骤
2. 删除新增的触发/等待/下载步骤
3. 无需修改 agent-skills

## 示例：Phase 1 完整替换

### 替换前（原方案）
```yaml
- name: Claude adapt to new vLLM
  uses: anthropics/claude-code-action/base-action@v1
  with:
    anthropic_api_key: ${{ secrets.ANTHROPIC_AUTH_TOKEN }}
    prompt: |
      Use the main2main skill to adapt...
      NEW_COMMIT: ${{ steps.detect.outputs.new_commit }}
    claude_args: "--model claude-sonnet-4-20250514 --dangerously-skip-permissions ..."
  env:
    OLD_COMMIT: ${{ steps.detect.outputs.old_commit }}
    NEW_COMMIT: ${{ steps.detect.outputs.new_commit }}
```

### 替换后（新方案）
```yaml
- name: Trigger agent-skills
  run: |
    curl -X POST ...
    # payload 包含：
    # - caller_repo: "owner/repo"
    # - custom_prompt: "Use the main2main skill..."
    # - model: "claude-sonnet-4-20250514"
    # - allowed_tools: "..."
    # - caller_env_vars: "OLD_COMMIT=...\nNEW_COMMIT=..."

- name: Wait for completion
  run: |
    # 轮询等待 agent-skills 完成

- name: Apply patch
  run: |
    # 下载 artifact 并应用
```

## 参考

- Agent-Skills 仓库：https://github.com/opensourceways/agent-skills
- 测试示例：vllm-benchmarks/.github/workflows/test-cc-phase1.yml
- 原始 main2main：nv-action/vllm-benchmarks/.github/workflows/main2main_auto.yaml
