# 快速参考

## 常用命令

### 克隆和配置

```bash
# 克隆仓库
git clone <repository-url> ~/agent-skills

# 配置 Claude Code (全局)
cat > ~/.claude/config.json << 'EOF'
{
  "skills": {
    "directories": [
      "~/agent-skills/skills/team-a",
      "~/agent-skills/skills/shared"
    ]
  }
}
EOF
```

### 创建新 Skill

```bash
# 复制模板
cp templates/skill-template.md skills/team-a/my-new-skill.md

# 编辑文件
# vim/code/nano skills/team-a/my-new-skill.md

# 提交
git add skills/team-a/my-new-skill.md
git commit -m "Add skill: my-new-skill"
git push origin main
```

### 更新 Skills

```bash
# 更新本地仓库
cd ~/agent-skills
git pull origin main

# Claude Code 会自动检测更新
```

### 使用 PR 流程

```bash
# 创建分支
git checkout -b feature/my-skill

# 添加 skill
cp templates/skill-template.md skills/team-a/my-skill.md
# 编辑文件...

# 提交
git add skills/team-a/my-skill.md
git commit -m "Add skill: my-skill"
git push origin feature/my-skill

# 在 GitHub 上创建 PR
```

## 文件路径速查

| 路径 | 用途 |
|------|------|
| `skills/team-a/` | Team A 的 skills |
| `skills/team-b/` | Team B 的 skills |
| `skills/team-c/` | Team C 的 skills |
| `skills/shared/` | 共享 skills |
| `templates/skill-template.md` | Skill 模板 |
| `docs/getting-started.md` | 入门指南 |
| `CONTRIBUTING.md` | 贡献指南 |

## Skill 文件结构速查

```markdown
# Skill Name

## 描述
简要说明

## 使用场景
- 场景1
- 场景2

## 前置要求
- 要求1
- 要求2

## 参数
| 参数名 | 类型 | 必需 | 默认值 | 描述 |
|--------|------|------|--------|------|

## 使用方法
### 基本用法
```bash
/skill-name
```

### 带参数用法
```bash
/skill-name --param="value"
```

## 示例
[提供具体示例]

## 注意事项
[列出注意事项]

## 作者
@username

## 最后更新
YYYY-MM-DD
```

## 配置文件位置

| 配置类型 | 文件路径 |
|----------|----------|
| 全局配置 | `~/.claude/config.json` |
| 项目配置 | `<project>/.claude/config.json` |

## 配置示例

### 本地目录配置

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

### Git 仓库配置

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

## 验证 Skills

```bash
# 在 Claude Code 中运行
/help

# 应该看到仓库中的 skills
```

## 命名规范

### Skill 文件名
- ✅ `my-skill-name.md`
- ❌ `My_Skill_Name.md`
- ❌ `my skill name.md`

### 目录名
- ✅ `code-review`
- ❌ `Code_Review`
- ❌ `code review`

## PR 标题格式

- `Add skill: <name>` - 新增
- `Update skill: <name>` - 更新
- `Fix skill: <name>` - 修复
- `Deprecate skill: <name>` - 废弃

## 常见问题快速解决

### Skills 不显示？
1. 检查配置文件路径
2. 检查 JSON 格式
3. 重启 Claude Code
4. 查看日志

### 配置不生效？
1. 确认路径正确（使用绝对路径）
2. 验证 JSON 格式
3. 重启 Claude Code

### 如何废弃 Skill？
1. 在文件开头添加 `[DEPRECATED]`
2. 说明原因和替代方案
3. 保留至少一个月

## 联系方式

- Issues: 报告问题
- PR: 贡献代码
- 团队频道: 日常讨论

---

**快速链接**:
- [主 README](../README.md)
- [入门指南](./getting-started.md)
- [贡献指南](../CONTRIBUTING.md)
- [仓库结构](./repository-structure.md)
