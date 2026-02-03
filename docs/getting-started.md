# 快速入门指南

本指南将帮助你快速上手使用 Agent-Skills 仓库。

## 第一步：克隆仓库

```bash
git clone <repository-url> ~/agent-skills
cd ~/agent-skills
```

## 第二步：配置 Claude Code

### 选项 A：配置全局 Skills 目录

编辑 `~/.claude/config.json`：

```json
{
  "skills": {
    "directories": [
      "~/agent-skills/skills/team-a",
      "~/agent-skills/skills/shared"
    ]
  }
}
```

### 选项 B：配置项目级 Skills 目录

在你的项目根目录创建 `.claude/config.json`：

```json
{
  "skills": {
    "directories": [
      "~/agent-skills/skills/team-b",
      "~/agent-skills/skills/shared"
    ]
  }
}
```

### 选项 C：直接从 Git 仓库加载

```json
{
  "skills": {
    "repositories": [
      {
        "url": "https://github.com/<org>/Agent-Skills.git",
        "path": "skills/team-a"
      }
    ]
  }
}
```

## 第三步：验证配置

在 Claude Code 中运行：

```
/help
```

你应该能看到仓库中的 skills 列在可用技能列表中。

## 第四步：使用 Skill

找到你需要的 skill 后，使用 `/` 命令调用：

```
/skill-name
```

或带参数：

```
/skill-name --param="value"
```

## 第五步：创建你的第一个 Skill

1. 复制模板文件：
   ```bash
   cp templates/skill-template.md skills/team-a/my-first-skill.md
   ```

2. 编辑文件，填写你的 skill 内容

3. 测试 skill：
   ```bash
   # 重新加载 Claude Code 配置
   # 然后使用 /my-first-skill 测试
   ```

4. 提交到仓库：
   ```bash
   git add skills/team-a/my-first-skill.md
   git commit -m "Add my first skill"
   git push origin main
   ```

## 常见问题

### 配置文件不生效？

1. 确保 JSON 格式正确（可以使用 JSON 验证工具）
2. 确保路径正确（使用绝对路径或 `~` 表示 home 目录）
3. 重启 Claude Code

### Skills 没有显示？

1. 检查 skill 文件是否为 `.md` 格式
2. 检查文件名是否符合规范（小写字母和连字符）
3. 查看 Claude Code 日志是否有错误信息

### 如何更新 Skills？

```bash
cd ~/agent-skills
git pull origin main
# Claude Code 会自动检测更新
```

## 下一步

- 浏览 [shared](../skills/shared/) 目录查看可用的共享 skills
- 阅读 [Skill 开发规范](../README.md#-skill-开发规范)
- 查看 [示例 skill](../skills/shared/example-skill.md)

## 需要帮助？

- 查看主 [README](../README.md)
- 提交 Issue
- 联系团队维护者
