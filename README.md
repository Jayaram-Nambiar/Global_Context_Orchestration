# Agent Context Engine (`ctx`)

[![Tests](https://img.shields.io/badge/tests-36%20passed-brightgreen.svg)](#automated-testing)
[![MCP-Protocol](https://img.shields.io/badge/MCP-2024--11--05%20compliant-blueviolet.svg)](#model-context-protocol-mcp-integration)
[![Zero-Cloud](https://img.shields.io/badge/cloud-zero%20external%20services-blue.svg)](#design-principles)
[![Dependencies](https://img.shields.io/badge/dependencies-zero%20external%20pkgs-success.svg)](#design-principles)
[![Token-Reduction](https://img.shields.io/badge/tokens-90%25%2B%20reduction-orange.svg)](#token-economics)

**Agent Context Engine (`ctx`)** is a lightweight, local-first developer experience (DX), dependency topology, and LLM token optimization engine. It eliminates context bloat, reduces token consumption by **80–94%**, and intercepts code syntax regressions before LLMs return to user chat loops across **Antigravity**, **Claude Desktop / Claude Code**, **Cursor**, and **OpenCode**.

---

## The Problem: Context Bloat & Hallucination Loops

Traditional AI coding workflows suffer from two primary failure modes:
1. **Context Window Exhaustion**: Agents dump hundreds or thousands of lines of raw source code into context just to understand high-level symbol relationships, imports, or signatures. This triggers model context degradation, lost-in-the-middle phenomena, and runaway API token costs.
2. **Post-Edit Hallucination Loops**: After modifying code, agents report task completion without verifying syntax locally. If a subtle syntax error was introduced (e.g., mismatched brackets, improper indentation), the user must copy-paste the error back to the LLM, triggering an expensive apologetic loop.

---

## The Solution: Structural Metadata Indexing, Topologies & MCP

`ctx` introduces a lightweight, deterministic paradigm inspired by Abstract Syntax Tree (AST) analysis, architectural dependency graphs, and Model Context Protocol principles:

```
┌────────────────────────────────────────────────────────────────────────┐
│                          Target Workspace                              │
│ (.py, .js, .ts, .kt, .swift, .cpp, .c, .rb, .php, .scala, .ex, etc.)   │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                         [ ctx map / ctx graph ]
                                    │
                                    ▼
       ┌─────────────────────────────────────────────────────────┐
       │                   .agent-context.json                   │
       │   - Class Hierarchies & Method Signatures               │
       │   - Function Arguments & Return Signatures              │
       │   - Cross-Boundary Hooks (Network, Process, File I/O)   │
       │   - Dependency Graphs & Cycle Detection Alerts          │
       │   - Recommended Topological Edit Sequence               │
       │   (Minified, 80-94% Token Savings vs Raw Source)        │
       └────────────────────────────┬────────────────────────────┘
                                    │
         ┌──────────────────────────┼──────────────────────────┐
         ▼                          ▼                          ▼
 [ ctx query <sym> ]     [ ctx slice <file> L1 L2 ]     [ ctx graph ]
 (Symbol Location)       (Line-Bounded Read)            (Topology Plan)
         │                          │                          │
         └──────────────────────────┴──────────────────────────┘
                                    │ Agent Performs Edits
                                    ▼
                             [ ctx check ]
                   (Native Local Syntax Validation)
                                    │
                  ┌─────────────────┴─────────────────┐
                  ▼                                   ▼
            [PASS: Exit 0]                      [FAIL: Exit 1]
         Proceed to Completion              Intercept Error Locally
```

---

## Features

- **Zero Cloud & Zero Third-Party Dependencies**: Runs strictly on standard library Python and native host binaries. Zero vector databases, zero pip installs, zero cloud dependencies.
- **Model Context Protocol (MCP) Server (`ctx mcp`)**: Pure Python stdio JSON-RPC 2.0 server complying with MCP `2024-11-05` exposing tools: `ctx_get_map`, `ctx_query_symbol`, `ctx_slice`, `ctx_check`, `ctx_get_graph`.
- **Architectural Dependency Graphs & Cycle Detection (`ctx graph`)**:
  - Resolves internal relative imports across all supported languages.
  - Detects circular dependency cycles using 3-color Depth-First Search.
  - Highlights architectural root entry points (in-degree = 0).
  - Performs Kahn's algorithm topological sorting to output the optimal file edit order (dependency prerequisites first).
- **Polyglot Structural Pattern Extraction**:
  - **Python (`.py`)**: Full AST traversal for classes, methods, inheritance, function arguments, async signatures, module constants, and cross-boundary network/process hooks (`subprocess`, `requests`, `os.system`, `httpx`).
  - **JavaScript / TypeScript / Google Apps Script (`.js`, `.ts`, `.gs`, `.jsx`, `.tsx`)**: Declarations, arrow functions, classes, and hooks (`fetch`, `axios`, `UrlFetchApp`, `child_process`).
  - **PowerShell (`.ps1`, `.psm1`)**: Cmdlet functions, filters, and invocations (`Invoke-RestMethod`, `Invoke-WebRequest`, `Start-Process`).
  - **VBScript / WScript (`.vbs`)**: Subroutines, functions, classes, and COM automation (`WScript.Shell`, `MSXML2.ServerXMLHTTP`).
  - **Kotlin (`.kt`, `.kts`)**: Classes, objects, interfaces, fun declarations, and network hooks (`ktor`, `okhttp3`).
  - **Swift (`.swift`)**: Classes, structs, protocols, functions, and hooks (`URLSession`, `Process`).
  - **C / C++ (`.c`, `.h`, `.cpp`, `.hpp`, `.cc`, `.cxx`)**: Classes, structs, functions, and hooks (`socket`, `curl`, `popen`, `fork`).
  - **Ruby (`.rb`, `.rake`)**: Classes, modules, defs, and hooks (`Net::HTTP`, `Open3`, `system`).
  - **PHP (`.php`)**: Classes, interfaces, traits, functions, and hooks (`curl_init`, `exec`, `shell_exec`).
  - **Scala (`.scala`, `.sc`)**: Classes, traits, objects, defs, and hooks (`Http`, `Process`).
  - **Elixir (`.ex`, `.exs`)**: Modules, defs, defps, and hooks (`HTTPoison`, `System`, `Port`).
  - **Go, Rust, C#, Java**: Structs, interfaces, and function signatures.
- **Pre-Commit Interception**: Installs git hooks into `.git/hooks/pre-commit` via `scripts/install-hooks.ps1` or `scripts/install-hooks.sh` to block commits containing syntax errors in <25ms.

---

## Quickstart

### 1. Global Installation & Cross-Editor Synchronization

From this repository, run the deployment script:

```powershell
# Windows
powershell -ExecutionPolicy Bypass -File scripts/deploy.ps1
```

Or on Linux / macOS:
```bash
bash scripts/deploy.sh
```

This installs:
- Master engine into `~/.agent-context-engine/engine.py` and `mcp_server.py`.
- Global launchers (`ctx.cmd`, `ctx.ps1`, `ctx`) in PATH and Scoop shims.
- Configures the MCP server across **Antigravity**, **Claude Desktop**, **Cursor**, and **OpenCode**.
- Injects surgical token optimization rules into global profiles.

### 2. Basic CLI Usage

```bash
# 1. Map current directory into minified .agent-context.json
ctx map

# 2. Inspect dependency topology, cycles, and edit sequence
ctx graph

# 3. Query a specific function or cross-boundary hook
ctx query computeTotal

# 4. Read only the necessary line range (e.g. lines 10 to 45)
ctx slice src/service.py 10 45

# 5. Validate syntax of all changed files before reporting completion
ctx check

# 6. Auto-synchronize MCP server across all installed AI editors
ctx mcp --install
```

---

## CLI Reference

| Command | Arguments | Purpose |
| :--- | :--- | :--- |
| `ctx map` | `[dir]` | Scans directory and produces minified `.agent-context.json`. Displays token savings metrics. |
| `ctx graph` | `[dir]` | Visualizes entry points, circular cycles, and Kahn's topological edit ordering. |
| `ctx check` | `[dir] [--all]` | Executes native local compilation on uncommitted git changes or recently modified files. |
| `ctx slice` | `<file> <start> <end>` | Emits line-numbered slices of target files, enforcing the "<150 lines read" rule. |
| `ctx query` | `<symbol> [dir]` | Looks up matching classes, methods, functions, or hooks in `.agent-context.json`. |
| `ctx mcp` | `[--install]` | Starts stdio JSON-RPC 2.0 MCP server, or auto-configures editor profiles with `--install`. |

---

## Model Context Protocol (MCP) Integration

The Agent Context Engine is a first-class MCP server exposing the following 5 tools:
- `ctx_get_map(workspace_path?: string)`: Retrieves or generates minified metadata map.
- `ctx_query_symbol(symbol: string, workspace_path?: string)`: Searches symbols without reading raw files.
- `ctx_slice(file_path: string, start_line: number, end_line: number)`: Returns surgical line ranges.
- `ctx_check(workspace_path?: string, check_all?: boolean)`: Executes local compilers and returns diagnostics.
- `ctx_get_graph(workspace_path?: string)`: Returns dependency topologies and topological edit sequence.

---

## Automated Testing

Run the included comprehensive test harness (36 automated tests covering engine, parsers, dependency graphs, hooks, and MCP server):

```bash
# Via Python
python -m unittest discover -s tests -p "test_*.py" -v

# Via PowerShell
powershell -ExecutionPolicy Bypass -File scripts/test.ps1
```

---

## Repository Structure

```
Global_Context_Orchestration/
├── bin/
│   ├── ctx.cmd               # Windows Command Prompt launcher
│   ├── ctx.ps1               # PowerShell launcher
│   └── ctx                   # POSIX Bash launcher
├── src/
│   ├── engine.py             # Core engine, parsers, dependency graphs & CLI
│   └── mcp_server.py         # MCP stdio JSON-RPC 2.0 server & editor sync
├── scripts/
│   ├── deploy.ps1            # Global Windows deployment automation
│   ├── deploy.sh             # Global Unix/macOS/Linux deployment script
│   ├── install-hooks.ps1     # Pre-commit git hook installer (Windows)
│   ├── install-hooks.sh      # Pre-commit git hook installer (Bash)
│   └── test.ps1              # Automated test runner
├── tests/
│   ├── test_engine.py        # Core engine, polyglot parsers, dependency graph tests
│   ├── test_hooks.py         # Git pre-commit hook interception tests
│   └── test_mcp_server.py    # MCP protocol handshake, tools, editor sync tests
├── docs/
│   ├── ARCHITECTURE.md       # Technical design & token economics
│   ├── AGENT_TRAINING.md     # AI agent behavioral instruction manual
│   ├── EDITOR_INTEGRATION.md # Cross-editor MCP & prompt injection guide
│   └── DEVELOPMENT_ROADMAP.md# Evolutionary roadmap & milestone log
├── .agent-context.json       # Minified project structural metadata
└── README.md                 # Master project documentation
```

---

## License

Internal Developer Utility — Designed for optimal local LLM performance and token preservation.

