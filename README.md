# Agent Context Engine (`ctx`)

Local command-line tool and [Model Context Protocol](https://modelcontextprotocol.io/) server. It builds a small structural index of a repository so an coding agent can find symbols, read a line range, and check syntax without loading whole files.

The project is [MIT licensed](LICENSE). You may use, modify, and redistribute it with no further restrictions beyond keeping the copyright notice and this license text with copies or substantial portions of the software.

Current release: **1.3.0**. Python **3.8+**. Standard library only. No pip packages and no network service.

## What you get

| Command | What it does |
| :--- | :--- |
| `ctx map [dir]` | Writes `.agent-context.json` for that directory. Refuses `$HOME` and a filesystem root. Stops at 8,000 files. |
| `ctx query <symbol> [dir]` | Finds classes, methods, functions, and hooks in the index. |
| `ctx slice <file> <start> <end>` | Prints a line-numbered range, clamped to 150 lines. |
| `ctx graph [dir]` | Lists entry points, import cycles, and a topological edit order. |
| `ctx check [dir] [--all]` | Runs a local syntax check. Files with no checker are `[SKIP]`, not `[PASS]`. |
| `ctx mcp` | Speaks JSON-RPC on stdin/stdout. |
| `ctx mcp --install` | Merges the server into installed editor configs. |
| `ctx --version` | Prints `ctx` and the version. |

`ctx map` stores the absolute workspace path in `.agent-context.json` because MCP clients must pass that path back as `workspace_path`. That file is gitignored. Do not commit it.

Supported editors for `ctx mcp --install`: Cursor, VS Code, Claude Desktop, Claude Code, Antigravity, OpenCode, and Codex. Protocol support is dual-era: `initialize` and `ping` for 2024–2025 clients, and `server/discover` for MCP `2026-07-28`.

## Prerequisites

Install Python 3.8 or newer and confirm it is on `PATH`. Git is optional; it is used by `ctx check` (changed files) and by the pre-commit hook.

**Windows (Command Prompt or PowerShell)**

```powershell
python --version
```

If `python` is missing, install from [python.org](https://www.python.org/downloads/windows/) and enable **Add python.exe to PATH**, or try `py -3 --version`.

**macOS**

```bash
python3 --version
```

If it is missing: `xcode-select --install`, or install Python 3 from [python.org](https://www.python.org/downloads/macos/).

**Linux**

```bash
python3 --version
```

Debian/Ubuntu: `sudo apt update && sudo apt install -y python3`. Fedora: `sudo dnf install -y python3`.

## Install

Clone the repository, then run the deploy script from the repository root. Paths below are relative to that root.

```bash
git clone https://github.com/Jayaram-Nambiar/Global_Context_Orchestration.git
cd Global_Context_Orchestration
```

### Windows

PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\deploy.ps1
```

Close the terminal and open a new one so the user `PATH` update is visible. Then:

```powershell
ctx --version
```

`deploy.ps1` copies `src/engine.py` and `src/mcp_server.py` to `%USERPROFILE%\.agent-context-engine\`, writes `ctx.cmd`, `ctx.ps1`, and `ctx` there, adds that directory to the user `PATH`, and runs `ctx mcp --install`. If Scoop shims exist, it copies the Windows launchers there too.

### macOS and Linux

```bash
bash scripts/deploy.sh
```

The script copies the same two Python files to `$HOME/.agent-context-engine/` and writes a `ctx` launcher in that directory. Add it to your shell profile if `ctx` is not found:

```bash
echo 'export PATH="$HOME/.agent-context-engine:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

On zsh, use `~/.zshrc` instead of `~/.bashrc`. Then:

```bash
ctx --version
```

### Run from the clone without installing

From the repository root:

```bash
python src/engine.py --version
```

On macOS or Linux, use `python3` if `python` is not Python 3:

```bash
python3 src/engine.py map
python3 src/engine.py query cmd_map
python3 src/engine.py slice src/engine.py 1012 1040
python3 src/engine.py check
```

Windows Command Prompt can also call the repo launcher:

```bat
bin\ctx.cmd map
```

PowerShell:

```powershell
.\bin\ctx.ps1 map
```

macOS and Linux:

```bash
chmod +x bin/ctx
./bin/ctx map
```

Cursor loads the installed copy at `~/.agent-context-engine/mcp_server.py`, not this git tree. After you change `src/`, run `scripts/deploy.ps1` or `scripts/deploy.sh` again.

## Use it on a project

From the project you want to index (not from your home directory):

```bash
ctx map
ctx query main
ctx slice src/engine.py 1 40
ctx graph
ctx check
```

`ctx slice` swaps reversed ranges and never returns more than 150 lines. `ctx check` with no flags looks at uncommitted git changes, then recently modified files. `ctx check --all` walks the tree.

### Editor connection

```bash
ctx mcp --install
```

Restart the editor afterward. Manual config paths and JSON examples are in [docs/EDITOR_INTEGRATION.md](docs/EDITOR_INTEGRATION.md). The installer merges existing configs. It skips a file that is not valid JSON, and it does not wipe Claude Code `projects` entries.

## Use cases

- Find the definition of a function, class, or hook before opening files.
- Read only the line range that an edit will touch.
- Order a multi-file change so a module is edited after the files it depends on, and see import cycles first.
- Check syntax of the files just changed before treating the task as finished.
- Block a commit that introduces a syntax error, using the optional git hook below.

The same jobs are available as shell commands (`ctx map`, `ctx query`, `ctx slice`, `ctx graph`, `ctx check`) and as MCP tools. Use the shell commands from a terminal. Use the MCP tools when the agent harness can call tools on the `agent-context-engine` server. Cursor exposes that server as `user-agent-context-engine`; the tool names below do not change.

## Calling tools from an agent harness

Connect the server with `ctx mcp --install`, then reload MCP in the editor. The MCP process working directory is not the project. Pass an absolute `workspace_path` on every tool that accepts it. Do not pass `$HOME` or a drive root; those calls are refused.

Call the tools in this order:

1. `ctx_get_map` — once per task, before searching or reading. Argument: `workspace_path` (absolute project root). The result is the structural index.
2. `ctx_query_symbol` — when the name of a function, class, method, or hook is known. Arguments: `symbol` (required), `workspace_path` (same absolute root). The result names the relative file and the match. A function match includes its argument names and the line of the definition. A method match is reported on the class declaration line. The result does not include the function body. If the index is missing, this call builds it first.
3. `ctx_slice` — when that body, or any other range, is required. Arguments: `file_path` (absolute path to the file), `start_line`, `end_line` (both 1-indexed, inclusive). A reversed range is swapped. The server returns at most 150 lines. A relative `file_path` is resolved from the MCP process directory, not from the project, so pass an absolute path.
4. `ctx_get_graph` — before a change that spans several files. Argument: `workspace_path`. The result lists entry points, cycles, and a topological order. If the index is missing, this call builds it.
5. `ctx_check` — after the edit, before the agent reports completion. Arguments: `workspace_path`, and `check_all` (`false` to check uncommitted or recently modified files, `true` to walk the tree). `[SKIP]` means that file type was not checked. `[FAIL]` means a checker reported a syntax error.

A harness that has a shell but no MCP client should run the matching `ctx` command from the project root instead of calling these tools.

### Optional git hook

From this repository root, the hook runs `ctx check` before each commit.

Windows:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install-hooks.ps1
```

macOS and Linux:

```bash
bash scripts/install-hooks.sh
```

Skip one commit with `git commit --no-verify` or `SKIP_CTX=1`.

## Tests

From the repository root:

```bash
python -m unittest discover -s tests -p "test_*.py" -v
```

Windows PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\test.ps1
```

## Repository layout

```
├── bin/                  ctx, ctx.cmd, ctx.ps1 (launch src/engine.py)
├── src/engine.py         Parsers, map, graph, slice, check, CLI
├── src/mcp_server.py     stdio MCP server and editor installer
├── scripts/              deploy, pre-commit hook, test runner
├── tests/                unittest suite
├── docs/                 Architecture, editor setup, agent notes, runbook
├── AGENTS.md             Constraints for agents editing this repo
├── LICENSE               MIT
└── README.md
```

Generated locally and not committed: `.agent-context.json`.

Further reading:

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — parsing and index design
- [docs/EDITOR_INTEGRATION.md](docs/EDITOR_INTEGRATION.md) — per-editor MCP config
- [docs/AGENT_MEMORY.md](docs/AGENT_MEMORY.md) — invariants for people changing the protocol or installer
- [CONTRIBUTING.md](CONTRIBUTING.md) — how to change the code
- [SECURITY.md](SECURITY.md) — how to report a vulnerability

## Troubleshooting

**`ctx` is not recognized.** Open a new terminal. Windows: user PATH should include `%USERPROFILE%\.agent-context-engine`. macOS and Linux: `export PATH="$HOME/.agent-context-engine:$PATH"`.

**Python was not found.** Reinstall Python 3.8+ and put it on `PATH`. On Windows, avoid `pythonw.exe` for the MCP server; the installer pins `python.exe`.

**`ctx map` refuses the directory.** It will not walk your home folder or a drive root. `cd` into the project and run `ctx map` again.

**Editor MCP discovery fails with invalid JSON.** The server must print only JSON-RPC on stdout. Redeploy, run `ctx mcp --install`, and reload MCP servers in the editor.

**`ctx mcp --install` skipped an editor.** Open that editor once so it creates its config file, or repair invalid JSON, then run the command again.

## Update and uninstall

To update, pull this repository and run `scripts/deploy.ps1` or `scripts/deploy.sh` again, then `ctx mcp --install`.

To remove the install:

1. Delete the `%USERPROFILE%\.agent-context-engine` directory (Windows) or `$HOME/.agent-context-engine` (macOS and Linux).
2. On Windows, remove that directory from your user `PATH`. On macOS and Linux, remove the `export PATH="$HOME/.agent-context-engine:$PATH"` line from your shell profile.
3. Remove the `agent-context-engine` entry from each editor's MCP config. Paths are listed in [docs/EDITOR_INTEGRATION.md](docs/EDITOR_INTEGRATION.md).
4. If you installed the git hook, delete `.git/hooks/pre-commit` in repositories where you installed it.

## Attribution

This repository is original source. It does not vendor third-party application code, and it has no package dependencies.

It implements the public [Model Context Protocol](https://modelcontextprotocol.io/) specification (legacy `initialize` through `2025-11-25`, and `server/discover` for `2026-07-28`). The protocol specification is not included in this repository. Graph ordering uses standard depth-first cycle detection and Kahn's algorithm; those algorithms are not copied from another project.

If you copy or redistribute this project, keep the copyright notice and the MIT license text. See [LICENSE](LICENSE).

## License

[MIT](LICENSE) © 2026 Jayaram Nambiar
