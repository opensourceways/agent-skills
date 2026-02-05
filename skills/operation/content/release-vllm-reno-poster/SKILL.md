---
name: github-release-poster
description: Generate professional dark-themed release announcement posters for GitHub releases. Use when the user wants to create a release poster, announcement image, changelog graphic, or visual summary for software releases. Triggers include "create release poster", "make announcement image", "generate release graphic", "版本发布海报", or when given a GitHub release URL with a request to visualize it. Automatically adapts to different categories, content lengths, and release note structures.
---

# GitHub Release Poster

Generate professional, dark-themed release announcement posters from GitHub release notes with automatic adaptation to varying content structures.

## Workflow

### 1. Extract Release Information

Fetch the release notes from the GitHub URL:

```python
# Use WebFetch to extract release content
result = webfetch(github_url, prompt="Extract complete release notes including all sections and bullet points")
```

Parse the extracted content to identify:
- Release version and title
- Release date (from GitHub, NOT current date)
- All content sections (Highlights, Features, Performance, etc.)
- Bullet points within each section

### 2. Analyze and Categorize Sections

For each section found in the release notes:

1. **Identify category type** - Match section name to category styles (see `references/category-styles.md`)
2. **Assign colors and icons** - Use predefined mappings or generate new ones for unknown categories
3. **Process content** - Keep original Chinese/English content, preserve technical terms

Common categories:
- Highlights / 核心亮点 → Gold color (#fbbf24), star icon
- Features / 新功能特性 → Green (#10b981), rocket icon
- Performance / 性能优化 → Blue (#3b82f6), speedometer icon
- Dependencies / 依赖更新 → Cyan (#06b6d4), package icon
- Breaking Changes / 重要变更 → Orange (#f59e0b), alert icon
- Known Issues / 已知问题 → Red accent, wrench+alert icon

**For unknown categories**: Generate appropriate styling by:
1. Analyzing semantic meaning of the category name
2. Selecting an unused accent color from the palette
3. Creating an appropriate SVG icon using templates in `references/icon-generation.md`

### 3. Generate HTML Poster

Create the poster using the template structure:

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>{project_name} {version} 正式发布</title>
    <style>
        /* Deep dark theme with glassmorphism effects */
        body {
            background: linear-gradient(135deg, #0a0e27 0%, #1a1f3a 50%, #0a0e27 100%);
        }

        .content-tray {
            background: linear-gradient(180deg, rgba(15, 23, 42, 0.85) 0%, rgba(15, 23, 42, 0.75) 100%);
            backdrop-filter: blur(30px);
            box-shadow: 0 30px 80px rgba(0, 0, 0, 0.6),
                        0 0 0 1px rgba(59, 130, 246, 0.25),
                        inset 0 2px 0 rgba(255, 255, 255, 0.1);
        }

        /* Dynamic accent colors for each category */
        .block-{category} {
            --accent-color: {color};
            --glow-color: {color with alpha};
        }
    </style>
</head>
<body>
    <!-- Hero section with title, version, date -->
    <!-- Timeline sections (alternating left/right layout) -->
    <!-- Footer with GitHub URL -->
</body>
</html>
```

**Key styling principles**:
- Use Inter font family for clean, modern look
- Large, readable fonts (40px titles, 20px content)
- Compact spacing (20px-30px padding in content cards)
- Alternating layout with `nth-child(even)` flex-direction reversal
- SVG icons at 180x180px with glow effects
- Consistent 4px top border accent on each card

### 4. Generate SVG Icons

For each category, create an appropriate SVG icon (see `references/icon-generation.md` for templates):

```html
<svg viewBox="0 0 200 200" xmlns="http://www.w3.org/2000/svg">
    <defs>
        <linearGradient id="grad-{name}">
            <stop offset="0%" style="stop-color:{color1}"/>
            <stop offset="100%" style="stop-color:{color2}"/>
        </linearGradient>
    </defs>
    <g>
        <!-- Icon elements using the gradient -->
    </g>
</svg>
```

**Icon design principles**:
- Use linear gradients matching category accent color
- Add subtle decorative elements (circles, sparkles)
- Keep design simple and recognizable
- Avoid blur filters (they cause rendering issues)
- Match the tech/modern aesthetic

### 5. Adapt to Content Variations

**Different category counts**: The timeline structure automatically adapts. Each category becomes a feature-block with alternating layout.

**Variable content length**:
- Short lists (1-4 items): Display normally
- Long lists (5+ items): Consider grouping or summarizing
- Very long content: May split into sub-sections

**New/unknown categories**:
1. Analyze category name semantics
2. Select appropriate icon type from `references/icon-generation.md`
3. Choose unused accent color from palette
4. Generate consistent styling

**Missing standard categories**: Skill works with any combination of categories found in the release notes.

### 6. Correct Date Handling

**CRITICAL**: Always use the actual release date from GitHub, NOT the current date.

Extract date from GitHub release metadata or tag creation date. Format as `YYYY年MM月DD日`.

### 7. Output and Export

Save the complete HTML to `/sessions/vigilant-trusting-galileo/mnt/outputs/{project}-{version}.html`

Provide the computer:// link to user. User can:
- Open HTML directly in browser for best quality
- Use Chrome DevTools → "Capture full size screenshot" for PNG export
- Or use Claude in Chrome MCP for automated screenshots

## Handling Special Cases

### Mixed Language Content
Preserve original language mixing (Chinese titles, English technical terms). This is typical for Chinese software documentation.

### Technical Terms
Keep code snippets, version numbers, technical abbreviations in original form (e.g., "W8A8-int8", "MoE", "310P").

### Long Release Notes
For releases with 8+ categories, maintain the same structure. The alternating timeline layout handles any number of sections gracefully.

### Ugly or Scary Icons
If default icon seems inappropriate:
- Bug/warning icons can look threatening → use gentler alternatives
- Bright red should be used sparingly for critical issues only
- Test icon aesthetic fit with the overall professional tech style

## Resources

### references/category-styles.md
Complete mapping of common release note categories to accent colors, gradients, and icon recommendations. Consult when styling categories.

### references/icon-generation.md
SVG icon templates and generation patterns for creating new icons that match the poster's aesthetic. Use when encountering unknown categories.

## Quality Standards

The final poster should:
- Use correct release date from GitHub (not today's date)
- Have all content from the release notes (no omissions)
- Display readable fonts (minimum 20px for body text)
- Use compact but not cramped spacing
- Feature professional, non-threatening iconography
- Maintain consistent dark tech aesthetic
- Provide direct computer:// link for user access
