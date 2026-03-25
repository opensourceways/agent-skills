---
name: nuxt-shadcn-vue
description: 初始化或配置 Nuxt 3 + shadcn-vue 项目，包括 Tailwind CSS 集成、组件安装与主题配置。适用于新建项目或为现有 Nuxt 3 项目添加 shadcn-vue。
allowed-tools: Bash(npm create:*), Bash(npx:*), Bash(npm install:*), Bash(npm run:*), Read, Write, Edit, Glob
---

## 使用Nuxt并配置 shadcn-vue 组件库创建项目模板

在 Nuxt 3 项目中初始化并配置 shadcn-vue 组件库。完成后项目应具备：Tailwind CSS、shadcn-vue、可用的组件示例，以及正确的 TypeScript 路径别名。

所有文件读写操作直接执行，无需用户确认。执行 npm/npx 命令前需确认工作目录正确。

---

## Step 0：识别输入

分析用户输入，判断操作模式：

- **新建项目**（提供项目名称，或当前目录为空）：执行 Step 1 → Step 2 → Step 3 → Step 4
- **现有项目**（当前目录已有 `nuxt.config.ts`）：跳过 Step 1，从 Step 2 开始
- **添加组件**（项目已配置 shadcn-vue，用户指定组件名）：直接执行 Step 3

---

## Step 1：创建 Nuxt 3 项目

```bash
# 使用官方脚手架创建项目，选择 TypeScript
npm create nuxt@latest <project-name>
cd <project-name>
```

创建时选项建议：
- Package manager: `npm`
- TypeScript: `Yes`
- ESLint: 按需

---

## Step 2：安装并配置依赖

### 2a. 安装 Tailwind CSS

```bash
npm install -D @nuxtjs/tailwindcss
```

在 `nuxt.config.ts` 的 `modules` 中添加：

```ts
// nuxt.config.ts
export default defineNuxtConfig({
  modules: ['@nuxtjs/tailwindcss'],
})
```

创建 `tailwind.config.ts`：

```ts
import type { Config } from 'tailwindcss'
import { fontFamily } from 'tailwindcss/defaultTheme'

export default {
  darkMode: ['class'],
  safelist: ['dark'],
  content: [],
  theme: {
    container: {
      center: true,
      padding: '2rem',
      screens: { '2xl': '1400px' },
    },
    extend: {
      colors: {
        border: 'hsl(var(--border))',
        input: 'hsl(var(--input))',
        ring: 'hsl(var(--ring))',
        background: 'hsl(var(--background))',
        foreground: 'hsl(var(--foreground))',
        primary: {
          DEFAULT: 'hsl(var(--primary))',
          foreground: 'hsl(var(--primary-foreground))',
        },
        secondary: {
          DEFAULT: 'hsl(var(--secondary))',
          foreground: 'hsl(var(--secondary-foreground))',
        },
        destructive: {
          DEFAULT: 'hsl(var(--destructive))',
          foreground: 'hsl(var(--destructive-foreground))',
        },
        muted: {
          DEFAULT: 'hsl(var(--muted))',
          foreground: 'hsl(var(--muted-foreground))',
        },
        accent: {
          DEFAULT: 'hsl(var(--accent))',
          foreground: 'hsl(var(--accent-foreground))',
        },
        card: {
          DEFAULT: 'hsl(var(--card))',
          foreground: 'hsl(var(--card-foreground))',
        },
      },
      borderRadius: {
        xl: 'calc(var(--radius) + 4px)',
        lg: 'var(--radius)',
        md: 'calc(var(--radius) - 2px)',
        sm: 'calc(var(--radius) - 4px)',
      },
      fontFamily: {
        sans: ['var(--font-sans)', ...fontFamily.sans],
      },
    },
  },
} satisfies Config
```

### 2b. 安装 shadcn-vue 及核心依赖

```bash
npm install -D shadcn-nuxt
npm install radix-vue class-variance-authority clsx tailwind-merge lucide-vue-next @vueuse/core
```

在 `nuxt.config.ts` 添加模块配置：

```ts
export default defineNuxtConfig({
  modules: ['@nuxtjs/tailwindcss', 'shadcn-nuxt'],
  shadcn: {
    prefix: '',                    // 组件前缀，留空则无前缀
    componentDir: './components/ui',
  },
})
```

### 2c. 配置 TypeScript 路径别名

检查 `tsconfig.json`，确保包含：

```json
{
  "compilerOptions": {
    "baseUrl": ".",
    "paths": {
      "@/*": ["./*"]
    }
  }
}
```

### 2d. 初始化 shadcn-vue

```bash
npx shadcn-vue@latest init
```

交互式选项：
- Style: `Default`（或 `New York`）
- Base color: 按需（如 `Slate`、`Zinc`）
- CSS variables: `Yes`

该命令会自动生成 `components/ui/` 目录并将 CSS 变量写入全局样式文件。

---

## Step 3：添加组件

### 添加单个组件

```bash
npx shadcn-vue@latest add <component-name>
```

### 批量添加常用组件

```bash
npx shadcn-vue@latest add button input label card dialog sheet toast
```

### 常用组件参考

| 组件 | 命令 | 用途 |
|------|------|------|
| Button | `add button` | 按钮 |
| Input | `add input` | 输入框 |
| Label | `add label` | 标签 |
| Card | `add card` | 卡片容器 |
| Dialog | `add dialog` | 模态弹窗 |
| Sheet | `add sheet` | 侧边抽屉 |
| Toast | `add toast` | 通知提示 |
| Table | `add table` | 数据表格 |
| Form | `add form` | 表单（含验证） |
| Select | `add select` | 下拉选择 |
| Dropdown Menu | `add dropdown-menu` | 下拉菜单 |
| Navigation Menu | `add navigation-menu` | 导航菜单 |

---

## Step 4：验证与示例

### 创建验证页面

在 `pages/index.vue` 中添加示例组件，验证安装是否成功：

```vue
<template>
  <div class="container py-10">
    <h1 class="text-3xl font-bold mb-6">shadcn-vue 已就绪</h1>
    <div class="flex gap-4">
      <Button>默认按钮</Button>
      <Button variant="outline">线框按钮</Button>
      <Button variant="destructive">危险操作</Button>
    </div>
  </div>
</template>
```

### 启动开发服务器

```bash
npm run dev
```

访问 `http://localhost:3000`，确认样式和组件正常渲染。

---

## 完成后目录结构

```
<project>/
├── components/
│   └── ui/              # shadcn-vue 生成的组件
│       ├── button/
│       │   └── Button.vue
│       └── ...
├── assets/
│   └── css/
│       └── tailwind.css  # 包含 shadcn-vue CSS 变量
├── pages/
│   └── index.vue
├── nuxt.config.ts
├── tailwind.config.ts
└── tsconfig.json
```

---

## 常见问题排查

| 问题 | 原因 | 解决方案 |
|------|------|---------|
| 组件样式不生效 | Tailwind 未加载 | 检查 `nuxt.config.ts` 的 `modules` 中包含 `@nuxtjs/tailwindcss` |
| 颜色 CSS 变量缺失 | `init` 未生成变量 | 重新运行 `npx shadcn-vue@latest init`，确认写入全局 CSS |
| `@/` 路径别名报错 | tsconfig 未配置 | 检查 `tsconfig.json` 的 `paths` 字段 |
| 组件自动导入失败 | 模块未注册 | 确认 `shadcn-nuxt` 已在 `nuxt.config.ts` 的 `modules` 中 |
| 暗色模式不生效 | `darkMode` 配置错误 | 确认 `tailwind.config.ts` 中 `darkMode: ['class']` |

---

## 输出格式

操作完成后输出：

```
✅ Nuxt 3 + shadcn-vue 配置完成

📦 已安装：
  - @nuxtjs/tailwindcss
  - shadcn-nuxt
  - radix-vue + 相关依赖

🧩 已添加组件：[组件列表]

📁 组件目录：./components/ui/

🚀 启动命令：npm run dev
```