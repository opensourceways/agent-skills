# Git Commit Helper

## 描述

帮助生成规范的 Git 提交信息，遵循 Conventional Commits 规范。

## 使用场景

- 需要创建符合团队规范的提交信息时
- 不确定如何描述代码变更时
- 想要保持提交历史清晰易读时

## 前置要求

- Git 已安装并配置
- 当前目录为 Git 仓库

## 参数

| 参数名 | 类型 | 必需 | 默认值 | 描述 |
|--------|------|------|--------|------|
| type | string | 否 | - | 提交类型（feat/fix/docs等） |
| scope | string | 否 | - | 影响范围 |

## 使用方法

### 基本用法

```bash
/git-commit-helper
```

Claude Code 会分析当前的代码变更，并建议合适的提交信息。

### 带参数用法

```bash
/git-commit-helper --type=feat --scope=auth
```

## 示例

### 示例1：自动分析提交

```bash
/git-commit-helper
```

**Claude 的输出**：
```
根据你的代码变更，建议使用以下提交信息：

feat(user): add password reset functionality

详细说明：
- 添加了密码重置接口
- 实现了邮件验证流程
- 更新了用户模型
```

### 示例2：指定类型

```bash
/git-commit-helper --type=fix
```

**Claude 的输出**：
```
fix(api): resolve null pointer exception in user service

修复了当用户数据为空时的空指针异常问题
```

## 注意事项

- 确保在执行前已经暂存了需要提交的文件
- 提交信息会遵循 Conventional Commits 规范
- 支持的类型：feat, fix, docs, style, refactor, test, chore

## 相关 Skills

- [代码审查助手](./code-review-helper.md)
- [变更日志生成器](./changelog-generator.md)

## 更新日志

### v1.0.0 (2026-02-03)
- 初始版本

## 作者

@example-author

## 最后更新

2026-02-03
