# Category Styles Reference

Complete mapping of release note categories to visual styling (colors, gradients, icons).

## Standard Categories

### Highlights / 核心亮点 / Release Highlights
- **Accent Color**: `#fbbf24` (amber/gold)
- **Glow Color**: `rgba(251, 191, 36, 0.4)`
- **Gradient**: `#fbbf24` → `#f59e0b`
- **Icon**: Star with sparkles
- **Semantic**: Major features, key improvements, flagship changes
- **Category Badge**: `⭐ HIGHLIGHTS`

### Features / 新功能特性 / New Features
- **Accent Color**: `#10b981` (emerald green)
- **Glow Color**: `rgba(16, 185, 129, 0.4)`
- **Gradient**: `#10b981` → `#059669`
- **Icon**: Rocket with flames
- **Semantic**: New capabilities, feature additions, functionality expansions
- **Category Badge**: `🚀 FEATURES`

### Performance / 性能优化 / Performance Improvements
- **Accent Color**: `#3b82f6` (blue)
- **Glow Color**: `rgba(59, 130, 246, 0.4)`
- **Gradient**: `#3b82f6` → `#2563eb`
- **Icon**: Speedometer/gauge
- **Semantic**: Speed improvements, optimizations, efficiency gains
- **Category Badge**: `⚡ PERFORMANCE`

### Others / 其他更新 / Other Changes
- **Accent Color**: `#8b5cf6` (purple/violet)
- **Glow Color**: `rgba(139, 92, 246, 0.4)`
- **Gradient**: `#8b5cf6` → `#7c3aed`
- **Icon**: Puzzle pieces
- **Semantic**: Miscellaneous changes, minor updates, various improvements
- **Category Badge**: `🧩 OTHERS`

### Dependencies / 依赖更新 / Dependency Updates
- **Accent Color**: `#06b6d4` (cyan)
- **Glow Color**: `rgba(6, 182, 212, 0.4)`
- **Gradient**: `#06b6d4` → `#0891b2`
- **Icon**: Package/box
- **Semantic**: Library updates, dependency changes, package upgrades
- **Category Badge**: `📦 DEPENDENCIES`

### Deprecation & Breaking Changes / 重要变更通知 / Breaking Changes
- **Accent Color**: `#f59e0b` (orange/amber)
- **Glow Color**: `rgba(245, 158, 11, 0.4)`
- **Gradient**: `#f59e0b` → `#d97706`
- **Icon**: Bell/notification with alert badge
- **Semantic**: API changes, deprecated features, migration requirements
- **Category Badge**: `🔔 DEPRECATION & BREAKING CHANGES`

### Known Issues / 已知问题 / Bug Reports
- **Accent Color**: `#ef4444` (red, use sparingly)
- **Glow Color**: `rgba(239, 68, 68, 0.4)`
- **Gradient**: `#ef4444` → `#dc2626`
- **Icon**: Wrench + alert badge (NOT scary bug/triangle)
- **Semantic**: Known bugs, issues to watch, temporary limitations
- **Category Badge**: `🔧 KNOWN ISSUES`

## Available Color Palette

When encountering new categories, select from unused colors:

Primary palette (already assigned above):
- Gold `#fbbf24` - Highlights
- Green `#10b981` - Features
- Blue `#3b82f6` - Performance
- Purple `#8b5cf6` - Others
- Cyan `#06b6d4` - Dependencies
- Orange `#f59e0b` - Breaking Changes
- Red `#ef4444` - Issues

Secondary palette (available for new categories):
- Pink `#ec4899`
- Indigo `#6366f1`
- Teal `#14b8a6`
- Lime `#84cc16`
- Rose `#f43f5e`
- Sky `#0ea5e9`

## Semantic Matching Guidelines

When encountering unknown categories, match them to appropriate styling:

**Success/Achievement themes** → Green, Gold, or Lime
- Examples: Achievements, Milestones, Successes

**Technical/Infrastructure themes** → Blue, Cyan, or Indigo
- Examples: Infrastructure, Architecture, Technical Debt

**User Experience themes** → Purple, Pink, or Rose
- Examples: UX Improvements, UI Updates, Accessibility

**Security themes** → Orange or Red (use red sparingly)
- Examples: Security Fixes, Vulnerabilities, Patches

**Documentation themes** → Sky or Teal
- Examples: Documentation, Examples, Guides

**Testing/Quality themes** → Indigo or Purple
- Examples: Testing, Quality Assurance, Validation

## CSS Class Naming Convention

For each category, generate a CSS class:

```css
.block-{category-slug} {
    --accent-color: {hex-color};
    --glow-color: {rgba-color};
}
```

Examples:
- `.block-highlights`
- `.block-features`
- `.block-performance`
- `.block-security` (for new Security category)

## Gradient Definition Pattern

All icons use linear gradients in their SVG defs:

```html
<linearGradient id="grad-{name}" x1="0%" y1="0%" x2="100%" y2="100%">
    <stop offset="0%" style="stop-color:{lighter-shade}"/>
    <stop offset="100%" style="stop-color:{darker-shade}"/>
</linearGradient>
```

The darker shade should be approximately 1-2 stops darker on the Tailwind color scale.
