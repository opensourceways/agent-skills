# SVG Icon Generation Templates

Templates and patterns for creating consistent SVG icons for release poster categories.

## Icon Specifications

- **ViewBox**: `0 0 200 200`
- **Size**: 180x180px (rendered size)
- **Style**: Flat design with gradients, no blur effects
- **Decorative elements**: Small circles/sparkles at 3-5px radius
- **Stroke width**: 2-3px for main elements
- **Opacity**: Background circles at 0.3, decorative elements at 0.8

## Design Principles

1. **Simplicity**: Icons should be instantly recognizable
2. **Consistency**: Use similar construction patterns across all icons
3. **Gradients**: Always use linear gradients matching accent colors
4. **No filters**: Avoid blur/glow filters (they cause rendering issues)
5. **Tech aesthetic**: Modern, geometric, professional appearance

## Standard Icon Templates

### Star Icon (Highlights)

```html
<svg viewBox="0 0 200 200" xmlns="http://www.w3.org/2000/svg">
    <defs>
        <linearGradient id="grad-star" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" style="stop-color:#fbbf24"/>
            <stop offset="100%" style="stop-color:#f59e0b"/>
        </linearGradient>
    </defs>
    <g>
        <circle cx="100" cy="100" r="60" fill="url(#grad-star)" opacity="0.3"/>
        <path d="M 100 40 L 115 80 L 160 85 L 125 115 L 135 160 L 100 135 L 65 160 L 75 115 L 40 85 L 85 80 Z"
              fill="url(#grad-star)" stroke="#92400e" stroke-width="3"/>
        <circle cx="70" cy="60" r="5" fill="#fbbf24" opacity="0.8"/>
        <circle cx="130" cy="60" r="4" fill="#fbbf24" opacity="0.8"/>
        <circle cx="60" cy="140" r="4" fill="#fbbf24" opacity="0.8"/>
        <circle cx="140" cy="140" r="5" fill="#fbbf24" opacity="0.8"/>
    </g>
</svg>
```

**Pattern**: Central shape with gradient fill + decorative sparkles at corners

### Rocket Icon (Features)

```html
<svg viewBox="0 0 200 200" xmlns="http://www.w3.org/2000/svg">
    <defs>
        <linearGradient id="grad-rocket" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" style="stop-color:#10b981"/>
            <stop offset="100%" style="stop-color:#059669"/>
        </linearGradient>
    </defs>
    <g>
        <ellipse cx="100" cy="100" rx="30" ry="50" fill="url(#grad-rocket)" stroke="#064e3b" stroke-width="3"/>
        <circle cx="100" cy="85" r="12" fill="#d1fae5" stroke="#064e3b" stroke-width="2"/>
        <path d="M 70 110 L 55 135 L 80 125 Z" fill="#34d399" stroke="#064e3b" stroke-width="2"/>
        <path d="M 130 110 L 145 135 L 120 125 Z" fill="#34d399" stroke="#064e3b" stroke-width="2"/>
        <path d="M 85 150 L 80 175 L 100 165 L 120 175 L 115 150 Z" fill="#fbbf24" stroke="#92400e" stroke-width="2"/>
        <circle cx="50" cy="80" r="4" fill="#34d399" opacity="0.8"/>
        <circle cx="150" cy="80" r="4" fill="#34d399" opacity="0.8"/>
    </g>
</svg>
```

**Pattern**: Vertical ellipse body + window + side fins + flame exhaust

### Speedometer Icon (Performance)

```html
<svg viewBox="0 0 200 200" xmlns="http://www.w3.org/2000/svg">
    <defs>
        <linearGradient id="grad-speed" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" style="stop-color:#3b82f6"/>
            <stop offset="100%" style="stop-color:#2563eb"/>
        </linearGradient>
    </defs>
    <g>
        <path d="M 40 120 A 60 60 0 1 1 160 120" fill="none" stroke="url(#grad-speed)" stroke-width="15" stroke-linecap="round"/>
        <circle cx="100" cy="120" r="10" fill="#3b82f6"/>
        <line x1="100" y1="120" x2="140" y2="80" stroke="#3b82f6" stroke-width="4" stroke-linecap="round"/>
        <circle cx="55" cy="105" r="5" fill="#60a5fa"/>
        <circle cx="100" cy="75" r="5" fill="#60a5fa"/>
        <circle cx="145" cy="105" r="5" fill="#60a5fa"/>
        <path d="M 130 140 L 140 155 L 125 150 Z" fill="#fbbf24" opacity="0.8"/>
    </g>
</svg>
```

**Pattern**: Arc gauge + center dot + needle pointer + marker dots

### Puzzle Icon (Others)

```html
<svg viewBox="0 0 200 200" xmlns="http://www.w3.org/2000/svg">
    <defs>
        <linearGradient id="grad-puzzle" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" style="stop-color:#8b5cf6"/>
            <stop offset="100%" style="stop-color:#7c3aed"/>
        </linearGradient>
    </defs>
    <g>
        <rect x="60" y="60" width="50" height="50" fill="url(#grad-puzzle)" stroke="#5b21b6" stroke-width="3" rx="5"/>
        <rect x="110" y="90" width="50" height="50" fill="url(#grad-puzzle)" stroke="#5b21b6" stroke-width="3" rx="5"/>
        <path d="M 110 85 Q 110 75 120 75 Q 130 75 130 85" fill="#a78bfa" stroke="#5b21b6" stroke-width="2"/>
        <circle cx="50" cy="70" r="4" fill="#a78bfa" opacity="0.8"/>
        <circle cx="160" cy="130" r="4" fill="#a78bfa" opacity="0.8"/>
    </g>
</svg>
```

**Pattern**: Interlocking rectangular pieces with connecting tabs

### Package Icon (Dependencies)

```html
<svg viewBox="0 0 200 200" xmlns="http://www.w3.org/2000/svg">
    <defs>
        <linearGradient id="grad-package" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" style="stop-color:#06b6d4"/>
            <stop offset="100%" style="stop-color:#0891b2"/>
        </linearGradient>
    </defs>
    <g>
        <path d="M 100 60 L 150 85 L 150 135 L 100 160 L 50 135 L 50 85 Z"
              fill="url(#grad-package)" stroke="#164e63" stroke-width="3"/>
        <path d="M 100 60 L 100 160" stroke="#164e63" stroke-width="3"/>
        <path d="M 50 85 L 100 110 L 150 85" stroke="#164e63" stroke-width="3"/>
        <circle cx="100" cy="85" r="8" fill="#22d3ee"/>
        <circle cx="60" cy="120" r="4" fill="#22d3ee" opacity="0.8"/>
        <circle cx="140" cy="120" r="4" fill="#22d3ee" opacity="0.8"/>
    </g>
</svg>
```

**Pattern**: 3D hexagonal box with center line and horizontal band

### Bell/Notification Icon (Breaking Changes)

```html
<svg viewBox="0 0 200 200" xmlns="http://www.w3.org/2000/svg">
    <defs>
        <linearGradient id="grad-bell" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" style="stop-color:#f59e0b"/>
            <stop offset="100%" style="stop-color:#d97706"/>
        </linearGradient>
    </defs>
    <g>
        <path d="M 75 120 L 75 85 Q 75 60 100 60 Q 125 60 125 85 L 125 120 Q 135 130 135 140 L 65 140 Q 65 130 75 120 Z"
              fill="url(#grad-bell)" stroke="#92400e" stroke-width="3"/>
        <rect x="95" y="50" width="10" height="15" fill="#fbbf24" rx="2"/>
        <path d="M 90 145 Q 90 155 100 155 Q 110 155 110 145" fill="#fbbf24" stroke="#92400e" stroke-width="2"/>
        <circle cx="130" cy="70" r="15" fill="#ef4444" stroke="#7f1d1d" stroke-width="2"/>
        <text x="130" y="77" font-size="20" font-weight="bold" text-anchor="middle" fill="white">!</text>
    </g>
</svg>
```

**Pattern**: Bell shape + alert badge with exclamation mark

### Wrench+Alert Icon (Known Issues)

```html
<svg viewBox="0 0 200 200" xmlns="http://www.w3.org/2000/svg">
    <defs>
        <linearGradient id="grad-wrench" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" style="stop-color:#64748b"/>
            <stop offset="100%" style="stop-color:#475569"/>
        </linearGradient>
    </defs>
    <g>
        <path d="M 70 130 L 90 110 Q 95 105 90 100 L 80 90 Q 75 85 80 80 L 95 65 Q 100 60 105 65 L 115 75 Q 120 80 125 75 L 145 95 Q 140 100 135 95 L 125 105 Q 120 110 125 115 L 135 125 Q 130 130 125 125 L 115 135 Q 110 140 105 135 L 95 145 Q 90 140 95 135 L 85 125 Q 80 120 75 125 Z"
              fill="url(#grad-wrench)" stroke="#1e293b" stroke-width="2"/>
        <circle cx="140" cy="70" r="18" fill="#fbbf24" stroke="#92400e" stroke-width="2"/>
        <text x="140" y="78" font-size="22" font-weight="bold" text-anchor="middle" fill="#7f1d1d">!</text>
    </g>
</svg>
```

**Pattern**: Wrench tool + warning badge (friendly, not threatening)

## Icon Generation for New Categories

When creating icons for unknown categories:

1. **Analyze semantic meaning**: What does this category represent?
2. **Choose base shape**:
   - Circular: Completeness, cycles, continuous (e.g., testing, monitoring)
   - Angular: Structure, precision, technical (e.g., architecture, schemas)
   - Organic: Growth, evolution, natural (e.g., community, adoption)

3. **Select from common tech iconography**:
   - Shield: Security, protection
   - Document: Documentation, guides
   - Graph: Analytics, metrics
   - Gear: Configuration, settings
   - Lightning: Speed, power
   - Lock: Security, privacy
   - Network: Connectivity, integration
   - Code brackets: Development, technical

4. **Apply gradient**: Use assigned accent color from category-styles.md

5. **Add decorative elements**: 2-4 small circles as sparkles/highlights

6. **Test rendering**: Ensure no blur filters that cause issues

## Example: Creating Security Icon

For a new "Security" category:

```html
<svg viewBox="0 0 200 200" xmlns="http://www.w3.org/2000/svg">
    <defs>
        <linearGradient id="grad-security" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" style="stop-color:#ec4899"/>  <!-- Pink from secondary palette -->
            <stop offset="100%" style="stop-color:#db2777"/>
        </linearGradient>
    </defs>
    <g>
        <!-- Shield shape -->
        <path d="M 100 50 L 140 70 Q 145 100 140 130 Q 130 155 100 165 Q 70 155 60 130 Q 55 100 60 70 Z"
              fill="url(#grad-security)" stroke="#831843" stroke-width="3"/>
        <!-- Lock symbol -->
        <rect x="90" y="95" width="20" height="25" fill="#fce7f3" rx="3"/>
        <path d="M 87 95 L 87 85 Q 87 75 100 75 Q 113 85 113 85 L 113 95"
              fill="none" stroke="#fce7f3" stroke-width="4"/>
        <!-- Decorative sparkles -->
        <circle cx="65" cy="80" r="4" fill="#f9a8d4" opacity="0.8"/>
        <circle cx="135" cy="80" r="4" fill="#f9a8d4" opacity="0.8"/>
    </g>
</svg>
```

**Semantic match**: Security → Shield (protection) + Lock (secured)
