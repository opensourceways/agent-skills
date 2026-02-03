# 贡献指南

感谢你为 Agent-Skills 仓库做出贡献！

## 贡献流程

### 1. 提交 Skill

#### 步骤 1：选择合适的目录

- **团队专属 skill**: 放在 `skills/team-{a,b,c}/` 目录
- **跨团队共享 skill**: 放在 `skills/shared/` 目录

#### 步骤 2：使用模板创建 Skill

```bash
# 复制模板
cp templates/skill-template.md skills/team-a/your-skill-name.md

# 编辑文件
# 填写所有必需的章节
```

#### 步骤 3：遵循命名规范

- 使用小写字母和连字符：`my-skill-name.md`
- 名称应该简洁且描述性强
- 避免使用空格、下划线或特殊字符

#### 步骤 4：编写完整文档

确保你的 skill 包含：
- 清晰的描述
- 使用场景说明
- 参数说明（如果有）
- 至少一个使用示例
- 作者信息和更新日期

#### 步骤 5：测试

在提交前，确保：
- Skill 能够正常工作
- 文档准确无误
- 示例可以运行

#### 步骤 6：提交 Pull Request

```bash
# 创建新分支
git checkout -b feature/add-skill-name

# 添加文件
git add skills/team-a/your-skill-name.md

# 提交
git commit -m "Add skill: your-skill-name"

# 推送
git push origin feature/add-skill-name
```

然后在 GitHub 上创建 Pull Request。

### 2. Pull Request 规范

#### PR 标题格式

- `Add skill: <skill-name>` - 新增 skill
- `Update skill: <skill-name>` - 更新现有 skill
- `Fix skill: <skill-name>` - 修复 skill 问题
- `Deprecate skill: <skill-name>` - 废弃 skill

#### PR 描述应包含

- Skill 的简要说明
- 解决的问题或新增的功能
- 使用示例
- 相关 issue（如果有）

#### PR 审查要求

- 团队 skill：至少需要 1 位团队成员审查
- 共享 skill：至少需要 2 位来自不同团队的成员审查

### 3. 更新现有 Skill

如果要更新现有的 skill：

1. 在文件中更新"更新日志"章节
2. 更新"最后更新"日期
3. 如果是重大变更，考虑更新版本号
4. 在 PR 中说明变更原因

### 4. 废弃 Skill

不要直接删除 skill，而是：

1. 在文件开头添加 `[DEPRECATED]` 标记
2. 说明废弃原因
3. 提供替代方案或迁移指南
4. 更新团队目录的 README
5. 至少保留一个发布周期（建议 1 个月）

示例：

```markdown
# [DEPRECATED] Old Skill Name

**此 skill 已废弃**，请使用 [new-skill](./new-skill.md) 替代。

**废弃原因**：功能已集成到 new-skill 中

**迁移指南**：
- 原来的 `/old-skill --param=value`
- 现在使用 `/new-skill --param=value`

---

[原有文档内容...]
```

## 代码规范

### Markdown 格式

- 使用标准 Markdown 格式
- 代码块指定语言：\`\`\`bash, \`\`\`json 等
- 保持一致的标题层级
- 使用表格来展示参数信息

### 文件组织

- 每个 skill 一个独立文件
- 相关的 skills 可以放在子目录中
- 保持目录结构清晰

### 文档质量

- 使用清晰、简洁的语言
- 提供实际可用的示例
- 包含常见问题的注意事项
- 链接到相关的 skills

## 审查清单

在提交 PR 前，请检查：

- [ ] Skill 文件命名符合规范
- [ ] 使用了模板结构
- [ ] 包含完整的文档
- [ ] 提供了使用示例
- [ ] 测试过 skill 可以正常工作
- [ ] 更新了相应目录的 README（如果需要）
- [ ] PR 标题和描述清晰
- [ ] 没有包含敏感信息（密码、密钥等）

## 沟通渠道

- GitHub Issues：报告问题、提出建议
- Pull Requests：代码审查、讨论实现细节
- 团队频道：日常讨论、快速咨询

## 行为准则

- 尊重他人的工作和意见
- 提供建设性的反馈
- 保持专业和友善
- 及时响应审查请求

## 问题反馈

如果遇到问题：

1. 查看现有 Issues 是否已有相关讨论
2. 如果没有，创建新 Issue 并提供：
   - 问题描述
   - 复现步骤
   - 预期行为 vs 实际行为
   - 环境信息（OS、Claude Code 版本等）

## 许可证

通过提交贡献，你同意你的贡献将按照本仓库的许可证进行授权。

---

再次感谢你的贡献！
