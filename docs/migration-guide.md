# 迁移指南：从直接 CC 调用到 Agent-Skills

本文档说明如何将 workflow 中直接调用 Claude Code 的方式，替换为通过 Agent-Skills 调用。

## 迁移步骤

### 1. 准备工作

#### Agent-Skills 端配置
1. 在 `allowed-callers.json` 中添加调用方仓库路径
2. 确保 `CLAUDE_API_KEY` secret 已配置
3. 确保 `AGENT_PAT` secret 已配置（用于检出调用方仓库）

#### 调用方仓库配置
1. 在仓库 Settings → Secrets 添加 `PAT_TOKEN`：
   - 需要有 `repo` 和 `workflow` 权限
   - 需要能触发 agent-skills 仓库的 workflow

### 2. 修改 Workflow

将原来的 `anthropics/claude-code-action/base-action@v1` 步骤替换为以下三个步骤：

#### 步骤 1: 触发 Agent-Skills

```yaml
- name: Trigger agent-skills workflow
  id: trigger
  env:
    GH_TOKEN: ${{ secrets.PAT_TOKEN }}
  run: |
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
    
    curl -X POST \
      -H "Authorization: Bearer $GH_TOKEN" \
      -H "Accept: application/vnd.github+json" \
      -H "X-GitHub-Api-Version: 2022-11-28" \
      "https://api.github.com/repos/kadenzhang3321/agent-skills/dispatches" \
      -d "$PAYLOAD"
    
    sleep 15  # 等待 workflow 启动
```

#### 步骤 2: 等待完成

```yaml
- name: Wait for agent-skills completion
  id: wait
  env:
    GH_TOKEN: ${{ secrets.PAT_TOKEN }}
  run: |
    for i in {1..180}; do
      RUN_ID=$(gh run list \
        --repo "kadenzhang3321/agent-skills" \
        --workflow _claude-code.yml \
        -L 1 \
        --json databaseId \
        --jq '.[0].databaseId')
      
      if [ -n "$RUN_ID" ]; then
        STATUS=$(gh run view "$RUN_ID" \
          --repo "kadenzhang3321/agent-skills" \
          --json conclusion \
          --jq '.conclusion')
        
        if [[ "$STATUS" == "success" || "$STATUS" == "failure" ]]; then
          echo "run_id=$RUN_ID" >> "$GITHUB_OUTPUT"
          break
        fi
      fi
      sleep 10
    done
```

#### 步骤 3: 下载并应用 Patch

```yaml
- name: Download and apply patch
  run: |
    gh run download "${{ steps.wait.outputs.run_id }}" \
      --repo "kadenzhang3321/agent-skills" \
      --name claude-changes-patch \
      --dir /tmp/patch
    
    git apply /tmp/patch/claude-changes.patch
```

### 3. 参数映射表

| 原参数 | 新参数 | 说明 |
|--------|--------|------|
| `anthropic_api_key` | 无需传递 | 由 agent-skills 管理 |
| `prompt` | `custom_prompt` | 直接传递 prompt 内容 |
| `claude_args` | `model`, `allowed_tools` 等 | 拆分为独立参数 |
| 环境变量 | `caller_env_vars` | 多行字符串格式，用 `\n` 分隔 |

### 4. 注意事项

#### 关于 `--dangerously-skip-permissions`
- **原方案**：可以使用（GitHub Action 内部处理）
- **新方案**：容器内使用 root 用户，**必须设为 false**
- 影响：CC 会提示权限确认，但测试显示可以正常工作

#### 关于环境变量
原方案通过 `env:` 直接设置：
```yaml
env:
  OLD_COMMIT: abc123
  NEW_COMMIT: def456
```

新方案通过 `caller_env_vars` 传递（多行字符串）：
```yaml
"caller_env_vars": "OLD_COMMIT=abc123\nNEW_COMMIT=def456"
```

#### 关于模型
- 原方案可以使用任意模型（包括第三方如 minimax）
- 新方案使用 Anthropic 官方模型（如 `claude-sonnet-4-20250514`）

#### 关于长内容传递
如果需要传递文件内容（如 bisect summary）：
```bash
# 读取并转义（限制大小避免超出 payload 限制）
CONTENT=$(head -c 3000 /path/to/file.md | sed ':a;N;$!ba;s/\n/\\n/g' | sed 's/"/\\"/g')
```

然后在 payload 中使用：
```yaml
"caller_env_vars": "FILE_CONTENT=${CONTENT}"
```

### 5. 完整示例

#### 替换前（原方案）
```yaml
- name: Claude adapt to new vLLM
  uses: anthropics/claude-code-action/base-action@v1
  with:
    anthropic_api_key: ${{ secrets.ANTHROPIC_AUTH_TOKEN }}
    prompt: |
      Use the main2main skill to adapt...
      NEW_COMMIT: ${{ steps.detect.outputs.new_commit }}
    claude_args: "--model minimax/minimax-m2.5:free --dangerously-skip-permissions --allowed-tools 'Bash(git *),Read,Write'"
  env:
    OLD_COMMIT: ${{ steps.detect.outputs.old_commit }}
    NEW_COMMIT: ${{ steps.detect.outputs.new_commit }}
    CLAUDE_WORKING_DIR: ${{ github.workspace }}/work-dir
```

#### 替换后（新方案）
```yaml
- name: Trigger agent-skills
  id: trigger
  env:
    GH_TOKEN: ${{ secrets.PAT_TOKEN }}
  run: |
    PAYLOAD=$(cat <<EOF
    {
      "event_type": "claude-request",
      "client_payload": {
        "caller_repo": "kadenzhang3321/vllm-benchmarks",
        "custom_prompt": "Use the main2main skill to adapt vllm-benchmarks to the latest vLLM main branch.\nThe NEW_COMMIT environment variable is set to ${{ steps.detect.outputs.new_commit }}.\nCommit your changes with '-s' but do NOT create a PR.",
        "model": "claude-sonnet-4-20250514",
        "allow_code_change": true,
        "dangerously_skip_permissions": false,
        "allowed_tools": "Bash(git *),Bash(gh *),Read,Write,Edit,Glob,Grep",
        "show_full_output": true,
        "caller_env_vars": "OLD_COMMIT=${{ steps.detect.outputs.old_commit }}\nNEW_COMMIT=${{ steps.detect.outputs.new_commit }}\nCLAUDE_WORKING_DIR=${{ github.workspace }}/work-dir"
      }
    }
    EOF
    )
    
    curl -X POST \
      -H "Authorization: Bearer $GH_TOKEN" \
      -H "Accept: application/vnd.github+json" \
      -H "X-GitHub-Api-Version: 2022-11-28" \
      "https://api.github.com/repos/kadenzhang3321/agent-skills/dispatches" \
      -d "$PAYLOAD"
    
    sleep 15

- name: Wait for agent-skills completion
  id: wait
  env:
    GH_TOKEN: ${{ secrets.PAT_TOKEN }}
  run: |
    for i in {1..180}; do
      RUN_ID=$(gh run list \
        --repo "kadenzhang3321/agent-skills" \
        --workflow _claude-code.yml \
        -L 1 \
        --json databaseId \
        --jq '.[0].databaseId')
      
      if [ -n "$RUN_ID" ]; then
        STATUS=$(gh run view "$RUN_ID" \
          --repo "kadenzhang3321/agent-skills" \
          --json conclusion \
          --jq '.conclusion')
        
        if [[ "$STATUS" == "success" || "$STATUS" == "failure" ]]; then
          echo "run_id=$RUN_ID" >> "$GITHUB_OUTPUT"
          break
        fi
      fi
      sleep 10
    done

- name: Download and apply patch
  run: |
    gh run download "${{ steps.wait.outputs.run_id }}" \
      --repo "kadenzhang3321/agent-skills" \
      --name claude-changes-patch \
      --dir /tmp/patch
    
    git apply /tmp/patch/claude-changes.patch
```

### 6. 回滚方案

如果新方案有问题，可以快速回滚：
1. 恢复原来的 `uses: anthropics/claude-code-action/base-action@v1` 步骤
2. 删除新增的触发/等待/下载步骤
3. 无需修改 agent-skills
