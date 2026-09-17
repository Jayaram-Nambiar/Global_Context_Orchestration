#!/usr/bin/env python3
"""
Agent Context Engine - Model Context Protocol (MCP) Server
Pure Python standard library implementation of JSON-RPC 2.0 stdio MCP server.
Zero external dependencies. Compliant with MCP 2025-06-18 (also 2025-03-26, 2024-11-05).
"""

import io
import json
import os
import sys
from pathlib import Path
from typing import Optional

# Ensure engine is accessible
CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

import engine

# Newest first. If the client requests a version in this tuple, echo it (spec MUST).
SUPPORTED_PROTOCOL_VERSIONS = ("2025-06-18", "2025-03-26", "2024-11-05")
LATEST_PROTOCOL_VERSION = SUPPORTED_PROTOCOL_VERSIONS[0]
PROTOCOL_VERSION = LATEST_PROTOCOL_VERSION
SERVER_NAME = "agent-context-engine"
SERVER_VERSION = engine.VERSION
SERVER_INSTRUCTIONS = (
    "Always pass workspace_path as the absolute project root. "
    "Call ctx_get_map before ctx_query_symbol or ctx_get_graph. "
    "Use ctx_slice for files over 150 lines. "
    "Call ctx_check after edits. "
    "Do not rely on the MCP process working directory."
)

_ANNOT_WRITE_MAP = {
    "readOnlyHint": False,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": False,
}
_ANNOT_READ = {
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": False,
}

TOOLS = [
    {
        "name": "ctx_get_map",
        "title": "Map workspace structure",
        "description": "Generate or retrieve the minified .agent-context.json metadata map containing class hierarchies, functions, arguments, and cross-boundary network/process hooks for the workspace. Always pass workspace_path as the absolute project root.",
        "annotations": _ANNOT_WRITE_MAP,
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
        "title": "Query symbol map",
        "description": "Search .agent-context.json for matching classes, methods, functions, or cross-boundary hooks without reading file contents. Pass workspace_path as the absolute project root.",
        "annotations": _ANNOT_WRITE_MAP,
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
        "title": "Read file slice",
        "description": "Retrieve a specific, 1-indexed line-range slice of a source file. Use this instead of reading full files over 150 lines.",
        "annotations": _ANNOT_READ,
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
        "title": "Validate syntax",
        "description": "Execute local native syntax compilation tests (Python, PowerShell, Node/JS, JSON) to intercept syntax errors before completing code modifications.",
        "annotations": _ANNOT_READ,
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
        "title": "Get dependency graph",
        "description": "Retrieve the architectural dependency graph, root entry points, circular dependencies, and recommended topological code edit sequence for the workspace. Pass workspace_path as the absolute project root.",
        "annotations": _ANNOT_WRITE_MAP,
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


def _as_int(value, default):
    if value is None or value == "":
        return default
    return int(value)


def _as_bool(value, default=False):
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "on")
    return bool(value)


def _tool_text(req_id, text, is_error=False):
    result = {"content": [{"type": "text", "text": text or ""}]}
    if is_error:
        result["isError"] = True
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def _capture_stdout(fn):
    buf = io.StringIO()
    old = sys.stdout
    sys.stdout = buf
    try:
        value = fn()
    finally:
        sys.stdout = old
    return value, engine.strip_ansi(buf.getvalue().strip())


class MCPServer:
    """Implements JSON-RPC 2.0 MCP server handlers."""

    def __init__(self):
        self.tools = {t["name"]: t for t in TOOLS}

    def handle_request(self, request: dict) -> Optional[dict]:
        """Processes a single JSON-RPC request and returns response dict or None for notifications."""
        req_id = request.get("id")
        method = request.get("method")
        params = request.get("params")
        if not isinstance(params, dict):
            params = {}

        # Notifications have no id. Never write a response (MCP + JSON-RPC 2.0).
        if req_id is None:
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
        requested = params.get("protocolVersion")
        if requested in SUPPORTED_PROTOCOL_VERSIONS:
            protocol_version = requested
        else:
            protocol_version = LATEST_PROTOCOL_VERSION

        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": protocol_version,
                "capabilities": {
                    "tools": {"listChanged": False}
                },
                "serverInfo": {
                    "name": SERVER_NAME,
                    "title": "Agent Context Engine",
                    "version": SERVER_VERSION
                },
                "instructions": SERVER_INSTRUCTIONS
            }
        }

    def _handle_tool_call(self, req_id, params):
        tool_name = params.get("name")
        args = params.get("arguments")
        if not isinstance(args, dict):
            args = {}

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
                code, _banner = _capture_stdout(lambda: engine.cmd_map(ws))
                map_file = ws / ".agent-context.json"
                if code != 0:
                    return _tool_text(req_id, f"ctx map failed for {ws}", is_error=True)
                if map_file.is_file():
                    with open(map_file, "r", encoding="utf-8") as f:
                        return _tool_text(req_id, f.read())
                return _tool_text(req_id, json.dumps({"error": "Failed to generate context map"}), is_error=True)

            elif tool_name == "ctx_query_symbol":
                symbol = args.get("symbol", "")
                if not str(symbol).strip():
                    return {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "error": {"code": -32602, "message": "symbol is required"}
                    }
                ws = Path(args.get("workspace_path") or os.getcwd())
                _code, text = _capture_stdout(lambda: engine.cmd_query(ws, str(symbol)))
                return _tool_text(req_id, text, is_error=_code not in (0, None))

            elif tool_name == "ctx_slice":
                raw_path = args.get("file_path")
                if not raw_path:
                    return {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "error": {"code": -32602, "message": "file_path is required"}
                    }
                file_path = Path(raw_path)
                start = _as_int(args.get("start_line"), 1)
                end = _as_int(args.get("end_line"), 1)
                code, text = _capture_stdout(lambda: engine.cmd_slice(file_path, start, end))
                return _tool_text(req_id, text, is_error=code != 0)

            elif tool_name == "ctx_check":
                ws = Path(args.get("workspace_path") or os.getcwd())
                check_all = _as_bool(args.get("check_all"), False)
                exit_code, text = _capture_stdout(lambda: engine.cmd_check(ws, check_all=check_all))
                return _tool_text(req_id, text, is_error=exit_code != 0)

            elif tool_name == "ctx_get_graph":
                ws = Path(args.get("workspace_path") or os.getcwd())
                context_file = ws / ".agent-context.json"
                if not context_file.is_file():
                    code, _banner = _capture_stdout(lambda: engine.cmd_map(ws))
                    if code != 0:
                        return _tool_text(req_id, f"ctx map failed for {ws}", is_error=True)
                if context_file.is_file():
                    with open(context_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    return _tool_text(req_id, json.dumps(data.get("graph", {}), indent=2))
                return _tool_text(
                    req_id,
                    json.dumps({"error": "Failed to generate graph metadata"}),
                    is_error=True,
                )

            return _tool_text(req_id, f"Unhandled tool: {tool_name}", is_error=True)

        except Exception as e:
            return _tool_text(req_id, f"Execution error: {e}", is_error=True)


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

    def _load_json_file(file_path: Path):
        """Load JSON/JSONC. Returns {} for missing/empty, None if an existing file is invalid."""
        if not file_path.is_file() or file_path.stat().st_size == 0:
            return {}
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = _clean_json_str(f.read())
                if not content.strip():
                    return {}
                data = json.loads(content)
                return data if isinstance(data, dict) else None
        except Exception:
            return None

    def _write_json_file(file_path: Path, data: dict):
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _configure_mcp_servers(file_path: Path, require_parent: bool = False) -> dict:
        if require_parent and not file_path.exists() and not file_path.parent.exists():
            return {"path": str(file_path), "status": "skipped (not installed)"}
        data = _load_json_file(file_path)
        if data is None:
            return {"path": str(file_path), "status": "skipped (invalid existing config)"}
        if "mcpServers" not in data or not isinstance(data["mcpServers"], dict):
            data["mcpServers"] = {}
        data["mcpServers"]["agent-context-engine"] = mcp_def_standard
        _write_json_file(file_path, data)
        return {"path": str(file_path), "status": "configured"}

    mcp_def_standard = {
        "command": sys.executable,
        "args": ["-u", str(server_target)]
    }

    # 1. Antigravity
    gemini_mcp = Path.home() / ".gemini" / "config" / "mcp_config.json"
    results["antigravity"] = _configure_mcp_servers(gemini_mcp)

    # 2. Claude Desktop
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming"))
        claude_path = Path(appdata) / "Claude" / "claude_desktop_config.json"
    elif sys.platform == "darwin":
        claude_path = Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
    else:
        claude_path = Path.home() / ".config" / "Claude" / "claude_desktop_config.json"

    results["claude"] = _configure_mcp_servers(claude_path, require_parent=True)

    # 3. Cursor
    cursor_mcp = Path.home() / ".cursor" / "mcp.json"
    results["cursor"] = _configure_mcp_servers(cursor_mcp)

    # 4. OpenCode
    opencode_dir = Path.home() / ".config" / "opencode"
    opencode_file = opencode_dir / "opencode.jsonc"
    if not opencode_file.exists() and (opencode_dir / "opencode.json").exists():
        opencode_file = opencode_dir / "opencode.json"

    if opencode_dir.exists():
        data = _load_json_file(opencode_file)
        if data is None:
            results["opencode"] = {"path": str(opencode_file), "status": "skipped (invalid existing config)"}
        else:
            if "mcp" not in data or not isinstance(data["mcp"], dict):
                data["mcp"] = {}
            data["mcp"]["agent-context-engine"] = {
                "type": "local",
                "command": [sys.executable, "-u", str(server_target)],
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
    """Runs the MCP server over standard input/output.

    MCP stdio (2025-06-18): stdout is reserved for newline-delimited JSON-RPC.
    Diagnostic / CLI banners MUST go to stderr. The server MUST NOT write
    anything else to stdout.
    """
    server = MCPServer()

    stdin = sys.stdin
    rpc_out = sys.stdout
    try:
        if hasattr(stdin, "reconfigure"):
            stdin.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(rpc_out, "reconfigure"):
            rpc_out.reconfigure(
                encoding="utf-8",
                errors="replace",
                newline="\n",
                line_buffering=True,
                write_through=True,
            )
    except Exception:
        pass

    # Isolate the RPC channel: print() and engine CLI banners cannot corrupt it.
    sys.stdout = sys.stderr

    while True:
        try:
            line = stdin.readline()
            if not line:
                break
            line = line.strip()
            if not line:
                continue

            try:
                request = json.loads(line)
            except json.JSONDecodeError as e:
                err_resp = {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": -32700, "message": f"Parse error: {e}"}
                }
                rpc_out.write(json.dumps(err_resp, separators=(",", ":")) + "\n")
                rpc_out.flush()
                continue

            if not isinstance(request, dict):
                err_resp = {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": -32600, "message": "Invalid Request"}
                }
                rpc_out.write(json.dumps(err_resp, separators=(",", ":")) + "\n")
                rpc_out.flush()
                continue

            response = server.handle_request(request)
            if response is not None:
                rpc_out.write(json.dumps(response, separators=(",", ":"), ensure_ascii=False) + "\n")
                rpc_out.flush()
        except (KeyboardInterrupt, SystemExit):
            break
        except Exception as e:
            print(f"[ctx mcp] handler error: {e}", file=sys.stderr)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in ("--install", "install", "-i"):
        sys.exit(cmd_install_mcp())
    else:
        run_stdio_server()

