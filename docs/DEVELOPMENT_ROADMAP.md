# Development Roadmap & Future Architecture

This document provides future maintainers, systems architects, and AI contributors with the evolutionary roadmap, extension points, and architectural guidelines for **Agent Context Engine (`ctx`)**.

---

## 1. Vision & Core Invariants

Any future extension must uphold these three non-negotiable invariants:
1. **Zero Cloud Requirement**: The engine must remain 100% functional offline with zero calls to remote vector databases, embeddings APIs, or external telemetry services.
2. **Sub-100ms Latency Target**: Indexing medium repositories (<1,000 files) must execute within sub-100ms so terminal-driven AI agent loops experience zero perceptible lag.
3. **Pure Execution**: Avoid heavy runtimes or compilation toolchains that require native C++ build tools on developer machines.

---

## 2. Feature Roadmap & Milestone Status

### [COMPLETED] Phase 1: Model Context Protocol (MCP) Server
*Status: Production Ready | Implemented in `src/mcp_server.py` & verified in `tests/test_mcp_server.py`*

- **MCP Tools Exposed**:
  - `ctx_get_map(workspace_path?: string)`: Returns the minified context map JSON.
  - `ctx_query_symbol(symbol: string, workspace_path?: string)`: Returns symbol locations and method signatures.
  - `ctx_slice(file_path: string, start_line: number, end_line: number)`: Returns line-numbered slices.
  - `ctx_check(workspace_path?: string, check_all?: boolean)`: Runs native compilers and returns pass/fail diagnostics.
  - `ctx_get_graph(workspace_path?: string)`: Returns dependency topologies, circular cycle alerts, and topological sort orders.
- **Transport**: Standard I/O (stdio) JSON-RPC 2.0 compliant with MCP `2025-06-18` (also `2025-03-26` / `2024-11-05`). stdout is JSON-RPC only; diagnostics go to stderr.
- **CLI Subcommand**: `ctx mcp` (starts stdio server) and `ctx mcp --install` (auto-registers with AI editors).

### [COMPLETED] Phase 2: Expanded Polyglot Structural Parsing
*Status: Production Ready | Implemented in `src/engine.py` & verified in `tests/test_engine.py`*

- **Zero-Prerequisite Structural Extractors**:
  - Kotlin (`.kt`, `.kts`) - classes, objects, interfaces, funs, ktor/okhttp hooks.
  - Swift (`.swift`) - classes, structs, protocols, funcs, URLSession/Process hooks.
  - C / C++ (`.c`, `.h`, `.cpp`, `.hpp`, `.cc`, `.cxx`) - classes, structs, functions, socket/curl/popen/fork hooks.
  - Ruby (`.rb`, `.rake`) - classes, modules, defs, Net::HTTP/system/Open3 hooks.
  - PHP (`.php`) - classes, interfaces, traits, functions, curl/exec/shell_exec hooks.
  - Scala (`.scala`, `.sc`) - classes, traits, objects, defs, Http/Process hooks.
  - Elixir (`.ex`, `.exs`) - defmodule, def, defp, HTTPoison/System/Port hooks.
- **Compiler Checkers**: Integrated into `ctx check` with graceful non-blocking fallback if compilers are not on PATH.

### [COMPLETED] Phase 3: Semantic Call Graphs & Dependency Topologies
*Status: Production Ready | Implemented in `src/engine.py` & verified in `tests/test_engine.py`*

- **Features**:
  - Multi-language import resolution mapping relative/internal dependencies across project files.
  - 3-color DFS circular dependency detection identifying cycles before code mutations.
  - In-degree analysis identifying architecture root callers/entry points (e.g. `main.py`, `app.js`, `deploy.ps1`).
  - Kahn's algorithm topological sorting outputting optimal edit sequences (dependency leaves first).
- **CLI Subcommand**: `ctx graph [dir]` and integrated `"graph"` metadata in `.agent-context.json`.

### [COMPLETED] Phase 4: Git Pre-Commit & Pre-Push Hooks
*Status: Production Ready | Implemented in `scripts/install-hooks.ps1` and `scripts/install-hooks.sh`*

- **Hook**: `.git/hooks/pre-commit` running local `ctx check`.
- **Latency**: Intercepts invalid syntax locally in <25ms before commits are staged. Can be bypassed via `git commit --no-verify` or `SKIP_CTX=1`.

### [COMPLETED] Phase 5: Cross-Editor MCP Configuration & Global Synchronization
*Status: Production Ready | Implemented in `src/mcp_server.py`, `scripts/deploy.ps1`, `scripts/deploy.sh`*

- **Supported Tools**:
  - Antigravity IDE: `~/.gemini/config/mcp_config.json`
  - Claude Desktop: `%APPDATA%\Claude\claude_desktop_config.json` (Windows/macOS/Linux)
  - Cursor: `~/.cursor/mcp.json`
  - OpenCode: `~/.config/opencode/opencode.jsonc` (using official `opencode.ai` schema)
- **Synchronization Command**: `ctx mcp --install` or `scripts/deploy.ps1` / `scripts/deploy.sh`.

### [COMPLETED] Phase 6: Stdio Integrity & Safe Workspace Bounds (v1.2.0)
*Status: Production Ready | `src/mcp_server.py`, `src/engine.py`, `tests/`*

- JSON-RPC stdout isolation; MCP `initialize` version negotiation for `2025-06-18`.
- `ctx slice` enforces the 150-line product cap; `ctx check` never reports fake `[PASS]`.
- `ctx map` / `ctx check` refuse `$HOME` and filesystem roots; mapping truncates at 8,000 files.
- `ctx mcp --install` will not clobber an existing invalid editor config.
- MCP tool results strip ANSI; numeric tool arguments accept JSON strings.

---

## 3. Contribution & Architecture Guidelines

When adding structural pattern detection for a new language:

1. **Add Extension to `LANGUAGE_MAP` in `src/engine.py`**:
   ```python
   LANGUAGE_MAP[".kt"] = "kotlin"
   ```
2. **Implement Parser Function**:
   - Must return a dictionary matching schema:
     ```python
     {
         "classes": [{"name": str, "line": int, "methods": list}],
         "functions": [{"name": str, "line": int, "args": list}],
         "hooks": list[str]
     }
     ```
3. **Register Compiler in `cmd_check`**:
   - Use host's native command if present (e.g. `kotlinc`, `javac`, `rustc`).
   - Gracefully fall back if binary is not installed on the system.
4. **Add Unit Tests in `tests/test_engine.py`**:
   - Add a test method verifying symbol and hook extraction.
   - Run `python -m unittest tests/test_engine.py` to confirm 100% pass rate.
