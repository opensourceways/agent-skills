# llms.txt

## 标准结构

1. 一级标题后跟站点名称
2. Blockquote 概述：简短摘要，说明项目的核心信息。
3. 零个或多个 Markdown 段落或列表（不带任何级别的标题），提供额外背景信息。
4. 零个或多个由二级标题分隔的页面列表，列表项最好带页面描述
5. 最后可以加一个`## Optional`章节，用于次要信息，LLM 在需要缩短上下文时可以跳过。

示例：

```markdown
# 站点标题

> 站点描述

额外信息/详细描述

## 章节

- [页面标题](https://link_url): 页面描述

## Optional

- [页面标题](https://link_url)
```

## 文档的md版本

如果可以的话建议为每篇 html 都生成一个 markdown 版本的链接

例如:

html 地址：`https://www.fastht.ml/docs/tutorials/by_example.html`

markdown 版本地址：`https://www.fastht.ml/docs/tutorials/by_example.html.md`

`llms.txt`中指向页面的地址可以替换成 markdown 版本的地址

```
- [Link title](https://link_url.html.md): Optional link details
```

## llms-full.txt

没有严格固定的格式，一般来说将所有文档整合到这一个文件中，需使用 markdown 语法，可以用二级、三级标题为文档进行分类，可以按照以下格式：

```markdown
# 站点标题

> 站点描述

额外信息/详细描述

## 章节

---
url: path/to/doc1.md
---
文档具体内容

---

---
url: path/to/doc2.md
---
文档具体内容
```

## 要点

- 简洁明了：避免冗余，突出核心信息，避免像sitemap一样列出所有页面。

- 结构化：用标题、列表组织内容，方便 LLM快速定位。

- 链接带注释：每个链接最好附简短说明，帮助模型理解用途。

- 分层信息：核心内容放在前面，次要信息放在 “Optional” 部分。
