# Contributing

Issues and pull requests are welcome. This repository is MIT licensed. Contributions are accepted under the same license. Keep the copyright notice and [LICENSE](LICENSE) text with any redistribution.

## Setup

Clone the repository and work from its root. Python 3.8+ is enough. There is nothing to `pip install`.

```bash
python -m unittest discover -s tests -p "test_*.py" -v
python src/engine.py check
```

On macOS or Linux, use `python3` when `python` is not Python 3.

## Changing the engine

Read [docs/AGENT_MEMORY.md](docs/AGENT_MEMORY.md) before changing the MCP server, the installer, or a parser.

- Standard library only. No HTTP transport, SSE, or OAuth.
- `ctx mcp` stdout is JSON-RPC only. Diagnostics go to stderr.
- `ctx slice` stays capped at 150 lines.
- `ctx check` prints `[SKIP]` when it cannot actually parse a file.
- `ctx map` and `ctx check` refuse `$HOME` and filesystem roots.
- Installer merges editor configs. It must not clobber invalid JSON or Claude Code `projects`.
- After editing `src/`, redeploy with `scripts/deploy.ps1` (Windows) or `scripts/deploy.sh` (macOS and Linux). Cursor runs the installed copy under the home directory, not this tree.

Add a test in `tests/` for a behavior change. Do not commit `.agent-context.json`, credentials, or logs.

## Adding a language

1. Map the extension in `LANGUAGE_MAP` in `src/engine.py`. Extensionless names such as `Dockerfile` and `Makefile` belong in `language_for_path`.
2. Return the same dictionary as the other parsers: `classes`, `functions`, and `hooks`. Register the parser in `parse_file_content`.
3. Add a `ctx check` compiler only when a local program can actually parse the file. Otherwise the result is `[SKIP]`.
4. Add a test in `tests/test_engine.py`.
