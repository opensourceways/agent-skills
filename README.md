# Agent-Skills 仓库

这是一个集中管理和共享 Claude Code Skills 的部门级仓库，支持多团队协作。

## 📁 仓库结构

```
Agent-Skills/
├── skills/
│   ├── infrastructure/  # Infrastructure 团队（基础设施建设）专属skills
│   ├── upstream/        # Upstream 团队（上游开发贡献）专属skills
│   ├── operation/       # Operation 团队（社区运营）专属skills
│   └── shared/          # 跨团队共享的skills
├── templates/           # Skill模板
└── docs/               # 文档和使用指南
```

## 🚀 快速开始

### 1. 上传 Skills

#### 方式一：直接上传到对应团队目录

```bash
# 克隆仓库
git clone <repository-url>
cd Agent-Skills

# 将你的skill文件放入对应的团队目录
# 例如：将 my-skill.md 放入 team-a 目录
cp /path/to/your/skill.md skills/infrastructure/

# 提交更改
git add skills/infrastructure/my-skill.md
git commit -m "Add my-skill for team-a"
git push origin main
```

#### 方式二：使用 PR 流程（推荐）

```bash
# 创建新分支
git checkout -b feature/add-new-skill

# 添加skill文件到对应目录
cp /path/to/your/skill.md skills/infrastructure/

# 提交并推送
git add skills/infrastructure/
git commit -m "Add new skill: skill-name"
git push origin feature/add-new-skill

# 在 GitHub 上创建 Pull Request
```

### 2. 使用 Skills

#### 在 Claude Code 中配置

本指南将帮助你将此 marketplace 中的技能安装到你自己的 Claude Code 环境中。

##### 方法一：在 Claude Code 客户端中添加（推荐）

你可以在 Claude Code 客户端中直接添加此 marketplace 并安装技能。

1. **添加 Marketplace**

   在 Claude Code 中运行以下命令：

   ```
   /plugin marketplace add KadenZhang3321/agent-skills
   ```

2. **浏览并安装skill**

   添加 marketplace 后，你可以通过以下两种方式安装技能：

   **方式 A：交互式安装**

   在 Claude Code 中输入 `/plugin` 或点击插件图标，然后：
   - 选择 `Browse and install plugins`（浏览并安装插件）
   - 选择 `KadenZhang3321-agent-skills` marketplace
   - 选择你想要安装的技能（例如 `triton-upgrade`）
   - 点击 `Install now`（立即安装）

   **方式 B：命令行直接安装**

   ```
   /plugin install triton-upgrade@KadenZhang3321-agent-skills
   ```


##### 方法二：手动编辑配置文件

如果你更喜欢手动配置，可以按照以下步骤操作：

1. **编辑 known_marketplaces.json**

   打开或创建 `~/.claude/plugins/known_marketplaces.json` 文件，添加以下内容：

   ```json
   {
     "KadenZhang3321-agent-skills": {
       "source": {
         "source": "github",
         "repo": "KadenZhang3321/agent-skills"
       },
       "installLocation": "~/.claude/plugins/marketplaces/KadenZhang3321-agent-skills",
       "lastUpdated": "2026-02-13T00:00:00.000Z"
     }
   }
   ```

   > **注意**：如果你的 `known_marketplaces.json` 文件中已经有其他 marketplace，请确保添加逗号并保持 JSON 格式正确。

2. **安装skill**

   在终端中运行安装命令：

   ```bash
   claude plugin install triton-upgrade@KadenZhang3321-agent-skills
   ```


##### 方式三：本地克隆使用

```bash
# 1. 克隆仓库到本地
git clone <repository-url> ~/agent-skills

# 2. 在 Claude Code 配置文件中添加技能目录
# 编辑 ~/.claude/config.json 或在项目的 .claude/config.json 中添加：
{
  "skills": {
    "directories": [
      "~/agent-skills/skills/team-a",
      "~/agent-skills/skills/shared"
    ]
  }
}

# 3. 重启 Claude Code 或重新加载配置
```

##### 方式四：直接引用 GitHub 上的 Skills

```bash
# 在 Claude Code 配置中使用 Git URL
# 编辑 ~/.claude/config.json：
{
  "skills": {
    "repositories": [
      {
        "url": "https://github.com/<org>/Agent-Skills.git",
        "path": "skills/team-a"
      },
      {
        "url": "https://github.com/<org>/Agent-Skills.git",
        "path": "skills/shared"
      }
    ]
  }
}
```

#### 验证 Skills 已加载

在 Claude Code 中运行：
```
/help
```
你应该能看到仓库中的 skills 列在可用技能列表中。

### 3. 更新 Skills

```bash
# 如果使用本地克隆方式
cd ~/agent-skills
git pull origin main

# Claude Code 会自动检测到更新，或手动重新加载
```

## 📝 Skill 开发规范

### Skill 文件命名规范

- 使用小写字母和连字符：`my-skill-name.md`
- 名称要描述性强，简洁明了
- 避免使用空格或特殊字符

### Skill 文件结构

每个 skill 应该包含以下部分：

```markdown
# Skill Name

## 描述
简要描述这个 skill 的功能和用途

## 使用场景
说明何时使用这个 skill

## 参数（如果有）
列出所有可用参数及其说明

## 示例
提供使用示例

## 作者
@your-github-username

## 更新日期
YYYY-MM-DD
```

### 目录选择指南

- **infrastructure/**: Infrastructure 团队（技术设施建设）的专属 skills
- **upstream/**: Upstream 团队（上游开发贡献）的专属 skills
- **operation/**: Operation 团队（社区运营）的专属 skills
- **shared/**: 放置所有团队都可能用到的通用 skills

## 🔍 Skills 分类建议

为了更好地组织，建议在各团队目录下按功能分类：

**Infrastructure 团队示例**：
```
skills/infrastructure/
├── devops/            # DevOps 相关
├── monitoring/        # 监控和告警
├── deployment/        # 部署相关
└── automation/        # 自动化工具
```

**Upstream 团队示例**：
```
skills/upstream/
├── contribution/      # 贡献相关
├── code-review/       # 代码审查相关
├── testing/          # 测试相关
└── documentation/    # 文档相关
```

**Operation 团队示例**：
```
skills/operation/
├── content/           # 内容创作相关
├── events/            # 活动策划相关
├── analytics/         # 数据分析相关
└── automation/        # 运营自动化工具
```

## 🤝 贡献指南

1. **创建 Skill 前**：检查是否已有类似功能的 skill
2. **编写文档**：确保你的 skill 有清晰的使用说明
3. **测试**：在提交前测试你的 skill
4. **代码审查**：通过 PR 方式提交，至少需要一位团队成员审查
5. **版本控制**：重大更新时在 skill 文件中注明版本号

## 📋 常见问题

### Q: 如何共享一个 skill 给其他团队？
A: 将 skill 从团队目录移动到 `skills/shared/` 目录。

### Q: 多个团队需要同一个 skill 的不同版本怎么办？
A: 在各自团队目录下维护各自的版本，文件名可以加上版本后缀，如 `deploy-v1.md`, `deploy-v2.md`。

### Q: 如何废弃一个 skill？
A: 不要直接删除，而是在文件开头添加 `[DEPRECATED]` 标记，并说明替代方案，保留至少一个版本周期。

### Q: 配置文件在哪里？
A: Claude Code 的配置文件通常在：
- 全局配置：`~/.claude/config.json`
- 项目配置：`<project-root>/.claude/config.json`

## 🤖 Claude Bot 集成指南

如何将 Claude Bot 集成到组织下的任意仓库，请参阅：[`.github/workflows/README.md`](.github/workflows/README.md)

## 🚀 Claude Code 中心服务调用指南

本仓库提供中心化的 Claude Code 调用服务，其他业务仓库可以通过 `workflow_call` 方式调用。

### 架构优势

- **集中管理 API Key**：调用方无需配置 Anthropic API Key
- **统一权限控制**：通过白名单和权限检查确保安全
- **自动重试机制**：失败时自动重试（最多 3 次）
- **预构建镜像支持**：可选使用预装 Claude CLI 的容器镜像，加速执行

### 快速开始

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

### 前置条件

1. **配置 Secrets**（在业务仓库的 Settings → Secrets 中）：
   - `DISPATCH_TOKEN`：GitHub PAT（需要 `repo` 权限）
   - `CLAUDE_API_KEY`：Anthropic API Key

2. **添加白名单**：联系本仓库管理员，将你的仓库添加到 `.github/allowed-callers.json`

### 详细文档

- **完整调用示例和参数说明**：[EXAMPLE-USAGE.md](EXAMPLE-USAGE.md)
- **调用模板文件**：[.github/workflows/TEMPLATE-CALLER.yml](.github/workflows/TEMPLATE-CALLER.yml)
- **从直接 CC 调用迁移**：[docs/migration-guide.md](docs/migration-guide.md)

### 预构建容器镜像

为了加速执行，可以使用预装 Claude CLI 的容器镜像：

```dockerfile
# Dockerfile 位于仓库根目录
# 构建命令：
#   docker build -t kadenzhang3321/claude-runner:latest .
#   docker push kadenzhang3321/claude-runner:latest
```

在调用时指定 `caller_image` 参数：

```yaml
jobs:
  claude:
    uses: KadenZhang3321/agent-skills/.github/workflows/_claude-code.yml@main
    with:
      caller_repo: ${{ github.repository }}
      caller_image: 'kadenzhang3321/claude-runner:latest'
      custom_prompt: '请分析代码'
    secrets:
      DISPATCH_TOKEN: ${{ secrets.DISPATCH_TOKEN }}
      CLAUDE_API_KEY: ${{ secrets.CLAUDE_API_KEY }}
```

## 📞 联系方式

如有问题或建议，请：
- 提交 Issue
- 在团队频道讨论
- 联系仓库维护者

## 📜 许可证

[根据你的组织政策添加许可证信息]

---

**维护者**: [添加维护者信息]
**最后更新**: 2026-04-15
