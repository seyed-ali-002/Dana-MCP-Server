# Dana MCP Server

> Turn AI chatbots into powerful, free agents that can work with your computer, code, files, projects, and development environment through MCP.

🇮🇷 **Persian documentation:** [README_FA.md](README_FA.md)  
🇬🇧 **English:** This document

---

## 🙏 Special Thanks

Special thanks to **Mohsen Samadinejad**. The original execution idea and early architectural direction that inspired this project came from his work.

His **PHP MCP Server** was an important behavioral reference during Dana's Python implementation and evolution.

GitHub: [Mohsen Samadinejad](https://github.com/samadinejad)

---

## What is Dana?

Dana is a cross-platform Python MCP server that gives compatible AI chatbots real capabilities on the machine where Dana runs.

Instead of being limited to conversation, a chatbot can become an agent that can:

- read, create, edit, and organize files
- inspect and modify codebases
- run tests, builds, linters, and diagnostics
- manage Git, processes, packages, Docker, databases, and APIs
- automate browsers
- analyze projects and architecture
- work with persistent project memory and optimized context
- extract and analyze PDF content
- generate documents, reports, README files, Word files, and PDFs
- plan, review, debug, and validate engineering work

Dana is designed to work with MCP-compatible AI clients such as ChatGPT, Claude, Grok, and other compatible clients. The core project is free and self-hosted: Dana runs on your own computer or server and performs work there.

## Why Dana?

Dana is built around three goals:

1. **Real agent capabilities** — the chatbot can act through tools instead of only generating text.
2. **Self-hosting and control** — tools run on infrastructure you control.
3. **Efficiency** — Progressive Tool Discovery, caching, compact results, batching, and context intelligence reduce unnecessary latency and token usage.

---

# Installation and Connection

## Step 1 — Install and sign in to Tailscale

For the easiest Local Mode setup, install [Tailscale](https://tailscale.com/) first and sign in on the machine that will run Dana. Dana uses Tailscale Funnel to expose a secure HTTPS MCP endpoint.

### Linux

Install Tailscale using the official instructions:

[Tailscale for Linux](https://tailscale.com/download/linux)

Then start it and sign in:

```bash
sudo systemctl enable --now tailscaled
sudo tailscale up
tailscale status
```

### Windows

Install Tailscale from:

[Tailscale for Windows](https://tailscale.com/download/windows)

Open the application, choose **Log in**, complete browser authentication, and confirm that the device is connected.

### macOS

Install Tailscale from:

[Tailscale for macOS](https://tailscale.com/download/mac)

Sign in and confirm that the device is connected.

> The Tailscale account must be allowed to use Funnel for Dana Local Mode.

---

## Step 2 — Clone Dana

```bash
git clone https://github.com/seyed-ali-002/Dana-MCP-Server.git
cd Dana-MCP-Server
```

## Step 3 — Run the Installer

### Linux / macOS

```bash
python3 install.py
```

### Windows

```bat
python install.py
```

The interactive installer:

- creates or updates an isolated `.venv`
- installs required dependencies
- lets you choose Local or Server Mode
- configures worker count
- creates persistent authentication configuration
- configures networking for the selected deployment mode
- checks required services before startup

For first-time setup, the Installer is the recommended path.

---

## Step 4 — Choose a Deployment Mode

### Local Mode — personal computer

Local Mode is the simplest setup for a development machine or personal computer:

```text
AI Client
   │
   │ MCP over HTTPS
   ▼
Tailscale Funnel
   │
   ▼
Dana
   │
   ├── Files
   ├── Code
   ├── Shell
   ├── Git
   ├── Browser
   └── Intelligence
```

Dana displays a tokenized connection URL similar to:

```text
https://<machine>.<tailnet>.ts.net/<TOKEN>/mcp
```

Use the URL shown by Dana as the MCP connection URL.

### Server Mode — VPS or dedicated server

Server Mode is designed for Linux servers and existing web infrastructure. Dana runs on an internal localhost port and integrates with an existing reverse proxy.

Supported reverse proxies:

- Nginx
- Caddy
- Apache

Architecture:

```text
Internet
   │
   ▼
https://mcp.example.com
   │
   ▼
Reverse Proxy :443
   │
   └── /mcp → 127.0.0.1:<DANA_PORT>
                    │
                    ▼
                  Dana
```

The Installer can detect existing proxies, back up configuration, validate changes, and avoid unnecessary service installation. If no supported proxy is available, it asks before installing Caddy.

Typical endpoint:

```text
https://mcp.example.com/mcp
```

Dana also exposes OAuth authorization metadata and a PKCE-based authorization-code flow for compatible reconnect flows, independently from My_PC or another local connector.

---

## Step 5 — Start and Stop Dana

After installation, use the project runners provided by your installation.

Typical local commands:

```bash
./run
./stop
```

On Windows, use the corresponding `.bat` runner.

In Server Mode, Dana can run as a systemd service:

```bash
sudo systemctl start dana
sudo systemctl stop dana
sudo systemctl restart dana
sudo systemctl status dana --no-pager
sudo journalctl -u dana -f
```

Worker count is configured during installation and stored as:

```env
DANA_WORKERS=5
```

---

## Step 6 — Connect Your AI Client

Add Dana as an MCP or Custom Connector in your AI client and use the URL generated by Dana.

### ChatGPT

Open the Connectors or MCP connection area and add Dana's endpoint. Server Mode supports OAuth metadata and PKCE reconnect flows for compatible clients.

### Claude

Add a Custom MCP connection and use Dana's endpoint.

### Grok

Create a Custom Connector and use Dana's endpoint.

> Client menu names can change over time. Use the current MCP/Connector configuration area of your client.

---

# Security and Access Control

Dana executes tools on the machine where it is running. Operating-system permissions therefore matter.

Filesystem access can be restricted in `config/access_policy.json`:

```json
{
  "allowed_paths": ["/home/user/projects", "/mnt/workspace"],
  "deny_paths": []
}
```

Dana also provides MCP tools for inspecting and updating the access policy.

Keep connection URLs and tokens private. Rotate a token when necessary:

```bash
python scripts/regenerate_token.py
```

---

# Performance and Context Optimization

Dana is intentionally designed to avoid turning a large tool registry into unnecessary prompt overhead.

## Progressive Tool Discovery

By default, the MCP client sees a small set of entry points:

- `dana_search_tools`
- `dana_call_tool`
- `dana_batch_call`
- `dana_capabilities`
- `dana_optimization_stats`

The complete registry remains available internally and is discovered on demand. This keeps initial MCP context small even when Dana contains many capabilities.

## Runtime Optimization

Dana includes:

- short-lived caching for safe read operations
- parallel execution for independent batch calls
- compact result generation
- context deduplication and compression
- repository and symbol indexing
- delta context and file summaries
- persistent codebase memory
- bounded analysis to avoid oversized responses
- tool cost and optimization statistics

Legacy clients that require the full tool list can disable progressive discovery:

```env
DANA_PROGRESSIVE_TOOLS=0
```

To disable safe-read caching:

```env
DANA_TOOL_CACHE=0
```

---

# All Dana Capabilities

Dana's complete registry is organized below. In the default optimized MCP mode, these capabilities are discovered and invoked through `dana_search_tools` and `dana_call_tool` rather than all being sent to the client at connection time.

## Core MCP and Optimization

- `dana_search_tools`
- `dana_call_tool`
- `dana_batch_call`
- `dana_capabilities`
- `dana_optimization_stats`
- `dana_optimization_controller`
- `dana_tool_cost`
- `dana_tool_costs`
- `dana_fast_path`
- `dana_prompt_cache_key`
- `dana_semantic_cache`
- `dana_result_optimize`
- `dana_result_page`
- `dana_result_delta`
- `dana_context_build`
- `dana_context_compact`

## Filesystem and Workspace

- `list_directory`
- `read_file`
- `write_file`
- `edit_file`
- `delete_path`
- `workspace_snapshot`
- `change_summary`
- `rollback_changes`
- `get_allowed_paths`
- `set_allowed_paths_tool`
- `add_allowed_path_tool`
- `remove_allowed_path_tool`
- `validate_path_access`

## Shell, Processes, System, and Network

- `run_command`
- `run_process`
- `debug_command`
- `debug_trace`
- `process_list`
- `process_stop`
- `system_info`
- `system_details`
- `system_metrics`
- `environment`
- `network_check`
- `port_check`
- `schedule_command`
- `cancel_scheduled_task`

## Code Search and Project Analysis

- `search_code`
- `find_symbol`
- `find_references`
- `find_entry_points`
- `analyze_project`
- `architecture_summary`
- `generate_project_diagram`
- `project_health_check`
- `code_complexity`
- `find_duplicate_code`
- `static_analysis`
- `python_diagnostics`
- `change_summary`
- `analyze_stacktrace`
- `analyze_implementation_need`
- `review_implementation`
- `simplify_code`

## Build, Test, Quality, and Debugging

- `run_tests`
- `build_project`
- `discover_tests`
- `coverage`
- `benchmark`
- `check_code_quality`
- `check_prettier`
- `lint_or_format`
- `format_code`
- `format_project`
- `format_python`
- `format_python_check`
- `lint_python`
- `fix_python_code`
- `sort_python_imports`
- `type_check_python`
- `lint_javascript`
- `dana_debug_issue`
- `dana_test_intelligence`
- `dana_predict_regression`
- `dana_rank_root_causes`
- `dana_self_healing_plan`

## Git, Packages, Containers, and Dependencies

- `git`
- `package_manager`
- `dependency_outdated`
- `dependency_security_scan`
- `secret_scan`
- `docker`
- `docker_status`
- `docker_build`
- `container_logs`
- `toolchain_status`

## HTTP, APIs, Browser, and Web

- `http_request`
- `api_request`
- `web_fetch`
- `browser_check`
- `browser_open`
- `browser_automation`
- `dana_api_intelligence`

Optional browser support can be installed with:

```bash
pip install -e ".[browser]"
playwright install chromium
```

## Database Intelligence

- `sqlite_query`
- `database_schema`
- `database_health_check`
- `dana_database_intelligence`

## PDF, Documents, Reports, and Documentation

- `extract_pdf_text`
- `extract_pdfs_text`
- `create_document`
- `create_docx`
- `create_pdf`
- `generate_readme`
- `generate_changelog`
- `generate_report`

## Codebase Memory and Context

- `index_codebase`
- `update_codebase_memory`
- `clear_codebase_memory`
- `codebase_memory_status`
- `search_codebase_memory`
- `get_context`
- `get_context_delta`
- `get_file_delta`
- `get_file_summary`
- `get_project_map`
- `get_symbol_context`
- `get_dependency_context`
- `estimate_tokens_for_context`
- `context_compress`
- `memory_write`
- `memory_retrieve`
- `memory_stats`
- `memory_digest`
- `memory_export`
- `memory_feedback`
- `memory_link`
- `memory_links`
- `memory_maintain`
- `memory_purge`

## Library and Documentation Intelligence

- `resolve_library`
- `get_library_docs`
- `search_library_docs`

## Advanced Engineering Intelligence

- `dana_classify_request`
- `dana_route_request`
- `dana_plan`
- `dana_plan_execute`
- `dana_create_implementation_plan`
- `dana_engineering_decision`
- `dana_engineering_policy`
- `dana_architecture_review`
- `dana_dependency_graph`
- `dana_analyze_change_impact`
- `dana_project_index`
- `dana_map_repository`
- `dana_symbol_search`
- `dana_trace_symbol`
- `dana_security_review`
- `dana_execution_sandbox_plan`
- `dana_cross_repository_intelligence`
- `dana_record_architecture_decision`
- `dana_visual_architecture_graph`

## Tasks, Planning, and Work Sessions

- `create_task_plan`
- `task_status`
- `start_work_session`
- `end_work_session`
- `dana_session_start`
- `dana_session_get`

## Token and Operation Analytics

- `record_token_usage`
- `get_token_analytics`
- `reset_token_analytics`
- `get_operation_analytics`

## UI and Visual Design Intelligence

- `dana_create_ui_design`
- `dana_add_ui_screen`
- `dana_add_ui_component`
- `dana_connect_ui_screens`
- `dana_generate_ui_prompt`
- `dana_export_ui_html`

---

# Example Requests

After connecting Dana, you can ask your AI client things like:

- “Analyze this repository and explain the architecture.”
- “Find the cause of this stack trace and propose the smallest safe fix.”
- “Read all PDFs in this folder, extract their content, and build a study guide.”
- “Review my changes, predict regression risks, run targeted tests, and report the result.”
- “Create an implementation plan before changing the code.”
- “Search the project for duplicate code and simplify it safely.”
- “Create a Persian Word or PDF report from these project files.”
- “Inspect the database schema and identify likely performance risks.”

---

## Dana Doctor

Dana includes a cross-platform diagnostic command for cases where one machine works correctly and another does not.

    python -m dana doctor

or:

    dana doctor

Doctor checks the Dana version and Git commit, Python compatibility, environment configuration, required project files, dependencies, live health and OAuth routes, Tailscale state, Funnel state, deployment mode, and the generated connector URL. Tokens are masked by default.

    python -m dana doctor --show-url

Use `--show-url` only on a trusted terminal when you need the complete Local Mode URL. Machine-readable output is also available:

    python -m dana doctor --json

---

# Testing

Run the test suite:

```bash
pytest -q
```

For a basic syntax check:

```bash
python3 -m py_compile dana/http.py
```

---

# Architecture

Dana keeps the MCP layer lightweight while heavier analysis is performed on demand:

```text
AI Client
   │
   ▼
Dana MCP Gateway
   │
   ├── Progressive Tool Discovery
   ├── Authentication / OAuth
   ├── Optimization Layer
   └── Tool Router
          │
          ├── System & Files
          ├── Engineering Intelligence
          ├── Codebase Memory
          ├── Browser & API
          ├── Documents & PDF
          └── Database & Containers
```

This design helps Dana grow without sending its entire capability set into every initial MCP request.

---

# Contributing

Dana is an open project and contributions are welcome.

You can help by:

1. reporting bugs
2. proposing new tools or integrations
3. improving installation and deployment support
4. adding tests
5. improving documentation
6. submitting pull requests
7. reviewing architecture and performance

Before opening a pull request, please test your changes and keep changes focused where possible.

When reporting a bug, include relevant information such as:

- operating system
- Python version
- Dana version or commit
- deployment mode
- relevant logs
- reproduction steps

If Dana is useful to you, consider starring the repository and sharing ideas for its next capabilities.

## License

See [LICENSE](LICENSE).
