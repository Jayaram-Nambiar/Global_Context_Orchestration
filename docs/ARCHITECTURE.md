# Architecture & Technical Design Specification

## 1. Executive Summary

Modern AI coding agents (such as Cursor, OpenCode, Claude Code, and Antigravity) are constrained by the economics and cognitive degradation of LLM context windows. As context sizes grow, agents suffer from:
- **Attention dilution ("Lost in the Middle")**: Vital project architectural constraints are ignored in favor of raw text dumped earlier in the context.
- **Runaway Token Costs**: Reading 1,000+ line files repeatedly consumes thousands of tokens per turn.
- **Apology & Hallucination Loops**: Code modifications made without deterministic local validation lead to broken syntax and repeated failed iterations.

**Agent Context Engine (`ctx`)** solves this by establishing a deterministic, local-only structural metadata index and pre-completion verification harness. It operates with **zero cloud dependencies** and **zero third-party package dependencies**.

---

## 2. Core Architectural Pillars

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           Agent Context Engine                          │
├───────────────────────────┬─────────────────────────────┬───────────────┤
│    1. Structural AST Map  │   2. Surgical Line Slicer   │  3. Pre-Check │
│   - Pure stdlib parsing   │   - 1-indexed line ranges   │  - py_compile │
│   - Minified JSON schema  │   - Bounded token reads     │  - PS1 parser │
│   - Cross-boundary hooks  │   - Zero context overflow   │  - node --chk │
└───────────────────────────┴─────────────────────────────┴───────────────┘
```

### Pillar 1: Zero External Dependencies
- Relies exclusively on Python's internal runtime (`ast`, `re`, `json`, `subprocess`, `argparse`) and standard OS utilities.
- Requires no `pip install`, no `node_modules`, no external C++ compilers, and no background daemon services.
- Runs instantaneously with execution times under 50ms for typical codebases.

### Pillar 2: Structural index
Rather than sending full source to an agent, `ctx map` records:
- File path and line count
- Classes, base classes, and methods
- Functions, arguments, and async signatures
- Exported constants
- Cross-boundary hooks (network APIs, shell execution)

`ctx map` prints a rough size comparison for that run (map bytes versus source bytes). That figure is not a benchmark.

---

## 3. Structural Parsing Implementation

### 3.1 Python: Full AST Traversal
Python files are parsed using Python's native `ast` module:
```python
tree = ast.parse(content)
```
- **Classes**: Extracted from `ast.ClassDef`. Bases are unparsed to capture inheritance hierarchies.
- **Functions**: Extracted from `ast.FunctionDef` and `ast.AsyncFunctionDef`. Parameter names and async status are preserved.
- **Constants**: Identifies top-level `ast.Assign` nodes with uppercase identifiers (e.g., `MAX_WORKERS`, `API_URL`).
- **Cross-Boundary Hooks**: Walks all `ast.Call` nodes. Analyzes function attributes for calls to:
  - Process/Shell: `subprocess.*`, `os.system`, `os.popen`, `shutil.*`
  - Network: `requests.*`, `urllib.*`, `httpx.*`, `aiohttp.*`, `socket.*`

### 3.2 JavaScript, TypeScript & Google Apps Script: Lexical Token Matching
To avoid requiring a heavy Node runtime or external Babel/TypeScript dependencies, JS/TS/AppsScript parsing uses high-performance regular expression grammars:
- **Classes**: `(?:export\s+)?class\s+([a-zA-Z0-9_$]+)(?:\s+extends\s+([a-zA-Z0-9_$]+))?`
- **Declared Functions**: `(?:export\s+)?(?:async\s+)?function\s+([a-zA-Z0-9_$]+)\s*\(([^)]*)\)`
- **Arrow Functions**: `(?:export\s+)?(?:const|let|var)\s+([a-zA-Z0-9_$]+)\s*=\s*(?:async\s*)?(?:\(([^)]*)\)|([a-zA-Z0-9_$]+))\s*=>`
- **Hooks**:
  - Web & API: `fetch(`, `axios.*`, `UrlFetchApp.fetch`, `XMLHttpRequest`
  - System: `child_process`, `execSync`, `spawnSync`, `Deno.run`

### 3.3 PowerShell: Cmdlets & Native AST
- Matches declared functions (`function Foo-Bar`, `filter Check-Status`).
- Captures native script parameters (`param(...)`).
- Hooks captured: `Invoke-RestMethod`, `Invoke-WebRequest`, `Start-Process`, `Invoke-Expression`.

### 3.4 VBScript / Windows Script Host (WSH)
- Captures `Class`, `Sub`, and `Function` signatures.
- Cross-boundary hooks: `WScript.Shell` invocations, `MSXML2.ServerXMLHTTP`, and `WinHttp.WinHttpRequest`.

### 3.5 Templates, diagrams, and industry formats
Regex extractors (same return schema as other parsers) cover Jinja2/Nunjucks/Liquid, Mermaid (including Markdown fences), SQL, Terraform HCL, GraphQL, Protobuf, Vue/Svelte `<script>` blocks, POSIX shell, Dockerfiles, and Makefiles. Google Apps Script (`.gs`) reuses the JS parser and records `SpreadsheetApp` / `google.script.run` hooks. Markdown files with no mermaid fence are not written into the map.

`language_for_path` maps extensionless names (`Dockerfile`, `Makefile`) in addition to `LANGUAGE_MAP` suffixes. `parse_file_content` is the single dispatch used by `ctx map`. Uncheckable types still print `[SKIP]` in `ctx check`.

---

## 4. Native Syntax Interception Engine (`ctx check`)

The `check` subsystem provides deterministic, non-destructive syntax verification without running untrusted user test suites or launching full applications.

### Detection Mechanism
1. **Git Integration**: Queries `git status --porcelain` to identify uncommitted modifications (`.py`, `.js`, `.ts`, `.ps1`, `.json`).
2. **Timestamp Fallback**: If Git is unavailable or no uncommitted changes exist, checks files modified within the last 30 minutes.
3. **Explicit Override (`--all`)**: Validates every supported source file in the project.

### Compiler Harnesses

```
┌──────────────────┬─────────────────────────────────────────────────────────────────┐
│ File Type        │ Verification Command                                            │
├──────────────────┼─────────────────────────────────────────────────────────────────┤
│ Python (.py)     │ python -m py_compile <file>                                     │
├──────────────────┼─────────────────────────────────────────────────────────────────┤
│ PowerShell (.ps1)│ [System.Management.Automation.Language.Parser]::ParseInput(...) │
├──────────────────┼─────────────────────────────────────────────────────────────────┤
│ JavaScript (.js) │ node --check <file> (if node in PATH)                           │
├──────────────────┼─────────────────────────────────────────────────────────────────┤
│ JSON (.json)     │ python -m json.tool <file>                                      │
├──────────────────┼─────────────────────────────────────────────────────────────────┤
│ Other / TS / etc │ SKIP — printed as `[SKIP]`, never a fake `[PASS]`               │
└──────────────────┴─────────────────────────────────────────────────────────────────┘
```

When a syntax error occurs:
- The exact file path, line number, and compiler message are printed.
- The process exits with exit code `1`, alerting the agent to correct the mistake immediately.

Each checker subprocess has a 20-second timeout. `ctx map` / `ctx check` refuse to scan the filesystem root or the user home directory, and mapping stops at 8,000 files (`meta.truncated`).

---

## 5. MCP transport

The server is stdio JSON-RPC only. Handshake rules, editor config shapes, and the failure history live in [AGENT_MEMORY.md](AGENT_MEMORY.md). Do not keep a second copy of that table here.

---

## 6. File Exclusions & Performance Optimization

To prevent scanning vendor dependencies and binary files, the engine enforces strict in-place pruning:
- **Ignored Directories**: `node_modules`, `.git`, `__pycache__`, `venv`, `.venv`, `dist`, `build`, `target`, `bin`, `obj`, `.next`, `.turbo`, `.gemini`, `.cursor`, `.vscode`.
- **Ignored Extensions**: Binaries, media, compressed archives, lockfiles (`.lock`), minified bundles (`*.min.js`, `*.bundle.js`, `*.map`).
- **Size Bounds**: Files exceeding 500 KB are bypassed to prevent memory spikes.
- **Workspace Bounds**: Filesystem root and `$HOME` are rejected. Walks stop after 8,000 indexed files.
