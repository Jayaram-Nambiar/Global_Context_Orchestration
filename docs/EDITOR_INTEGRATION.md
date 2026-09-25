# Editor Integration & Surgical Rule Injection Guide

This guide provides configuration instructions and injection blocks for integrating the **Agent Context Engine (`ctx`)** across **Antigravity**, **Claude Desktop**, **Cursor**, **OpenCode**, and **VS Code / Claude Code**.

---

## 1. Dual-Integration Architecture

The Agent Context Engine connects to AI coding agents via two complementary channels:
1. **Model Context Protocol (MCP)**: Native stdio JSON-RPC 2.0 tool interface allowing the AI to call `ctx_get_map`, `ctx_query_symbol`, `ctx_slice`, `ctx_check`, and `ctx_get_graph` without executing shell sub-processes.
2. **Behavioral Rules Injection**: Persistent prompt directives instructing the agent to always map before reading, slice large files, and run syntax validation before completing tasks.

---

## 2. Model Context Protocol (MCP) Setup

Install from the repository root first (`README.md`). Then run `ctx mcp --install`. That command writes the absolute Python interpreter path and `-u` (unbuffered stdio) into each editor config. Manual examples below use `python`; on Windows, prefer the interpreter path the installer writes.

### Installed server path

`ctx mcp --install` writes the absolute path for the current machine. Manual configs must use that same absolute path. The server is installed outside this repository:

| Operating system | Path to `mcp_server.py` |
| :--- | :--- |
| Windows | `%USERPROFILE%\.agent-context-engine\mcp_server.py` |
| macOS | `$HOME/.agent-context-engine/mcp_server.py` |
| Linux | `$HOME/.agent-context-engine/mcp_server.py` |

In JSON or TOML, paste the expanded path for your account. Examples below use `<path-to-mcp_server.py>` as that placeholder. Do not commit an expanded home-directory path.

### Manual MCP Configurations

#### Antigravity (Google Gemini / Antigravity IDE)
- **Config Path**: `~/.gemini/config/mcp_config.json`
- **Format**:
  ```json
  {
    "mcpServers": {
      "agent-context-engine": {
        "command": "python",
        "args": [
          "-u",
          "<path-to-mcp_server.py>"
        ]
      }
    }
  }
  ```

#### Claude Desktop
- **Config Path**:
  - Windows: `%APPDATA%\Claude\claude_desktop_config.json`
  - macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
  - Linux: `~/.config/Claude/claude_desktop_config.json`
- **Format**:
  ```json
  {
    "mcpServers": {
      "agent-context-engine": {
        "command": "python",
        "args": [
          "-u",
          "<path-to-mcp_server.py>"
        ]
      }
    }
  }
  ```

#### Cursor
- **Config Path**: `~/.cursor/mcp.json`
- **Format**:
  ```json
  {
    "mcpServers": {
      "agent-context-engine": {
        "command": "python",
        "args": [
          "-u",
          "<path-to-mcp_server.py>"
        ]
      }
    }
  }
  ```

#### OpenCode
- **Config Path**: `~/.config/opencode/opencode.jsonc` (or `opencode.json`)
- **Format** (matches official `https://opencode.ai/config.json` schema):
  ```json
  {
    "$schema": "https://opencode.ai/config.json",
    "mcp": {
      "agent-context-engine": {
        "type": "local",
        "command": [
          "python",
          "-u",
          "<path-to-mcp_server.py>"
        ],
        "enabled": true
      }
    }
  }
  ```

#### VS Code (GitHub Copilot MCP)
- **Config Path**: `%APPDATA%\Code\User\mcp.json` (macOS: `~/Library/Application Support/Code/User/mcp.json`)
- **Format** (note: the collection key is `servers`, not `mcpServers`):
  ```json
  {
    "servers": {
      "agent-context-engine": {
        "type": "stdio",
        "command": "python",
        "args": ["-u", "<path-to-mcp_server.py>"]
      }
    }
  }
  ```

#### Claude Code (user scope)
- **Config Path**: `~/.claude.json` top-level `mcpServers`. Per-repo `projects.*.mcpServers` is left untouched.
- **Format**:
  ```json
  {
    "mcpServers": {
      "agent-context-engine": {
        "type": "stdio",
        "command": "python",
        "args": ["-u", "<path-to-mcp_server.py>"]
      }
    }
  }
  ```

#### Codex
- **Config Path**: `~/.codex/config.toml`
- **Format**:
  ```toml
  [mcp_servers.agent-context-engine]
  command = "python"
  args = ["-u", "<path-to-mcp_server.py>"]
  ```

#### Antigravity IDE (live config)
Antigravity also reads `~/.gemini/antigravity/mcp_config.json` (same `mcpServers` shape as `~/.gemini/config/mcp_config.json`). `ctx mcp --install` writes both.

---

## 3. Behavioral Rules Injection

The following standard directive is injected into each editor's system prompt profile:

```markdown
---

## 8. Agent Context Engine & Token Optimization Protocol

To minimize LLM token consumption and prevent context exhaustion/hallucination loops:
- **Map Before Read (`ctx map` or `ctx_get_map`)**: ALWAYS run `ctx map` or call `ctx_get_map` before inspecting or editing files. Consult `.agent-context.json` to identify function signatures, classes, and cross-boundary hooks without dumping raw file bodies.
- **Surgical Line-Range Slicing**: NEVER dump or read full files exceeding 150 lines. Rely strictly on line-range slicing (`ctx slice <file> <start> <end>` or `ctx_slice`) targeting only the specific functions/blocks needed.
- **Pre-Completion Syntax Interception (`ctx check` or `ctx_check`)**: ALWAYS execute `ctx check` or `ctx_check` automatically after code updates. Intercept compilation and syntax errors locally before returning to the user or claiming completion.
- **Topological Edit Sequencing (`ctx graph` or `ctx_get_graph`)**: Consult the dependency graph to plan multi-file edits (leaf prerequisite modules first) and verify zero circular cycles.
```

### Profile Locations

1. **Antigravity**:
   - Global: `~/.gemini/config/rules/global-guidelines.md`
   - Workspace: `<workspace>/.agents/rules/agent-context.md`

2. **Cursor**:
   - Modern MDC Profile: `~/.cursor/rules/global-rules.mdc`
   - Legacy: `~/.cursorrules`
   - Workspace: `<workspace>/.cursor/rules/context-optimization.mdc`

3. **OpenCode**:
   - Instructions file: `~/.config/opencode/AGENTS.md` (referenced via `opencode.jsonc`)

4. **Claude Code / VS Code**:
   - Global: `~/.claude/config.json` or `CLAUDE.md`
   - Copilot: `.github/copilot-instructions.md`

