#!/usr/bin/env python3
"""
Agent Context Engine - Model Context Protocol (MCP) Server
Pure Python standard library implementation of JSON-RPC 2.0 stdio MCP server.
Zero external dependencies. Fully compliant with MCP 2024-11-05 specification.
"""

import io
import json
import os
import sys
from pathlib import Path

# Ensure engine is accessible
CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

import engine

PROTOCOL_VERSION = "2024-11-05"
SERVER_NAME = "agent-context-engine"
SERVER_VERSION = engine.VERSION

TOOLS = [
    {
        "name": "ctx_get_map",
        "description": "Generate or retrieve the minified .agent-context.json metadata map containing class hierarchies, functions, arguments, and cross-boundary network/process hooks for the workspace.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "workspace_path": {
                    "type": "string",
                    "description": "Target workspace directory path (defaults to current working directory)"
                }
            }
        }
    },
    {
        "name": "ctx_query_symbol",
        "description": "Search .agent-context.json for matching classes, methods, functions, or cross-boundary hooks without reading file contents.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "Symbol name, keyword, or hook name to look up"
                },
                "workspace_path": {
                    "type": "string",
                    "description": "Target workspace directory path (defaults to current working directory)"
                }
            },
            "required": ["symbol"]
        }
    },
    {
        "name": "ctx_slice",
        "description": "Retrieve a specific, 1-indexed line-range slice of a source file. Use this instead of reading full files over 150 lines.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to the target file"
                },
                "start_line": {
                    "type": "integer",
                    "description": "Starting line number (1-indexed)"
                },
                "end_line": {
                    "type": "integer",
                    "description": "Ending line number (inclusive)"
                }
            },
            "required": ["file_path", "start_line", "end_line"]
        }
    },
    {
        "name": "ctx_check",
        "description": "Execute local native syntax compilation tests (Python, PowerShell, Node/JS, JSON) to intercept syntax errors before completing code modifications.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "workspace_path": {
                    "type": "string",
                    "description": "Target workspace directory path (defaults to current working directory)"
                },
                "check_all": {
                    "type": "boolean",
                    "description": "If true, checks all supported files in workspace rather than only changed/recent files"
                }
            }
        }
    },
    {
        "name": "ctx_get_graph",
        "description": "Retrieve the architectural dependency graph, root entry points, circular dependencies, and recommended topological code edit sequence for the workspace.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "workspace_path": {
                    "type": "string",
                    "description": "Target workspace directory path (defaults to current working directory)"
                }
            }
        }
    }
]


class MCPServer:
    """Implements JSON-RPC 2.0 MCP server handlers."""

    def __init__(self):
        self.tools = {t["name"]: t for t in TOOLS}

    def handle_request(self, request: dict) -> dict | None:
        """Processes a single JSON-RPC request and returns response dict or None for notifications."""
        req_id = request.get("id")
        method = request.get("method")
        params = request.get("params", {})

        # Handle notifications (no id)
        if req_id is None:
            if method == "notifications/initialized":
                return None
            return None

        # Route methods
        if method == "initialize":
            return self._handle_initialize(req_id, params)
        elif method == "ping":
            return {"jsonrpc": "2.0", "id": req_id, "result": {}}
        elif method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"tools": TOOLS}
            }
        elif method == "tools/call":
            return self._handle_tool_call(req_id, params)
        else:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {
                    "code": -32601,
                    "message": f"Method '{method}' not found"
                }
            }

    def _handle_initialize(self, req_id, params):
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {
                    "tools": {}
                },
                "serverInfo": {
                    "name": SERVER_NAME,
                    "version": SERVER_VERSION
                }
            }
        }

    def _handle_tool_call(self, req_id, params):
        tool_name = params.get("name")
        args = params.get("arguments", {})

        if tool_name not in self.tools:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {
                    "code": -32602,
                    "message": f"Unknown tool: {tool_name}"
                }
            }

        try:
            if tool_name == "ctx_get_map":
                ws = Path(args.get("workspace_path") or os.getcwd())
                # Capture map output
                engine.cmd_map(ws)
                map_file = ws / ".agent-context.json"
                if map_file.is_file():
                    with open(map_file, "r", encoding="utf-8") as f:
                        map_content = f.read()
                    text_out = map_content
                else:
                    text_out = json.dumps({"error": "Failed to generate context map"})

                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [{"type": "text", "text": text_out}]
                    }
                }

            elif tool_name == "ctx_query_symbol":
                symbol = args.get("symbol", "")
                ws = Path(args.get("workspace_path") or os.getcwd())
                buf = io.StringIO()
                old_stdout = sys.stdout
                sys.stdout = buf
                try:
                    engine.cmd_query(ws, symbol)
                finally:
                    sys.stdout = old_stdout

                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [{"type": "text", "text": buf.getvalue().strip()}]
                    }
                }

            elif tool_name == "ctx_slice":
                file_path = Path(args.get("file_path"))
                start = int(args.get("start_line", 1))
                end = int(args.get("end_line", 1))
                buf = io.StringIO()
                old_stdout = sys.stdout
                sys.stdout = buf
                try:
                    engine.cmd_slice(file_path, start, end)
                finally:
                    sys.stdout = old_stdout

                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [{"type": "text", "text": buf.getvalue().strip()}]
                    }
                }

            elif tool_name == "ctx_check":
                ws = Path(args.get("workspace_path") or os.getcwd())
                check_all = bool(args.get("check_all", False))
                buf = io.StringIO()
                old_stdout = sys.stdout
                sys.stdout = buf
                try:
                    exit_code = engine.cmd_check(ws, check_all=check_all)
                finally:
                    sys.stdout = old_stdout

                is_err = exit_code != 0
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "isError": is_err,
                        "content": [{"type": "text", "text": buf.getvalue().strip()}]
                    }
                }

            elif tool_name == "ctx_get_graph":
                ws = Path(args.get("workspace_path") or os.getcwd())
                context_file = ws / ".agent-context.json"
                if not context_file.is_file():
                    engine.cmd_map(ws)
                if context_file.is_file():
                    with open(context_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    graph_data = data.get("graph", {})
                    text_out = json.dumps(graph_data, indent=2)
                else:
                    text_out = json.dumps({"error": "Failed to generate graph metadata"})

                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [{"type": "text", "text": text_out}]
                    }
                }

        except Exception as e:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "isError": True,
                    "content": [{"type": "text", "text": f"Execution error: {e}"}]
                }
            }


def configure_editors(engine_dir: Path = None) -> dict:
    """
    Idempotently configures and registers the Agent Context Engine MCP server
    across all detected editor environments:
    - Antigravity: ~/.gemini/config/mcp_config.json
    - Claude Desktop: %APPDATA%/Claude/claude_desktop_config.json
    - Cursor: ~/.cursor/mcp.json
    - OpenCode: ~/.config/opencode/opencode.jsonc
    """
    if engine_dir is None:
        installed_mcp = Path.home() / ".agent-context-engine" / "mcp_server.py"
        server_target = installed_mcp if installed_mcp.is_file() else Path(__file__).resolve()
    else:
        server_target = Path(engine_dir) / "mcp_server.py"

    results = {}

    def _clean_json_str(raw: str) -> str:
        lines = []
        for line in raw.splitlines():
            trimmed = line.strip()
            if trimmed.startswith("//"):
                continue
            lines.append(line)
        return "\n".join(lines)

    def _load_json_file(file_path: Path) -> dict:
        if not file_path.is_file() or file_path.stat().st_size == 0:
            return {}
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = _clean_json_str(f.read())
                if not content.strip():
                    return {}
                return json.loads(content)
        except Exception:
            return {}

    def _write_json_file(file_path: Path, data: dict):
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    mcp_def_standard = {
        "command": "python",
        "args": [str(server_target)]
    }

    # 1. Antigravity
    gemini_mcp = Path.home() / ".gemini" / "config" / "mcp_config.json"
    data = _load_json_file(gemini_mcp)
    if "mcpServers" not in data or not isinstance(data["mcpServers"], dict):
        data["mcpServers"] = {}
    data["mcpServers"]["agent-context-engine"] = mcp_def_standard
    _write_json_file(gemini_mcp, data)
    results["antigravity"] = {"path": str(gemini_mcp), "status": "configured"}

    # 2. Claude Desktop
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming"))
        claude_path = Path(appdata) / "Claude" / "claude_desktop_config.json"
    elif sys.platform == "darwin":
        claude_path = Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
    else:
        claude_path = Path.home() / ".config" / "Claude" / "claude_desktop_config.json"

    if claude_path.parent.exists() or claude_path.exists():
        data = _load_json_file(claude_path)
        if "mcpServers" not in data or not isinstance(data["mcpServers"], dict):
            data["mcpServers"] = {}
        data["mcpServers"]["agent-context-engine"] = mcp_def_standard
        _write_json_file(claude_path, data)
        results["claude"] = {"path": str(claude_path), "status": "configured"}
    else:
        results["claude"] = {"path": str(claude_path), "status": "skipped (not installed)"}

    # 3. Cursor
    cursor_mcp = Path.home() / ".cursor" / "mcp.json"
    data = _load_json_file(cursor_mcp)
    if "mcpServers" not in data or not isinstance(data["mcpServers"], dict):
        data["mcpServers"] = {}
    data["mcpServers"]["agent-context-engine"] = mcp_def_standard
    _write_json_file(cursor_mcp, data)
    results["cursor"] = {"path": str(cursor_mcp), "status": "configured"}

    # 4. OpenCode
    opencode_dir = Path.home() / ".config" / "opencode"
    opencode_file = opencode_dir / "opencode.jsonc"
    if not opencode_file.exists() and (opencode_dir / "opencode.json").exists():
        opencode_file = opencode_dir / "opencode.json"

    if opencode_dir.exists():
        data = _load_json_file(opencode_file)
        if "mcp" not in data or not isinstance(data["mcp"], dict):
            data["mcp"] = {}
        data["mcp"]["agent-context-engine"] = {
            "type": "local",
            "command": ["python", str(server_target)],
            "enabled": True
        }
        _write_json_file(opencode_file, data)
        results["opencode"] = {"path": str(opencode_file), "status": "configured"}
    else:
        results["opencode"] = {"path": str(opencode_file), "status": "skipped (not installed)"}

    return results


def cmd_install_mcp(engine_dir: Path = None) -> int:
    """CLI action to install/update MCP configurations across editors."""
    print("\033[1;36m[*] Configuring Agent Context Engine MCP across AI coding tools...\033[0m")
    results = configure_editors(engine_dir)
    for editor, info in results.items():
        status = info["status"]
        path = info["path"]
        if status == "configured":
            print(f"  \033[1;32m[+] {editor.capitalize():12}\033[0m -> {path}")
        else:
            print(f"  \033[1;30m[-] {editor.capitalize():12}\033[0m -> {status}")
    print("\033[1;32m[+] MCP configuration synchronized successfully.\033[0m\n")
    return 0


def run_stdio_server():
    """Runs the MCP server over standard input/output."""
    server = MCPServer()

    # Ensure stdout is unbuffered in UTF-8
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)
    sys.stdin = io.TextIOWrapper(sys.stdin.buffer, encoding="utf-8")

    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                break
            line = line.strip()
            if not line:
                continue

            request = json.loads(line)
            response = server.handle_request(request)
            if response is not None:
                sys.stdout.write(json.dumps(response, separators=(",", ":")) + "\n")
                sys.stdout.flush()
        except (KeyboardInterrupt, SystemExit):
            break
        except Exception as e:
            err_resp = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": f"Parse error: {e}"}
            }
            sys.stdout.write(json.dumps(err_resp, separators=(",", ":")) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in ("--install", "install", "-i"):
        sys.exit(cmd_install_mcp())
    else:
        run_stdio_server()

