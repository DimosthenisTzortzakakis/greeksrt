# Design

## Theme

**Apple-inspired light SaaS.** Premium, high-contrast, clean. Inspired by base44.com and Apple's product UI. The interface is calm and confident — it gets out of the way.

## Color Palette

Light palette. Apple blue primary, semantic success/error only where state demands it.

| Token | Value | Usage |
|-------|-------|-------|
| `--bg` | `#F5F5F7` | Page background (Apple off-white) |
| `--surface` | `#FFFFFF` | Cards, header, auth card |
| `--surface2` | `#F2F2F7` | Inputs, tabs track, drop zone |
| `--border` | `rgba(0,0,0,0.10)` | Subtle borders |
| `--border-md` | `rgba(0,0,0,0.16)` | Input borders, icon buttons |
| `--accent` | `#0071E3` | CTAs, active state, focus rings |
| `--accent2` | `#0077ED` | Hover state for accent |
| `--accent-lt` | `rgba(0,113,227,0.09)` | Active radio/drop hover tint |
| `--text` | `#1D1D1F` | Body copy (Apple near-black) |
| `--text-2` | `#3C3C43` | Secondary text |
| `--muted` | `#8E8E93` | Labels, placeholders, hints |
| `--success` | `#34C759` | (reference) |
| `--error` | `#FF3B30` | Error messages, logout hover |
| `--focus` | `#0071E3` | Focus rings (3px, 15% alpha) |
| `--shadow-xs` | `0 1px 2px rgba(0,0,0,0.06)` | Cards, player bar |
| `--shadow-sm` | `0 1px 4px …` | Hover elevation |
| `--shadow-lg` | `0 8px 40px …` | Auth card, modals |

## Typography

**Family:** Inter (Google Fonts) → system-ui fallback. `-webkit-font-smoothing: antialiased`.
**Base:** 14px / 1.5 line-height

| Element | Size | Weight | Notes |
|---------|------|--------|-------|
| Page title | 1.75rem | 700 | letter-spacing: −0.04em |
| Auth wordmark | 22px | 700 | letter-spacing: −0.04em |
| App header logo | 15px | 700 | letter-spacing: −0.03em |
| Card title | 11px | 600 | uppercase, letter-spacing: 0.08em |
| Body / labels | 14px | 400/500 | — |
| Auth field label | 12px | 600 | normal case |
| Hint / desc | 12px | 400 | `--muted` |
| Timestamps | 11px | 400 | ui-monospace |

## Spacing

- `--r: 10px` — most cards
- `--r-sm: 7px` — inputs, smaller components
- `--r-lg: 14px` — auth card
- Cards: 20px padding, 10px gap
- Auth card: 40px top, 36px sides
- Body top padding: 5rem (accounts for 52px fixed header)

## Components

### Cards
White background, 1px `var(--border)`, `var(--shadow-sm)`. Clean elevation without harsh borders.

### Segmented Control Tabs (Provider / Language)
Track: `var(--surface2)` with 3px padding. Active pill: white with `var(--shadow-xs)`. Text goes from `--muted` → `--text` on activation. No color accent on active — Apple style.

### Generate Button (Primary CTA)
Full-width, `--accent` fill, white text, 15px/600. Hover: `--accent2` + blue glow shadow.

### Download Button
`#1C9B50` fill, white text. Hover: darker green + shadow.

### Subtitle Card (playing)
Left border accent (`border-left: 3px solid --accent`), subtle background tint (`rgba(0,113,227,0.025)`).

### Auth Screen
Full-viewport overlay, `var(--bg)` background. White card, `var(--shadow-lg)`, `--r-lg` radius. 380px max-width.

### App Header
52px fixed bar, glassmorphism blur (`backdrop-filter: blur(20px) saturate(1.8)`, 88% white). Logo left, user email + logout right.

### Sticky Bar (download)
Same glassmorphism as header — `rgba(255,255,255,0.88)` + blur. Floats above content.

## Motion

- All transitions: 150ms ease (most components)
- Toggle: 220ms cubic-bezier for the knob slide
- No entrance sequences, no choreography

## Anti-patterns (do not introduce)

- Dark backgrounds or OKLCH dark palette
- Gradient text
- `transform: translateY(-1px)` lift on buttons
- Custom scrollbars
- Oklch colors (use hex/rgba for this light theme)
