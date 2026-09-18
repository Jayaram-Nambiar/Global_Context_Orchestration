# Agent Memory — Hard-Won Invariants

Durable notes for future agents working in this repository. Prefer this file over chat history. When you discover a new invariant, append a dated entry here rather than burying it in a commit message.

Last verified against MCP spec: [2026-07-28](https://modelcontextprotocol.io/specification/2026-07-28/changelog).

---

## Product invariants (do not regress)

1. **Stdlib only.** No pip packages, no Node MCP SDK, no cloud index. Python 3.8+.
2. **Stdout is JSON-RPC only** when running `ctx mcp`. Isolate with `sys.stdout = sys.stderr` and write RPC to the original stdout. Cursor fails live discovery with `Unexpected token 'ESC'` if ANSI banners leak.
3. **Always pass `workspace_path`.** MCP process CWD is not the user's repo. MCP Roots are deprecated in 2026-07-28; do not add `roots/list`.
4. **Slice cap is 150 lines.** Product rule, not a suggestion.
5. **`ctx check` never fakes `[PASS]`.** Uncheckable files (no compiler / unsupported type) print `[SKIP]`.
6. **Refuse `$HOME` and filesystem roots** in map/check. Cap walks at 8,000 files.
7. **Installer must not clobber invalid JSON.** Return `skipped (invalid existing config)`.
8. **Do not implement Streamable HTTP, SSE, or OAuth** for this local stdio server.
9. **Do not rewrite `engine.py` language parsers** unless a specific parser bug is reproduced.

## Dual-era MCP (v1.3.0)

| Client era | Handshake | This server |
| :--- | :--- | :--- |
| Cursor / Claude Desktop / 2024–2025 | `initialize` → `notifications/initialized` → `tools/list` | Keep `initialize` and `ping`. Echo requested version if listed. |
| MCP 2026-07-28 | Optional `server/discover`; per-request `_meta` | **MUST** implement `server/discover`. `initialize` remains for legacy. |

`DiscoverResult` requires `resultType`, `supportedVersions`, `capabilities`, `ttlMs`, `cacheScope`. Put identity in `_meta["io.modelcontextprotocol/serverInfo"]`. `tools/list` is a CacheableResult (`resultType`, `ttlMs`, `cacheScope`) and MUST return tools in a stable order.

Do not remove `ping` while Cursor still sends it. Unknown methods return JSON-RPC `-32601`.

## Editor config shapes (installer)

| Host | Path | Collection key | Notes |
| :--- | :--- | :--- | :--- |
| Cursor | `~/.cursor/mcp.json` | `mcpServers` | `command` + `args` with `-u`. Cursor's session namespace becomes `user-agent-context-engine`. |
| Gemini / Antigravity config | `~/.gemini/config/mcp_config.json` | `mcpServers` | Merge; do not drop sibling servers. |
| Antigravity IDE (live) | `~/.gemini/antigravity/mcp_config.json` | `mcpServers` | **This is the file Antigravity actually reads.** Configuring only `~/.gemini/config/` is not enough. |
| Claude Desktop | `%APPDATA%/Claude/claude_desktop_config.json` | `mcpServers` | Skip if Claude was never installed (`require_parent`). |
| VS Code Copilot | `%APPDATA%/Code/User/mcp.json` | **`servers`** (not `mcpServers`) | Include `"type": "stdio"`. Empty file is valid. |
| Claude Code (user scope) | `~/.claude.json` | top-level `mcpServers` | Merge only. **Never wipe `projects.*`.** Do not create this file if missing. Official CLI: `claude mcp add --transport stdio --scope user`. |
| OpenCode | `~/.config/opencode/opencode.jsonc` | `mcp` | `type: local`, `command: [python, -u, mcp_server.py]`. Strip empty-string keys (`""`) — a common `$schema` mis-key. |
| Codex | `~/.codex/config.toml` | `[mcp_servers.agent-context-engine]` | String-replace the table. Do **not** scan table bodies with `[^\[]*` — `args = ["-u", ...]` contains `[`. |

Windows launchers must pin `python.exe`, not `pythonw.exe`. Unbuffered (`-u`) is required for stdio MCP.

## Failure modes already paid for

- **2026-09-17:** Cursor MCP error `Unexpected token 'ESC'` — `cmd_map` ANSI went to stdout. Fix: RPC stdout isolation + ANSI strip in tool results.
- **2026-09-17:** `ctx_query_symbol` timed out when workspace defaulted to a huge CWD / `$HOME`. Fix: unsafe-workspace guard + require `workspace_path`.
- **2026-09-17:** `ctx check` reported `[PASS]` for files it did not actually compile. Fix: `[SKIP]`.
- **2026-09-17:** Installer overwrote corrupt editor JSON. Fix: skip invalid files.
- **2026-09-18:** Spec latest is `2026-07-28`. Dual-era servers keep `initialize` **and** MUST add `server/discover`.
- **2026-09-18:** VS Code user MCP uses `{ "servers": ... }`. Claude Code user MCP is `~/.claude.json` (not `claude_desktop_config.json`). Codex is TOML.
- **2026-09-18:** `git push` to `Jayaram-Nambiar/Global_Context_Orchestration` failed while `gh` was logged in as `JayaramNambiar`. Switch account, do not force-push.
- **2026-09-18:** Language dispatch is `language_for_path` + `parse_file_content`. `.gs` already used the JS parser; GAS hooks are `SpreadsheetApp` / `google.script.run`. Jinja is `.j2`/`.jinja`/`.njk`/`.liquid`, not generic `.html`. Mermaid is `.mmd`/`.mermaid` plus Markdown fences; Markdown without a fence is omitted from the map so READMEs do not bloat the index. `ctx check` ignores Markdown entirely (no checker — would otherwise SKIP every README). `Dockerfile`/`Makefile` have no suffix — handle them in `language_for_path`. Do not add a syntax checker unless a local binary can actually parse the file.

## How future agents should work here

Follow `AGENTS.md` and `docs/AGENT_TRAINING.md`. After non-trivial MCP or installer changes, run `python -m unittest discover -s tests -v` and `ctx check` from the repo root. Redeploy with `scripts/deploy.ps1` so `~/.agent-context-engine` matches `src/`. Cursor only loads the **installed** copy, not the git working tree.
