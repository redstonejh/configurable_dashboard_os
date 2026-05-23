# Visual Audit

## Current Issues

- The toolbar and time range controls were recently softened with one-off rgba values. That made the top bar look faded and unfinished instead of intentionally quiet.
- Panels still use per-theme border, header, surface, and glow values directly. This keeps the configurable colors working, but the intensity differs too much between themes.
- Metric cards use a separate card material from panels, then borrow panel placeholder variables. This creates a mixed system: widget content matches, but the outer card shell does not.
- Settings, detail pages, forms, tables, toast notifications, dropdowns, and sticky save surfaces still use older `var(--line)`, `var(--shadow)`, and raw rgba backgrounds.
- Menus and palettes are tied to panel theme colors, while toolbar menus and settings surfaces are tied to global blues. They feel like separate apps.
- Dark mode is currently just the default palette. There is no parallel light-mode token set, and the existing dark look leans toward hard neon/cyber accents instead of midnight glass.

## Recent Drift

- `Refine dashboard button styling` introduced glass button values that only covered controls.
- `Soften toolbar and range controls` reduced contrast in the top bar but did not update the shared surface system, creating ghosted toolbar text and weak hierarchy.
- Panel icon fixes improved rendering but did not address the underlying material mismatch.

## Token Plan

Create a small material system and route shared UI through it:

- `--app-background`
- `--surface-glass`
- `--surface-elevated-glass`
- `--border-subtle`
- `--border-active`
- `--shadow-soft`
- `--shadow-elevated`
- `--text-primary`
- `--text-secondary`
- `--icon-primary`
- `--control-background`
- `--control-hover`
- `--control-active`
- `--panel-header`
- `--widget-surface`
- `--modal-surface`
- `--toolbar-surface`

Keep the current dashboard shape and configurable panel colors, but make theme colors act as accents layered onto the same base material instead of becoming entirely separate material systems.

## Application Plan

1. Define dark-mode and light-mode token sets in `:root` and `[data-theme="dark"]`.
2. Map legacy tokens (`--bg`, `--surface`, `--line`, `--shadow`, `--text`) to the new material tokens so older sections inherit the system.
3. Replace repeated toolbar, button, card, form, table, dropdown, toast, panel, and menu surfaces with tokenized values.
4. Reduce theme glow globally and use accent color mainly for headers, controls, and active states.
5. Keep layout, sizing, and interaction behavior intact unless a style depends on broken one-off values.

## Screenshot Checklist

Capture after implementation:

- Dashboard light mode
- Dashboard dark mode
- Settings light mode
- Settings dark mode
- Modal/confirm equivalent light mode
- Modal/confirm equivalent dark mode
