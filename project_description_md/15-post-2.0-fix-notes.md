# Post 2.0 UI merge — fix notes

## Functional
- `get_connection_mode()` now reads via `_read_env()` (was calling `_read_env_file()` with no path → TypeError / silent fail).
- `set_connection_mode()` persists `DANA_CONNECTION_MODE` to the env file so the mode survives restarts.
- SuperMCP start/stop failures no longer abort the whole mode switch.
- `SetupStatus.connection_mode` is populated on every status poll.

## Visual
- Version badge falls back to `2.0.1` (was `0.1.1` when `__APP_VERSION__` is missing).
- Added missing view containers: `config-view`, `repair-view`, `help-view`, `skills-view`, `usage-view`, `logs-view`.
- Added `fl-activity-box`, `fl-groups-box`, help TOC, usage charts, token pie placeholders.
- Content padding/gap tightened; control cards and card-actions spacing fixed.
- Form controls (select/input) use custom appearance — no browser defaults.
- Responsive sidebar collapses under 980px.

## Apply on existing checkouts
```bash
python3 packaging/apply_v201_fixes.py
```
