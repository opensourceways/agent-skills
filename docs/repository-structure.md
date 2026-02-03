# 仓库结构说明

本文档详细说明了 Agent-Skills 仓库的目录结构和文件组织方式。

## 完整目录结构

```
Agent-Skills/
├── README.md                    # 主文档，包含使用指南和快速开始
├── CONTRIBUTING.md              # 贡献指南
├── .gitignore                   # Git 忽略文件配置
│
├── skills/                      # Skills 主目录
│   ├── team-a/                  # Team A 专属 skills
│   │   ├── README.md           # Team A 说明文档
│   │   ├── code-review/        # 代码审查相关（建议创建）
│   │   ├── testing/            # 测试相关（建议创建）
│   │   ├── deployment/         # 部署相关（建议创建）
│   │   └── documentation/      # 文档相关（建议创建）
│   │
│   ├── team-b/                  # Team B 专属 skills
│   │   ├── README.md           # Team B 说明文档
│   │   ├── code-review/        # 代码审查相关（建议创建）
│   │   ├── testing/            # 测试相关（建议创建）
│   │   ├── deployment/         # 部署相关（建议创建）
│   │   └── documentation/      # 文档相关（建议创建）
│   │
│   ├── team-c/                  # Team C 专属 skills
│   │   ├── README.md           # Team C 说明文档
│   │   ├── code-review/        # 代码审查相关（建议创建）
│   │   ├── testing/            # 测试相关（建议创建）
│   │   ├── deployment/         # 部署相关（建议创建）
│   │   └── documentation/      # 文档相关（建议创建）
│   │
│   └── shared/                  # 跨团队共享 skills
│       ├── README.md           # 共享 skills 说明
│       └── example-skill.md    # 示例 skill（Git 提交助手）
│
├── templates/                   # 模板文件
│   └── skill-template.md       # Skill 创建模板
│
└── docs/                        # 文档目录
    ├── getting-started.md      # 快速入门指南
    └── repository-structure.md # 本文档
```

## 目录说明

### 根目录文件

| 文件 | 说明 |
|------|------|
| `README.md` | 仓库主文档，包含使用指南、配置方法、开发规范等 |
| `CONTRIBUTING.md` | 贡献指南，说明如何提交 skills、PR 规范等 |
| `.gitignore` | Git 忽略规则配置 |

### skills/ 目录

存放所有 skills 的主目录，按团队和用途组织。

#### 团队目录（team-a, team-b, team-c）

每个团队有独立的目录，用于存放该团队专属的 skills。

**建议的子目录结构**：
- `code-review/` - 代码审查相关的 skills
- `testing/` - 测试相关的 skills
- `deployment/` - 部署和发布相关的 skills
- `documentation/` - 文档生成和管理相关的 skills

每个团队可以根据自己的需求调整子目录结构。

#### shared/ 目录

存放所有团队共享的通用 skills。

**放入 shared 的标准**：
- 对多个团队都有价值
- 功能通用，不包含团队特定逻辑
- 经过充分测试和文档化
- 至少两个团队成员审查通过

### templates/ 目录

存放各种模板文件。

| 文件 | 说明 |
|------|------|
| `skill-template.md` | 创建新 skill 时使用的标准模板 |

### docs/ 目录

存放仓库相关的文档。

| 文件 | 说明 |
|------|------|
| `getting-started.md` | 新用户快速入门指南 |
| `repository-structure.md` | 仓库结构说明（本文档） |

## 文件命名规范

### Skill 文件命名

- 使用小写字母
- 单词之间使用连字符（-）分隔
- 扩展名为 `.md`
- 示例：`git-commit-helper.md`, `code-review-assistant.md`

### 目录命名

- 使用小写字母
- 单词之间使用连字符（-）分隔
- 示例：`code-review`, `deployment`

## 组织原则

### 1. 单一职责

每个 skill 文件应该只关注一个特定的功能或任务。

### 2. 可发现性

- 使用描述性的文件名
- 在团队 README 中列出可用的 skills
- 提供清晰的文档和示例

### 3. 可维护性

- 保持文件结构一致
- 定期更新文档
- 及时清理过时的 skills

### 4. 可扩展性

- 目录结构支持添加新的分类
- 支持嵌套子目录
- 预留增长空间

## 最佳实践

### 团队目录管理

1. **定期审查**：每季度审查团队 skills，清理不再使用的
2. **保持同步**：及时从 main 分支拉取更新
3. **文档更新**：添加新 skill 后更新团队 README

### Shared 目录管理

1. **质量门槛**：确保只有高质量的 skills 进入 shared
2. **版本控制**：重大更新时做好版本标记
3. **向后兼容**：尽量保持 API 稳定，避免破坏性变更

### 文档维护

1. **保持最新**：修改代码时同步更新文档
2. **示例验证**：确保文档中的示例可以运行
3. **链接检查**：定期检查文档中的链接是否有效

## 扩展建议

随着仓库的发展，你可能需要：

### 添加新的分类

```bash
# 在团队目录下创建新分类
mkdir skills/team-a/new-category

# 添加说明文档
cat > skills/team-a/new-category/README.md << EOF
# New Category Skills

说明这个分类的用途
EOF
```

### 添加版本管理

```
skills/
└── shared/
    └── deployment/
        ├── deploy-v1.md     # 旧版本
        └── deploy-v2.md     # 新版本
```

### 添加测试

```
tests/
├── team-a/
├── team-b/
└── shared/
```

## 维护检查清单

定期（建议每月）检查：

- [ ] 清理废弃的 skills
- [ ] 更新过时的文档
- [ ] 检查断开的链接
- [ ] 审查新提交的 skills
- [ ] 更新示例和模板
- [ ] 收集用户反馈

## 相关文档

- [README](../README.md) - 仓库主文档
- [快速入门指南](./getting-started.md) - 新用户指南
- [贡献指南](../CONTRIBUTING.md) - 如何贡献

---

**最后更新**: 2026-02-03
