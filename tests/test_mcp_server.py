#!/usr/bin/env python3
"""
Automated Test Suite for Agent Context Engine - Model Context Protocol (MCP) Server
Validates JSON-RPC 2.0 handshake, tool enumeration, tool invocation, and stdio execution.
Zero external dependencies.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

# Add src to python path
SRC_DIR = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC_DIR))

import mcp_server


class TestMCPServerUnit(unittest.TestCase):
    """Direct programmatic tests on the MCPServer class."""

    def setUp(self):
        self.server = mcp_server.MCPServer()
        self.test_dir = Path(tempfile.mkdtemp())
        
        # Setup sample files
        (self.test_dir / "service.py").write_text(
            "import os\n\nclass AuthService:\n    def verify_token(self, token):\n        return True\n",
            encoding="utf-8"
        )

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_initialize(self):
        req = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test-client", "version": "1.0"}
            }
        }
        res = self.server.handle_request(req)
        self.assertEqual(res["jsonrpc"], "2.0")
        self.assertEqual(res["id"], 1)
        self.assertEqual(res["result"]["protocolVersion"], "2024-11-05")
        self.assertEqual(res["result"]["serverInfo"]["name"], "agent-context-engine")
        self.assertIn("tools", res["result"]["capabilities"])

    def test_ping(self):
        req = {"jsonrpc": "2.0", "id": 2, "method": "ping", "params": {}}
        res = self.server.handle_request(req)
        self.assertEqual(res["result"], {})

    def test_tools_list(self):
        req = {"jsonrpc": "2.0", "id": 3, "method": "tools/list", "params": {}}
        res = self.server.handle_request(req)
        tools = res["result"]["tools"]
        tool_names = [t["name"] for t in tools]
        self.assertIn("ctx_get_map", tool_names)
        self.assertIn("ctx_query_symbol", tool_names)
        self.assertIn("ctx_slice", tool_names)
        self.assertIn("ctx_check", tool_names)

    def test_call_ctx_get_map(self):
        req = {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": "ctx_get_map",
                "arguments": {"workspace_path": str(self.test_dir)}
            }
        }
        res = self.server.handle_request(req)
        self.assertNotIn("error", res)
        content = res["result"]["content"][0]["text"]
        data = json.loads(content)
        self.assertIn("files", data)
        self.assertIn("service.py", data["files"])

    def test_call_ctx_query_symbol(self):
        # Map first
        self.server.handle_request({
            "jsonrpc": "2.0",
            "id": 5,
            "method": "tools/call",
            "params": {"name": "ctx_get_map", "arguments": {"workspace_path": str(self.test_dir)}}
        })

        req = {
            "jsonrpc": "2.0",
            "id": 6,
            "method": "tools/call",
            "params": {
                "name": "ctx_query_symbol",
                "arguments": {"symbol": "AuthService", "workspace_path": str(self.test_dir)}
            }
        }
        res = self.server.handle_request(req)
        text = res["result"]["content"][0]["text"]
        self.assertIn("AuthService", text)

    def test_call_ctx_slice(self):
        req = {
            "jsonrpc": "2.0",
            "id": 7,
            "method": "tools/call",
            "params": {
                "name": "ctx_slice",
                "arguments": {
                    "file_path": str(self.test_dir / "service.py"),
                    "start_line": 3,
                    "end_line": 4
                }
            }
        }
        res = self.server.handle_request(req)
        text = res["result"]["content"][0]["text"]
        self.assertIn("class AuthService:", text)

    def test_call_ctx_check(self):
        req = {
            "jsonrpc": "2.0",
            "id": 8,
            "method": "tools/call",
            "params": {
                "name": "ctx_check",
                "arguments": {"workspace_path": str(self.test_dir), "check_all": True}
            }
        }
        res = self.server.handle_request(req)
        self.assertFalse(res["result"].get("isError", False))
        text = res["result"]["content"][0]["text"]
        self.assertIn("PASS", text)

    def test_call_ctx_get_graph(self):
        req = {
            "jsonrpc": "2.0",
            "id": 9,
            "method": "tools/call",
            "params": {
                "name": "ctx_get_graph",
                "arguments": {"workspace_path": str(self.test_dir)}
            }
        }
        res = self.server.handle_request(req)
        self.assertNotIn("error", res)
        text = res["result"]["content"][0]["text"]
        data = json.loads(text)
        self.assertIn("total_nodes", data)
        self.assertIn("entry_points", data)

    def test_unknown_method(self):
        req = {"jsonrpc": "2.0", "id": 9, "method": "invalid/method", "params": {}}
        res = self.server.handle_request(req)
        self.assertIn("error", res)
        self.assertEqual(res["error"]["code"], -32601)

    def test_unknown_tool(self):
        req = {
            "jsonrpc": "2.0",
            "id": 10,
            "method": "tools/call",
            "params": {"name": "non_existent_tool", "arguments": {}}
        }
        res = self.server.handle_request(req)
        self.assertIn("error", res)
        self.assertEqual(res["error"]["code"], -32602)


class TestMCPServerStdio(unittest.TestCase):
    """End-to-end integration test running mcp_server.py via stdio subprocess."""

    def test_stdio_handshake(self):
        server_path = SRC_DIR / "mcp_server.py"
        proc = subprocess.Popen(
            [sys.executable, str(server_path)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        init_req = json.dumps({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test-client", "version": "1.0"}
            }
        }) + "\n"

        stdout, _ = proc.communicate(input=init_req, timeout=5)
        response = json.loads(stdout.strip())
        self.assertEqual(response["jsonrpc"], "2.0")
        self.assertEqual(response["id"], 1)
        self.assertEqual(response["result"]["serverInfo"]["name"], "agent-context-engine")


class TestMCPEditorConfiguration(unittest.TestCase):
    """Verifies cross-editor MCP configuration format and non-destructive merging."""

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.mock_gemini = self.temp_dir / ".gemini" / "config" / "mcp_config.json"
        self.mock_claude = self.temp_dir / "Claude" / "claude_desktop_config.json"
        self.mock_cursor = self.temp_dir / ".cursor" / "mcp.json"
        self.mock_opencode = self.temp_dir / ".config" / "opencode" / "opencode.jsonc"

        # Pre-seed existing configurations with user data
        self.mock_claude.parent.mkdir(parents=True, exist_ok=True)
        self.mock_claude.write_text(
            json.dumps({"preferences": {"keepAwake": True}, "customUserDir": "C:\\MyProjects"}),
            encoding="utf-8"
        )

        self.mock_opencode.parent.mkdir(parents=True, exist_ok=True)
        self.mock_opencode.write_text(
            json.dumps({"$schema": "https://opencode.ai/config.json", "instructions": ["AGENTS.md"]}),
            encoding="utf-8"
        )

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_configure_editors_idempotent(self):
        import unittest.mock as mock

        with mock.patch("pathlib.Path.home", return_value=self.temp_dir), \
             mock.patch.dict(os.environ, {"APPDATA": str(self.temp_dir)}):

            results = mcp_server.configure_editors(engine_dir=self.temp_dir)

            # 1. Antigravity configured
            self.assertTrue(self.mock_gemini.is_file())
            gemini_data = json.loads(self.mock_gemini.read_text(encoding="utf-8"))
            self.assertIn("agent-context-engine", gemini_data["mcpServers"])
            self.assertEqual(gemini_data["mcpServers"]["agent-context-engine"]["command"], "python")

            # 2. Claude Desktop configured & preserved existing keys
            self.assertTrue(self.mock_claude.is_file())
            claude_data = json.loads(self.mock_claude.read_text(encoding="utf-8"))
            self.assertIn("agent-context-engine", claude_data["mcpServers"])
            self.assertEqual(claude_data["preferences"]["keepAwake"], True)
            self.assertEqual(claude_data["customUserDir"], "C:\\MyProjects")

            # 3. Cursor configured
            self.assertTrue(self.mock_cursor.is_file())
            cursor_data = json.loads(self.mock_cursor.read_text(encoding="utf-8"))
            self.assertIn("agent-context-engine", cursor_data["mcpServers"])

            # 4. OpenCode configured with official schema ("mcp" key with type: local)
            self.assertTrue(self.mock_opencode.is_file())
            opencode_data = json.loads(self.mock_opencode.read_text(encoding="utf-8"))
            self.assertIn("agent-context-engine", opencode_data["mcp"])
            self.assertEqual(opencode_data["mcp"]["agent-context-engine"]["type"], "local")
            self.assertIn("python", opencode_data["mcp"]["agent-context-engine"]["command"])
            self.assertEqual(opencode_data["instructions"], ["AGENTS.md"])


if __name__ == "__main__":
    unittest.main()

