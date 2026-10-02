# Capabilities and Tool Registry

## 1. مدل قابلیت‌ها

Dana ابزارها را به جای قرار دادن یک لیست بسیار بزرگ در ابتدای context، در registry نگه می‌دارد.

client ابتدا discovery می‌کند:

`search → inspect/help → call`

این الگو باعث کاهش prompt overhead می‌شود.

## 2. Core MCP and Optimization

نمونه ابزارها:

- `dana_search_tools`
- `dana_list_tools`
- `dana_help_tool`
- `dana_call_tool`
- `dana_batch_call`
- `dana_capabilities`
- `dana_optimization_stats`
- `dana_optimization_controller`
- `dana_tool_cost`
- `dana_fast_path`
- `dana_semantic_cache`
- `dana_result_optimize`
- `dana_result_page`
- `dana_result_delta`
- `dana_context_build`
- `dana_context_compact`

## 3. Filesystem and Workspace

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

## 4. System, Processes and Network

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

## 5. Code and Repository Intelligence

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
- `analyze_stacktrace`
- `analyze_implementation_need`
- `review_implementation`
- `simplify_code`

## 6. Testing and Quality

- `run_tests`
- `build_project`
- `discover_tests`
- `coverage`
- `benchmark`
- `check_code_quality`
- `lint_or_format`
- `format_code`
- `format_project`
- `format_python`
- `format_python_check`
- `lint_python`
- `fix_python_code`
- `sort_python_imports`
- `type_check_python`
- `dana_debug_issue`
- `dana_test_intelligence`
- `dana_predict_regression`
- `dana_rank_root_causes`
- `dana_self_healing_plan`

## 7. Git, dependencies and containers

- Git operations
- package manager operations
- outdated dependency inspection
- security scan
- secret scan
- Docker status/build/logs
- toolchain status

## 8. HTTP, APIs and Browser

- `http_request`
- `api_request`
- `web_fetch`
- `browser_check`
- `browser_open`
- `browser_automation`
- `dana_api_intelligence`

Browser dependencies are optional و با extra مخصوص browser نصب می‌شوند.

## 9. Database

- `sqlite_query`
- `database_schema`
- `database_health_check`
- `dana_database_intelligence`

## 10. Documents and PDF

- `extract_pdf_text`
- `extract_pdfs_text`
- `create_document`
- `create_docx`
- `create_pdf`
- `generate_readme`
- `generate_changelog`
- `generate_report`

## 11. Memory and Context

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

## 12. Engineering Intelligence

- request classification
- request routing
- planning
- plan execution
- implementation planning
- engineering decisions
- engineering policies
- architecture review
- dependency graph
- change impact analysis
- repository mapping
- symbol tracing
- security review
- sandbox planning
- cross-repository intelligence
- architecture decision records
- visual architecture graph

## 13. Runtime and Sessions

- task planning
- task status
- work sessions
- session start/get/end
- parallel calls
- plan execution
- workspace context
- worker status
- runtime health

## 14. Analytics

- token usage
- operation analytics
- token reset
- optimization statistics

## 15. UI intelligence

Dana دارای ابزارهای طراحی و تولید UI نیز هست، از جمله:

- UI design creation
- screen/component generation
- screen connections
- UI prompt generation
- HTML export

## 16. Access policy

دو تنظیم اصلی:

`DANA_ALLOWED_PATHS`

`DANA_DENIED_PATHS`

قواعد:

1. allowed list خالی → به طور پیش‌فرض همه مسیرها قابل دسترسی‌اند، مگر deny شده باشند.
2. deny همیشه precedence دارد.
3. path policy باید قبل از عملیات filesystem اعمال شود.
4. policy نباید با token authentication اشتباه گرفته شود؛ این دو لایه مستقل هستند.

## 17. Adding a new tool

برای اضافه کردن tool:

1. module مناسب در `dana/tools/` انتخاب شود.
2. schema و description روشن باشد.
3. tool registry آن را discover کند.
4. category مناسب داشته باشد.
5. permission/security implications بررسی شود.
6. unit/integration test اضافه شود.
7. progressive discovery behavior بررسی شود.
8. README یا این مستندات در صورت تغییر capability به‌روزرسانی شود.

## 18. Tool compatibility

`dana/tools/tool_catalog.py` category و canonical naming را مدیریت می‌کند.

Aliasها برای حفظ compatibility با clientها و نام‌های قدیمی استفاده می‌شوند.

تغییر نام یک tool بدون alias یا migration می‌تواند breaking change باشد.
