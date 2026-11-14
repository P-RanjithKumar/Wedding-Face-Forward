# Agent Memory & Project Configuration

This file stores important project-specific environment details and paths to ensure Antigravity can operate efficiently within this workspace.

## Environment Paths

- **Node.js Installation**: `C:\Program Files\nodejs`
- **Global NPM Packages**: `C:\Users\ranji\AppData\Roaming\npm` (includes `uipro-cli`)
- **Python**: Available in system PATH (verified).

## Installed Skills

- **UI/UX Pro Max**: Located at `.agent/skills/ui-ux-pro-max`
  - *Main Script*: `python .agent/skills/ui-ux-pro-max/scripts/search.py`
  - *Instruction File*: `.agent/skills/ui-ux-pro-max/SKILL.md`

## Project Context

- **Name**: AURA (formerly Wedding Face Forward)
- **Frameworks**: Moving towards Next.js for frontend, Python backend.
- **Goal**: Premium "Multi-billion dollar Windows app" aesthetic (Mica/OLED dark).

## Current Status & Learnings (Session Update)

### Admin UI Overhaul (AURA Control Center)

- **Frontend Path**: `c:\Users\ranji\Desktop\MYwork\Wedding Face Forward\aura_web`
- **Build System**: Next.js 15+ using **Tailwind CSS v4**.
- **Design Tokens**: Defined in `@theme` block within `globals.css`. Uses `:root` CSS variables for component-level overrides.
- **Typography**:
  - `Inter` (Sans/Body)
  - `Space Grotesk` (Display/Headings)
  - `JetBrains Mono` (Metrics/System Data)

### Critical Technical Notes for Tailwind v4

1. **The Specificity Trap (Mistake 2026-03-10)**: Custom CSS placed after `@import "tailwindcss"` without being wrapped in `@theme` or proper layers can result in "basic" looking UI because Tailwind v4's reset/preflight overrides standard `:root` and element selectors.
2. `@import url(...)` for fonts must be **BEFORE** `@import "tailwindcss"`.
3. Custom variables must be inside `@theme { }` or declared as standard CSS variables with enough specificity to fight the reset.
4. Always use `!important` or high-specificity selectors for key design system utilities (like `animate-shimmer`) to ensure Turbopack/v4 doesn't strip or override them.

### Unfinished Vision (Blockers)

- **Visual Depth**: The user feels the UI is still "too basic" compared to the super-premium mockup.
- **Next Steps**: Enhance `glass-card` with multi-layered shadows, 0.5px inner borders, and refined gradients. Add micro-interactions for every hover.
- **Data State**: UI looks sparse with `0` values; ensure backend is running to see full chart effects.
