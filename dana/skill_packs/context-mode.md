---
id: context-mode
name: Context mode
description: Keep large tool dumps out of the chat; summarize and reference paths.
tags: context, tokens
---

# Context mode

- Prefer writing large outputs to files and returning paths + short digests.
- When a tool returns >2KB of text, summarize structure and quote only critical lines.
- Re-read files on demand instead of pasting full contents repeatedly.
- Keep a running "state" of open files and pending tasks in a few lines.
