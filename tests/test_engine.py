#!/usr/bin/env python3
"""
Automated Test Suite for Agent Context Engine (ctx)
Validates AST parsing, regex extraction, command execution, and syntax checking.
Zero external dependencies -- standard Python unittest.
"""

import json
import os
import shutil
import sys
import tempfile
import unittest
from io import StringIO
from pathlib import Path

# Add src to python path
SRC_DIR = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC_DIR))

import engine


class TestPythonASTParser(unittest.TestCase):
    def test_class_and_methods(self):
        code = """
class BaseService:
    pass

class UserService(BaseService):
    def __init__(self, db_url):
        self.db = db_url

    async def get_user(self, user_id):
        return {"id": user_id}
"""
        parsed = engine.parse_python_file(code)
        self.assertEqual(len(parsed["classes"]), 2)
        user_svc = next(c for c in parsed["classes"] if c["name"] == "UserService")
        self.assertEqual(user_svc["bases"], ["BaseService"])
        self.assertIn("__init__", user_svc["methods"])
        self.assertIn("get_user", user_svc["methods"])

    def test_functions_and_constants(self):
        code = """
MAX_RETRIES = 5
API_URL = "https://example.com"
temp_var = 123

def calculate_hash(data, salt="default"):
    pass

async def send_event(event_name):
    pass
"""
        parsed = engine.parse_python_file(code)
        self.assertIn("MAX_RETRIES", parsed["constants"])
        self.assertIn("API_URL", parsed["constants"])
        self.assertNotIn("temp_var", parsed["constants"])
        
        fn_names = [f["name"] for f in parsed["functions"]]
        self.assertIn("calculate_hash", fn_names)
        self.assertIn("send_event", fn_names)
        
        async_fn = next(f for f in parsed["functions"] if f["name"] == "send_event")
        self.assertTrue(async_fn["async"])

    def test_cross_boundary_hooks(self):
        code = """
import subprocess
import requests

def call_remote():
    requests.get("https://example.com")
    subprocess.run(["ls", "-la"])
"""
        parsed = engine.parse_python_file(code)
        self.assertTrue(any("requests" in h for h in parsed["hooks"]))
        self.assertTrue(any("subprocess" in h for h in parsed["hooks"]))

    def test_syntax_error_handled(self):
        code = "def broken(:"
        parsed = engine.parse_python_file(code)
        self.assertIn("error", parsed)


class TestJavaScriptParser(unittest.TestCase):
    def test_js_classes_and_functions(self):
        code = """
class Router extends BaseRouter {
    constructor() {}
}

export function handleRequest(req, res) {
    return true;
}

const formatData = async (data, format) => {
    return data;
};
"""
        parsed = engine.parse_js_ts_file(code)
        self.assertEqual(len(parsed["classes"]), 1)
        self.assertEqual(parsed["classes"][0]["name"], "Router")
        self.assertEqual(parsed["classes"][0]["extends"], "BaseRouter")

        fn_names = [f["name"] for f in parsed["functions"]]
        self.assertIn("handleRequest", fn_names)
        self.assertIn("formatData", fn_names)

    def test_js_hooks(self):
        code = """
async function sync() {
    const r = await fetch('/api');
    UrlFetchApp.fetch('https://google.com');
    const cp = require('child_process');
}
"""
        parsed = engine.parse_js_ts_file(code)
        self.assertTrue(any("fetch" in h for h in parsed["hooks"]))
        self.assertTrue(any("UrlFetchApp" in h for h in parsed["hooks"]))
        self.assertTrue(any("process" in h or "shell" in h for h in parsed["hooks"]))


class TestPowerShellParser(unittest.TestCase):
    def test_ps1_functions_and_hooks(self):
        code = """
function Start-Deployment {
    param([string]$EnvName)
    Start-Process 'powershell.exe'
}

filter Filter-ActiveJob {
    Invoke-RestMethod -Uri 'https://api.internal/jobs'
}
"""
        parsed = engine.parse_powershell_file(code)
        fn_names = [f["name"] for f in parsed["functions"]]
        self.assertIn("Start-Deployment", fn_names)
        self.assertIn("Filter-ActiveJob", fn_names)
        self.assertTrue(any("Invoke-RestMethod" in h for h in parsed["hooks"]))
        self.assertTrue(any("Start-Process" in h for h in parsed["hooks"]))


class TestVBScriptParser(unittest.TestCase):
    def test_vbscript_sub_and_function(self):
        code = """
Class ServiceLogger
    Sub Log(msg)
    End Sub
End Class

Function PostPayload(url, payload)
    Set shell = WScript.CreateObject("WScript.Shell")
    Set http = CreateObject("MSXML2.ServerXMLHTTP")
End Function
"""
        parsed = engine.parse_vbscript_file(code)
        self.assertEqual(len(parsed["classes"]), 1)
        self.assertEqual(parsed["classes"][0]["name"], "ServiceLogger")
        
        fn_names = [f["name"] for f in parsed["functions"]]
        self.assertIn("Log", fn_names)
        self.assertIn("PostPayload", fn_names)
        self.assertIn("WScript.Shell", parsed["hooks"])
        self.assertIn("WinHttp/MSXML", parsed["hooks"])


class TestEngineCommands(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp())
        
        # Create test project files
        (self.test_dir / "main.py").write_text(
            "import os\n\ndef main():\n    print('hello')\n",
            encoding="utf-8"
        )
        (self.test_dir / "util.js").write_text(
            "function compute(x, y) { return x + y; }\n",
            encoding="utf-8"
        )
        (self.test_dir / "service.py").write_text(
            "class AuthService:\n    def verify_token(self, token):\n        return True\n",
            encoding="utf-8"
        )

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def _stdout(self, fn):
        buf = StringIO()
        old = sys.stdout
        sys.stdout = buf
        try:
            ret = fn()
        finally:
            sys.stdout = old
        return ret, engine.strip_ansi(buf.getvalue())

    def test_cmd_map(self):
        ret = engine.cmd_map(self.test_dir)
        self.assertEqual(ret, 0)
        
        context_file = self.test_dir / ".agent-context.json"
        self.assertTrue(context_file.is_file())
        
        with open(context_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        self.assertIn("meta", data)
        self.assertIn("files", data)
        self.assertEqual(data["meta"]["total_files"], 3)
        self.assertIn("main.py", data["files"])
        self.assertIn("util.js", data["files"])
        self.assertNotIn(".agent-context.json", data["files"])

    def test_cmd_map_skips_generated_index(self):
        engine.cmd_map(self.test_dir)
        engine.cmd_map(self.test_dir)
        data = json.loads((self.test_dir / ".agent-context.json").read_text(encoding="utf-8"))
        self.assertNotIn(".agent-context.json", data["files"])

    def test_cmd_map_truncates(self):
        old = engine.MAP_MAX_FILES
        engine.MAP_MAX_FILES = 1
        try:
            ret = engine.cmd_map(self.test_dir)
            self.assertEqual(ret, 0)
            data = json.loads((self.test_dir / ".agent-context.json").read_text(encoding="utf-8"))
            self.assertTrue(data["meta"].get("truncated"))
            self.assertEqual(data["meta"]["total_files"], 1)
        finally:
            engine.MAP_MAX_FILES = old

    def test_cmd_map_refuses_home_and_root(self):
        self.assertEqual(engine.cmd_map(Path.home()), 1)
        self.assertEqual(engine.cmd_map(Path(Path.home().anchor)), 1)

    def test_cmd_slice(self):
        file_path = self.test_dir / "main.py"
        ret, out = self._stdout(lambda: engine.cmd_slice(file_path, 1, 3))
        self.assertEqual(ret, 0)
        self.assertIn("def main():", out)

    def test_cmd_slice_clamps_and_swaps(self):
        big = self.test_dir / "big.py"
        big.write_text("\n".join(f"line_{i} = {i}" for i in range(1, 201)), encoding="utf-8")
        ret, out = self._stdout(lambda: engine.cmd_slice(big, 1, 500))
        self.assertEqual(ret, 0)
        self.assertIn("line_1 =", out)
        self.assertIn("line_150 =", out)
        self.assertNotIn("line_151 =", out)
        ret, out = self._stdout(lambda: engine.cmd_slice(big, 5, 2))
        self.assertEqual(ret, 0)
        self.assertIn("line_2 =", out)
        self.assertIn("line_5 =", out)

    def test_cmd_query(self):
        engine.cmd_map(self.test_dir)
        ret, out = self._stdout(lambda: engine.cmd_query(self.test_dir, "compute"))
        self.assertEqual(ret, 0)
        self.assertIn("compute", out)

    def test_cmd_query_finds_methods(self):
        engine.cmd_map(self.test_dir)
        ret, out = self._stdout(lambda: engine.cmd_query(self.test_dir, "verify_token"))
        self.assertEqual(ret, 0)
        self.assertIn("AuthService.verify_token", out)

    def test_cmd_check_clean(self):
        ret = engine.cmd_check(self.test_dir, check_all=True)
        self.assertEqual(ret, 0)

    def test_cmd_check_fail(self):
        (self.test_dir / "broken.py").write_text("def broken(:", encoding="utf-8")
        ret = engine.cmd_check(self.test_dir, check_all=True)
        self.assertEqual(ret, 1)

    def test_cmd_check_skip_is_not_pass(self):
        (self.test_dir / "types.ts").write_text("export type Id = string;\n", encoding="utf-8")
        ret, out = self._stdout(lambda: engine.cmd_check(self.test_dir, check_all=True))
        self.assertEqual(ret, 0)
        self.assertIn("[SKIP]", out)
        self.assertIn("types.ts", out)
        self.assertNotIn("[PASS] types.ts", out)

    def test_cmd_graph(self):
        engine.cmd_map(self.test_dir)
        ret = engine.cmd_graph(self.test_dir)
        self.assertEqual(ret, 0)


class TestPolyglotParsers(unittest.TestCase):
    def test_kotlin_parser(self):
        code = """
import okhttp3.OkHttpClient

data class UserDto(val id: String)

class UserService {
    fun fetchUser(id: String): UserDto {
        val client = OkHttpClient()
        return UserDto(id)
    }
}
"""
        parsed = engine.parse_kotlin_file(code)
        cls_names = [c["name"] for c in parsed["classes"]]
        self.assertIn("UserDto", cls_names)
        self.assertIn("UserService", cls_names)
        self.assertTrue(any(f["name"] == "fetchUser" for f in parsed["functions"]))
        self.assertTrue(any("OkHttpClient" in h for h in parsed["hooks"]))
        self.assertIn("okhttp3.OkHttpClient", parsed["imports"])

    def test_swift_parser(self):
        code = """
import Foundation

class NetworkManager {
    func request(url: URL) {
        URLSession.shared.dataTask(with: url)
    }
}
"""
        parsed = engine.parse_swift_file(code)
        self.assertTrue(any(c["name"] == "NetworkManager" for c in parsed["classes"]))
        self.assertTrue(any(f["name"] == "request" for f in parsed["functions"]))
        self.assertTrue(any("URLSession" in h for h in parsed["hooks"]))

    def test_c_cpp_parser(self):
        code = """
#include <iostream>
#include "curl/curl.h"

class HttpClient {
public:
    int get(const char* url) {
        CURL* curl = curl_easy_init();
        system("echo ping");
        return 0;
    }
};
"""
        parsed = engine.parse_c_cpp_file(code)
        self.assertTrue(any(c["name"] == "HttpClient" for c in parsed["classes"]))
        self.assertTrue(any(f["name"] == "get" for f in parsed["functions"]))
        self.assertTrue(any("curl_easy_init" in h or "system" in h for h in parsed["hooks"]))
        self.assertIn("iostream", parsed["imports"])

    def test_ruby_parser(self):
        code = """
require 'net/http'

module Payments
    class Gateway
        def process_charge(amount)
            Net::HTTP.get_response(URI("https://api.stripe.com"))
        end
    end
end
"""
        parsed = engine.parse_ruby_file(code)
        self.assertTrue(any("Gateway" in c["name"] for c in parsed["classes"]))
        self.assertTrue(any(f["name"] == "process_charge" for f in parsed["functions"]))
        self.assertIn("network/shell", parsed["hooks"])
        self.assertIn("net/http", parsed["imports"])

    def test_php_parser(self):
        code = """
<?php
namespace App;

class ApiClient {
    public function executeCall($endpoint) {
        $ch = curl_init();
        shell_exec("uptime");
    }
}
"""
        parsed = engine.parse_php_file(code)
        self.assertTrue(any(c["name"] == "ApiClient" for c in parsed["classes"]))
        self.assertTrue(any(f["name"] == "executeCall" for f in parsed["functions"]))
        self.assertIn("network/shell", parsed["hooks"])

    def test_scala_parser(self):
        code = """
import scala.sys.process._

case class Metric(name: String, value: Double)

object Reporter {
    def sendMetric(m: Metric): Unit = {
        Process("curl http://metrics").!
    }
}
"""
        parsed = engine.parse_scala_file(code)
        cls_names = [c["name"] for c in parsed["classes"]]
        self.assertIn("Metric", cls_names)
        self.assertIn("Reporter", cls_names)
        self.assertTrue(any(f["name"] == "sendMetric" for f in parsed["functions"]))
        self.assertIn("process/http", parsed["hooks"])

    def test_elixir_parser(self):
        code = """
defmodule Core.Worker do
    import System

    def start_job(job_id) do
        System.cmd("task", [job_id])
    end
end
"""
        parsed = engine.parse_elixir_file(code)
        self.assertTrue(any("Core.Worker" in c["name"] for c in parsed["classes"]))
        self.assertTrue(any(f["name"] == "start_job" for f in parsed["functions"]))
        self.assertIn("system/http", parsed["hooks"])
        self.assertIn("System", parsed["imports"])


class TestDependencyGraph(unittest.TestCase):
    def test_graph_resolution_and_topological_order(self):
        files = {
            "src/utils.py": {"imports": []},
            "src/models.py": {"imports": ["utils"]},
            "src/app.py": {"imports": ["models", "utils"]}
        }
        graph = engine.build_dependency_graph(files)
        self.assertEqual(graph["total_nodes"], 3)
        self.assertEqual(graph["total_edges"], 3)
        self.assertEqual(len(graph["circular_dependencies"]), 0)
        
        order = graph["topological_order"]
        self.assertLess(order.index("src/utils.py"), order.index("src/models.py"))
        self.assertLess(order.index("src/models.py"), order.index("src/app.py"))
        self.assertIn("src/app.py", graph["entry_points"])

    def test_cycle_detection(self):
        files = {
            "a.py": {"imports": ["b"]},
            "b.py": {"imports": ["a"]}
        }
        graph = engine.build_dependency_graph(files)
        self.assertGreater(len(graph["circular_dependencies"]), 0)


class TestGenericParsers(unittest.TestCase):
    def test_go_parser(self):
        code = """
package main
import "net/http"
type Server struct {}
func (s *Server) Listen(addr string) error { return nil }
func main() {}
"""
        parsed = engine.parse_generic_file(code, "go")
        names = [f["name"] for f in parsed["functions"]]
        self.assertIn("Listen", names)
        self.assertIn("main", names)
        self.assertEqual(parsed["classes"][0]["name"], "Server")

    def test_strip_ansi(self):
        self.assertEqual(engine.strip_ansi("\033[1;32m[ctx]\033[0m hi"), "[ctx] hi")


if __name__ == "__main__":
    unittest.main()
