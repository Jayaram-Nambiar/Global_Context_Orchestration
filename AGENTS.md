# Agent instructions for this repository

This repo is the **Agent Context Engine (`ctx`)** — a stdlib-only CLI + stdio MCP server. Read `docs/AGENT_MEMORY.md` before changing protocol or installer behavior.

## Required loop

1. `ctx map` (or `ctx_get_map` with this repo as `workspace_path`) before browsing files.
2. `ctx query <symbol>` / `ctx_query_symbol` instead of whole-tree grep for known names.
3. Never ingest files over 150 lines in full — `ctx slice` / `ctx_slice`.
4. After edits: `ctx check` / `ctx_check`, then `python -m unittest discover -s tests`.

## Constraints

- Python 3.8+, standard library only. No pip, no HTTP MCP transport.
- MCP stdout is JSON-RPC only. Diagnostics go to stderr.
- Pass absolute `workspace_path` into every MCP tool. Do not map `$HOME`.
- Dual-era protocol: keep `initialize` + `ping` for Cursor; implement `server/discover` for MCP 2026-07-28.
- `ctx mcp --install` must merge editor configs, never clobber invalid JSON or Claude Code `projects`.
- Cursor hosts the **installed** server at `~/.agent-context-engine/mcp_server.py`. After changing `src/`, run `scripts/deploy.ps1`.
