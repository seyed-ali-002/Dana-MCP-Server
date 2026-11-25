# frontend-design

Use when designing or polishing Dana Control Center UI, React/CSS layouts, or any web surface.

## Principles (Dana dark Control Center)
- Hierarchy: eyebrow → title → one lead → actions → content grid.
- Avoid sparse empty cards; each card needs title, 2–4 line body, one primary action.
- Use CSS variables (`--surface`, `--border`, `--muted`, `--success`).
- Skills grid: minmax(260px, 1fr); clamp descriptions to 3 lines; toggles top-right.
- Filter + category chips above the grid; pack actions as a compact toolbar.
- Primary action is one clear button; secondary actions stay quiet.
- Empty/error states include a next step.
