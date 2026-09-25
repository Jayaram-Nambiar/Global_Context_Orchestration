#!/usr/bin/env python3
"""
Agent Context Engine (ctx)
Global Token Optimization & Pre-Completion Verification Utility
Zero external dependencies -- pure Python stdlib & native runtime execution.
"""

import argparse
import ast
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

VERSION = "1.3.0"
IGNORE_DIRS = {
    "node_modules", ".git", "__pycache__", "venv", ".venv", "env", ".env",
    "dist", "build", "target", "bin", "obj", ".next", ".nuxt", ".turbo",
    ".cursor", ".vscode", ".gemini", ".antigravity", ".agent-context-engine",
    "coverage", ".pytest_cache", ".mypy_cache", "AppData", "Cache", "Logs"
}

IGNORE_EXTENSIONS = {
    ".exe", ".dll", ".so", ".dylib", ".bin", ".iso", ".zip", ".tar", ".gz",
    ".7z", ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg", ".webp", ".mp4",
    ".mp3", ".wav", ".pdf", ".woff", ".woff2", ".ttf", ".eot", ".lock",
    ".min.js", ".min.css", ".bundle.js", ".map"
}

LANGUAGE_MAP = {
    ".py": "python",
    ".js": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".gs": "google-apps-script",
    ".vue": "vue",
    ".svelte": "svelte",
    ".ps1": "powershell",
    ".psm1": "powershell",
    ".psd1": "powershell",
    ".vbs": "vbscript",
    ".vbe": "vbscript",
    ".wsf": "vbscript",
    ".go": "go",
    ".rs": "rust",
    ".cs": "csharp",
    ".java": "java",
    ".json": "json",
    ".kt": "kotlin",
    ".kts": "kotlin",
    ".swift": "swift",
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".hpp": "cpp",
    ".cc": "cpp",
    ".cxx": "cpp",
    ".rb": "ruby",
    ".rake": "ruby",
    ".php": "php",
    ".scala": "scala",
    ".sc": "scala",
    ".ex": "elixir",
    ".exs": "elixir",
    ".j2": "jinja",
    ".jinja": "jinja",
    ".jinja2": "jinja",
    ".njk": "jinja",
    ".liquid": "jinja",
    ".mmd": "mermaid",
    ".mermaid": "mermaid",
    ".md": "markdown",
    ".markdown": "markdown",
    ".sh": "shell",
    ".bash": "shell",
    ".zsh": "shell",
    ".ksh": "shell",
    ".sql": "sql",
    ".tf": "terraform",
    ".lua": "lua",
    ".dart": "dart",
    ".graphql": "graphql",
    ".gql": "graphql",
    ".proto": "proto",
    ".sol": "solidity",
    ".r": "r",
    ".mk": "make",
}

_GENERIC_LANGS = (
    "go", "rust", "csharp", "java", "lua", "dart", "graphql", "proto", "solidity", "r",
)


def language_for_path(path: Path):
    """Map a file path to a LANGUAGE_MAP language, including extensionless names."""
    name = path.name.lower()
    if name in ("dockerfile", "containerfile") or name.startswith("dockerfile."):
        return "dockerfile"
    if name in ("makefile", "gnumakefile"):
        return "make"
    return LANGUAGE_MAP.get(path.suffix.lower())


def _is_checkable_path(path: Path):
    """True when map would index the file AND check should mention it.

    Markdown is mapped only when mermaid fences exist; check has no MD parser
    and would otherwise SKIP every README on every run.
    """
    lang = language_for_path(path)
    return lang is not None and lang != "markdown"

SLICE_MAX_LINES = 150
MAP_MAX_FILES = 8000
CHECK_TIMEOUT_SEC = 20
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def strip_ansi(text: str) -> str:
    """Remove ANSI color sequences from captured CLI output."""
    return _ANSI_RE.sub("", text or "")


def relposix(path: Path, root: Path) -> str:
    """Python 3.8-safe relative POSIX path; falls back to the absolute string."""
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


def is_unsafe_workspace(path: Path) -> bool:
    """True for filesystem roots and the user home directory (accidental full-disk scans)."""
    try:
        resolved = path.resolve()
    except OSError:
        return True
    if resolved.parent == resolved:
        return True
    try:
        if resolved == Path.home().resolve():
            return True
    except OSError:
        return False
    return False


def _run_checker(cmd):
    """Run a syntax checker with a hard timeout. Returns (returncode, error_text)."""
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=CHECK_TIMEOUT_SEC)
        return res.returncode, (res.stderr or res.stdout).strip()
    except subprocess.TimeoutExpired:
        return 1, f"Timed out after {CHECK_TIMEOUT_SEC}s: {' '.join(str(c) for c in cmd[:4])}"
    except OSError as e:
        return 1, str(e)


# --- Structural Pattern Extractors ---

def parse_python_file(content: str):
    """AST-based symbol and cross-boundary hook extraction for Python."""
    classes = []
    functions = []
    hooks = set()
    constants = []
    imports = set()

    try:
        tree = ast.parse(content)
    except Exception as e:
        return {"error": f"SyntaxError: {e}", "classes": [], "functions": [], "hooks": [], "constants": [], "imports": []}

    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            methods = [
                n.name for n in node.body
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
            ]
            bases = []
            for b in node.bases:
                if isinstance(b, ast.Name):
                    bases.append(b.id)
                elif isinstance(b, ast.Attribute):
                    bases.append(f"{ast.unparse(b.value)}.{b.attr}" if hasattr(ast, "unparse") else b.attr)
            classes.append({
                "name": node.name,
                "line": node.lineno,
                "bases": bases,
                "methods": methods
            })
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            args = [a.arg for a in node.args.args]
            functions.append({
                "name": node.name,
                "line": node.lineno,
                "args": args,
                "async": isinstance(node, ast.AsyncFunctionDef)
            })
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id.isupper():
                    constants.append(target.id)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.add(node.module)

    # Detect cross-boundary hooks across all AST calls
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func_name = ""
            if isinstance(node.func, ast.Name):
                func_name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                func_name = ast.unparse(node.func) if hasattr(ast, "unparse") else node.func.attr

            # Check for shell & network invocations
            if any(k in func_name for k in ["subprocess", "os.system", "os.popen", "os.spawn", "shutil"]):
                hooks.add(func_name)
            elif any(k in func_name for k in ["requests.", "urllib.", "httpx.", "aiohttp.", "socket."]):
                hooks.add(func_name)

    return {
        "classes": classes,
        "functions": functions,
        "constants": constants[:10],
        "hooks": sorted(list(hooks)),
        "imports": sorted(list(imports))
    }

def parse_js_ts_file(content: str):
    """Regex pattern extraction for JS/TS/AppsScript."""
    classes = []
    functions = []
    hooks = set()
    imports = set()

    lines = content.splitlines()
    for idx, line in enumerate(lines, start=1):
        sline = line.strip()
        if not sline or sline.startswith("//") or sline.startswith("/*") or sline.startswith("*"):
            continue

        # Class matching
        m_cls = re.search(r'(?:export\s+)?class\s+([a-zA-Z0-9_$]+)(?:\s+extends\s+([a-zA-Z0-9_$]+))?', sline)
        if m_cls:
            classes.append({
                "name": m_cls.group(1),
                "line": idx,
                "extends": m_cls.group(2) if m_cls.group(2) else None
            })
            continue

        # Function matching: function foo(a, b)
        m_fn = re.search(r'(?:export\s+)?(?:async\s+)?function\s+([a-zA-Z0-9_$]+)\s*\(([^)]*)\)', sline)
        if m_fn:
            args = [a.strip().split(":")[0].strip() for a in m_fn.group(2).split(",") if a.strip()]
            functions.append({
                "name": m_fn.group(1),
                "line": idx,
                "args": args
            })
            continue

        # Arrow function: const foo = async (a, b) => or let foo = (a) =>
        m_arrow = re.search(r'(?:export\s+)?(?:const|let|var)\s+([a-zA-Z0-9_$]+)\s*=\s*(?:async\s*)?(?:\(([^)]*)\)|([a-zA-Z0-9_$]+))\s*=>', sline)
        if m_arrow:
            raw_args = m_arrow.group(2) or m_arrow.group(3) or ""
            args = [a.strip().split(":")[0].strip() for a in raw_args.split(",") if a.strip()]
            functions.append({
                "name": m_arrow.group(1),
                "line": idx,
                "args": args
            })
            continue

        # Imports matching
        m_imp = re.search(r'(?:import\s+(?:.*?\s+from\s+)?|require\()[\'"]([^\'"]+)[\'"]', sline)
        if m_imp:
            imports.add(m_imp.group(1))

        # Cross-boundary hooks detection
        if re.search(r'\b(?:fetch|axios\.(?:get|post|put|delete)|UrlFetchApp\.fetch|XMLHttpRequest|\$\.ajax)\b', sline):
            m = re.findall(r'\b(?:fetch|axios\.[a-z]+|UrlFetchApp\.fetch|XMLHttpRequest)\b', sline)
            if m:
                hooks.add(m[0])
        for gas in re.findall(
            r'\b(?:UrlFetchApp|SpreadsheetApp|DocumentApp|GmailApp|DriveApp|'
            r'CalendarApp|FormApp|SlidesApp|ScriptApp|HtmlService|'
            r'CacheService|PropertiesService|Jdbc|CardService)\b',
            sline,
        ):
            hooks.add(gas)
        if "google.script.run" in sline:
            hooks.add("google.script.run")
        if re.search(r'\b(?:child_process|execSync|spawnSync|exec|spawn|Deno\.run)\b', sline):
            hooks.add("shell/process_invocation")

    return {
        "classes": classes,
        "functions": functions,
        "hooks": sorted(list(hooks)),
        "imports": sorted(list(imports))
    }

def parse_powershell_file(content: str):
    """Regex pattern extraction for PowerShell."""
    functions = []
    hooks = set()
    imports = set()

    lines = content.splitlines()
    for idx, line in enumerate(lines, start=1):
        sline = line.strip()
        if not sline or sline.startswith("#"):
            continue

        m_fn = re.search(r'^(?:function|filter)\s+([a-zA-Z0-9_\-]+)', sline, re.IGNORECASE)
        if m_fn:
            functions.append({
                "name": m_fn.group(1),
                "line": idx
            })

        m_imp = re.search(r'(?:Import-Module|\.\s+[\'"]?)([^\'"\r\n;]+)', sline, re.IGNORECASE)
        if m_imp:
            imports.add(m_imp.group(1).strip())

        # Cross-boundary hooks
        if re.search(r'\b(?:Invoke-RestMethod|Invoke-WebRequest|HttpClient|WebClient)\b', sline, re.IGNORECASE):
            m = re.findall(r'\b(?:Invoke-RestMethod|Invoke-WebRequest|HttpClient|WebClient)\b', sline, re.IGNORECASE)
            hooks.add(m[0])
        if re.search(r'\b(?:Start-Process|Invoke-Expression|cmd\.exe|powershell\.exe)\b', sline, re.IGNORECASE):
            m = re.findall(r'\b(?:Start-Process|Invoke-Expression)\b', sline, re.IGNORECASE)
            hooks.add(m[0] if m else "process_invocation")

    return {
        "classes": [],
        "functions": functions,
        "hooks": sorted(list(hooks)),
        "imports": sorted(list(imports))
    }

def parse_vbscript_file(content: str):
    """Regex pattern extraction for VBScript."""
    functions = []
    classes = []
    hooks = set()

    lines = content.splitlines()
    for idx, line in enumerate(lines, start=1):
        sline = line.strip()
        if not sline or sline.startswith("'") or sline.lower().startswith("rem"):
            continue

        m_fn = re.search(r'^(?:Sub|Function)\s+([a-zA-Z0-9_]+)\s*(?:\(([^)]*)\))?', sline, re.IGNORECASE)
        if m_fn:
            raw_args = m_fn.group(2) or ""
            args = [a.strip() for a in raw_args.split(",") if a.strip()]
            functions.append({
                "name": m_fn.group(1),
                "line": idx,
                "args": args
            })

        m_cls = re.search(r'^Class\s+([a-zA-Z0-9_]+)', sline, re.IGNORECASE)
        if m_cls:
            classes.append({
                "name": m_cls.group(1),
                "line": idx
            })

        if re.search(r'WScript\.CreateObject\(["\']WScript\.Shell["\']\)|\.Run\(|\.Exec\(', sline, re.IGNORECASE):
            hooks.add("WScript.Shell")
        if re.search(r'MSXML2\.ServerXMLHTTP|MSXML2\.XMLHTTP|WinHttp\.WinHttpRequest', sline, re.IGNORECASE):
            hooks.add("WinHttp/MSXML")

    return {
        "classes": classes,
        "functions": functions,
        "hooks": sorted(list(hooks)),
        "imports": []
    }

def parse_kotlin_file(content: str):
    """Structural pattern extraction for Kotlin."""
    classes, functions, hooks, imports = [], [], set(), set()
    for idx, line in enumerate(content.splitlines(), start=1):
        sline = line.strip()
        if not sline or sline.startswith("//") or sline.startswith("/*"):
            continue

        m_cls = re.search(r'(?:open\s+|data\s+|abstract\s+|sealed\s+|internal\s+)?(?:class|interface|object)\s+([a-zA-Z0-9_]+)', sline)
        if m_cls:
            classes.append({"name": m_cls.group(1), "line": idx})

        m_fn = re.search(r'(?:override\s+|suspend\s+|private\s+|protected\s+|public\s+|internal\s+)?fun\s+(?:<[^>]+>\s+)?([a-zA-Z0-9_]+)\s*\(([^)]*)\)', sline)
        if m_fn:
            args = [a.strip().split(":")[0].strip() for a in m_fn.group(2).split(",") if a.strip()]
            functions.append({"name": m_fn.group(1), "line": idx, "args": args})

        m_imp = re.search(r'^import\s+([a-zA-Z0-9_.*]+)', sline)
        if m_imp:
            imports.add(m_imp.group(1))

        if re.search(r'\b(?:HttpClient|OkHttpClient|Fuel|ProcessBuilder|Runtime\.getRuntime)\b', sline):
            m_hook = re.findall(r'\b(?:HttpClient|OkHttpClient|Fuel|ProcessBuilder)\b', sline)
            hooks.add(m_hook[0] if m_hook else "process/http")

    return {"classes": classes, "functions": functions, "hooks": sorted(list(hooks)), "imports": sorted(list(imports))}

def parse_swift_file(content: str):
    """Structural pattern extraction for Swift."""
    classes, functions, hooks, imports = [], [], set(), set()
    for idx, line in enumerate(content.splitlines(), start=1):
        sline = line.strip()
        if not sline or sline.startswith("//"):
            continue

        m_cls = re.search(r'(?:public\s+|private\s+|open\s+|final\s+)?(?:class|struct|enum|protocol)\s+([a-zA-Z0-9_]+)', sline)
        if m_cls:
            classes.append({"name": m_cls.group(1), "line": idx})

        m_fn = re.search(r'(?:public\s+|private\s+|open\s+|override\s+|static\s+)?func\s+([a-zA-Z0-9_]+)\s*(?:<[^>]+>)?\s*\(([^)]*)\)', sline)
        if m_fn:
            args = [a.strip().split(":")[0].strip() for a in m_fn.group(2).split(",") if a.strip()]
            functions.append({"name": m_fn.group(1), "line": idx, "args": args})

        m_imp = re.search(r'^import\s+([a-zA-Z0-9_]+)', sline)
        if m_imp:
            imports.add(m_imp.group(1))

        if re.search(r'\b(?:URLSession|Alamofire|Process\(|ProcessInfo)\b', sline):
            m_hook = re.findall(r'\b(?:URLSession|Alamofire|Process)\b', sline)
            hooks.add(m_hook[0] if m_hook else "process/http")

    return {"classes": classes, "functions": functions, "hooks": sorted(list(hooks)), "imports": sorted(list(imports))}

def parse_c_cpp_file(content: str):
    """Structural pattern extraction for C and C++."""
    classes, functions, hooks, imports = [], [], set(), set()
    for idx, line in enumerate(content.splitlines(), start=1):
        sline = line.strip()
        if not sline or sline.startswith("//") or sline.startswith("/*"):
            continue

        m_cls = re.search(r'(?:class|struct|enum)\s+([a-zA-Z0-9_]+)(?:\s*:\s*(?:public|private|protected)\s+([a-zA-Z0-9_]+))?', sline)
        if m_cls and not sline.endswith(";"):
            classes.append({"name": m_cls.group(1), "line": idx})

        m_fn = re.search(r'^\s*(?:(?:inline|static|virtual|explicit|extern|const)\s+)*[\w:*&<>]+\s+([a-zA-Z0-9_~]+)\s*\(([^)]*)\)\s*(?:const)?\s*(?:;|{|->)', sline)
        if m_fn and m_fn.group(1) not in ("if", "for", "while", "switch", "catch"):
            args = [a.strip().split()[-1] for a in m_fn.group(2).split(",") if a.strip()]
            functions.append({"name": m_fn.group(1), "line": idx, "args": args})

        m_inc = re.search(r'#include\s*[<"]([^>"]+)[>"]', sline)
        if m_inc:
            imports.add(m_inc.group(1))

        if re.search(r'\b(?:system|popen|execvp|execl|curl_easy_init|socket|connect|CreateProcess)\b', sline):
            m_hook = re.findall(r'\b(?:system|popen|curl_easy_init|socket|CreateProcess)\b', sline)
            hooks.add(m_hook[0] if m_hook else "system/network")

    return {"classes": classes, "functions": functions, "hooks": sorted(list(hooks)), "imports": sorted(list(imports))}

def parse_ruby_file(content: str):
    """Structural pattern extraction for Ruby."""
    classes, functions, hooks, imports = [], [], set(), set()
    for idx, line in enumerate(content.splitlines(), start=1):
        sline = line.strip()
        if not sline or sline.startswith("#"):
            continue

        m_cls = re.search(r'(?:class|module)\s+([a-zA-Z0-9_:]+)', sline)
        if m_cls:
            classes.append({"name": m_cls.group(1), "line": idx})

        m_fn = re.search(r'def\s+([a-zA-Z0-9_!?=]+)(?:\s*\(([^)]*)\))?', sline)
        if m_fn:
            args = [a.strip() for a in (m_fn.group(2) or "").split(",") if a.strip()]
            functions.append({"name": m_fn.group(1), "line": idx, "args": args})

        m_req = re.search(r'(?:require|require_relative|load)\s+[\'"]([^\'"]+)[\'"]', sline)
        if m_req:
            imports.add(m_req.group(1))

        if re.search(r'\b(?:Net::HTTP|Faraday|system|exec|Open3)\b|`[^`]+`', sline):
            hooks.add("network/shell")

    return {"classes": classes, "functions": functions, "hooks": sorted(list(hooks)), "imports": sorted(list(imports))}

def parse_php_file(content: str):
    """Structural pattern extraction for PHP."""
    classes, functions, hooks, imports = [], [], set(), set()
    for idx, line in enumerate(content.splitlines(), start=1):
        sline = line.strip()
        if not sline or sline.startswith("//") or sline.startswith("#"):
            continue

        m_cls = re.search(r'(?:abstract\s+|final\s+)?(?:class|interface|trait)\s+([a-zA-Z0-9_]+)', sline)
        if m_cls:
            classes.append({"name": m_cls.group(1), "line": idx})

        m_fn = re.search(r'(?:public\s+|protected\s+|private\s+|static\s+)?function\s+([a-zA-Z0-9_]+)\s*\(([^)]*)\)', sline)
        if m_fn:
            args = [a.strip().split("$")[-1] for a in m_fn.group(2).split(",") if a.strip()]
            functions.append({"name": m_fn.group(1), "line": idx, "args": args})

        m_req = re.search(r'(?:require|require_once|include|include_once|use)\s+[\'"]?([^\'";\s]+)', sline)
        if m_req:
            imports.add(m_req.group(1))

        if re.search(r'\b(?:curl_init|curl_exec|file_get_contents|exec|shell_exec|system|passthru)\b', sline):
            hooks.add("network/shell")

    return {"classes": classes, "functions": functions, "hooks": sorted(list(hooks)), "imports": sorted(list(imports))}

def parse_scala_file(content: str):
    """Structural pattern extraction for Scala."""
    classes, functions, hooks, imports = [], [], set(), set()
    for idx, line in enumerate(content.splitlines(), start=1):
        sline = line.strip()
        if not sline or sline.startswith("//"):
            continue

        m_cls = re.search(r'(?:case\s+)?(?:class|object|trait)\s+([a-zA-Z0-9_]+)', sline)
        if m_cls:
            classes.append({"name": m_cls.group(1), "line": idx})

        m_fn = re.search(r'def\s+([a-zA-Z0-9_+=><]+)\s*(?:\[[^\]]+\])?\s*(?:\(([^)]*)\))?', sline)
        if m_fn:
            args = [a.strip().split(":")[0].strip() for a in (m_fn.group(2) or "").split(",") if a.strip()]
            functions.append({"name": m_fn.group(1), "line": idx, "args": args})

        m_imp = re.search(r'^import\s+([a-zA-Z0-9_.*]+)', sline)
        if m_imp:
            imports.add(m_imp.group(1))

        if re.search(r'\b(?:scala\.sys\.process|Http|sttp|Process)\b', sline):
            hooks.add("process/http")

    return {"classes": classes, "functions": functions, "hooks": sorted(list(hooks)), "imports": sorted(list(imports))}

def parse_elixir_file(content: str):
    """Structural pattern extraction for Elixir."""
    classes, functions, hooks, imports = [], [], set(), set()
    for idx, line in enumerate(content.splitlines(), start=1):
        sline = line.strip()
        if not sline or sline.startswith("#"):
            continue

        m_mod = re.search(r'defmodule\s+([a-zA-Z0-9_.]+)', sline)
        if m_mod:
            classes.append({"name": m_mod.group(1), "line": idx})

        m_fn = re.search(r'(?:def|defp)\s+([a-zA-Z0-9_!?]+)(?:\s*\(([^)]*)\))?', sline)
        if m_fn:
            args = [a.strip() for a in (m_fn.group(2) or "").split(",") if a.strip()]
            functions.append({"name": m_fn.group(1), "line": idx, "args": args})

        m_imp = re.search(r'(?:alias|import|use)\s+([a-zA-Z0-9_.]+)', sline)
        if m_imp:
            imports.add(m_imp.group(1))

        if re.search(r'\b(?:System\.cmd|HTTPoison|Req|Finch)\b', sline):
            hooks.add("system/http")

    return {"classes": classes, "functions": functions, "hooks": sorted(list(hooks)), "imports": sorted(list(imports))}


def parse_jinja_file(content: str):
    """Jinja2 / Nunjucks / Liquid macros, blocks, and template inheritance."""
    classes, functions, hooks, imports = [], [], set(), set()
    for idx, line in enumerate(content.splitlines(), start=1):
        sline = line.strip()
        if not sline:
            continue
        m_macro = re.search(
            r'\{%-?\s*(?:macro|function)\s+([a-zA-Z0-9_]+)\s*\(([^)]*)\)',
            sline,
        )
        if m_macro:
            args = [a.strip().split("=")[0].strip() for a in m_macro.group(2).split(",") if a.strip()]
            functions.append({"name": m_macro.group(1), "line": idx, "args": args})
        m_block = re.search(r'\{%-?\s*block\s+([a-zA-Z0-9_]+)', sline)
        if m_block:
            classes.append({"name": m_block.group(1), "line": idx})
        for imp in re.findall(
            r'\{%-?\s*(?:extends|include|import|from)\s+[\'"]([^\'"]+)[\'"]',
            sline,
        ):
            imports.add(imp)
        if re.search(r'\b(?:url_for|request\.|UrlFetchApp|fetch\(|curl)\b', sline):
            hooks.add("template/network")
    return {"classes": classes, "functions": functions, "hooks": sorted(list(hooks)), "imports": sorted(list(imports))}


_MERMAID_KIND = re.compile(
    r'^\s*(flowchart|graph|sequenceDiagram|classDiagram|erDiagram|'
    r'stateDiagram(?:-v2)?|gantt|pie|gitGraph|journey|mindmap|timeline|'
    r'quadrantChart|sankey(?:-beta)?|xychart(?:-beta)?|kanban|'
    r'C4Context|C4Container|C4Component)\b',
    re.I,
)


def parse_mermaid_file(content: str):
    """Diagram kind plus named participants, classes, and subgraphs."""
    classes, functions, hooks, imports = [], [], set(), set()
    for idx, line in enumerate(content.splitlines(), start=1):
        sline = line.strip()
        if not sline or sline.startswith("%%"):
            continue
        m_kind = _MERMAID_KIND.match(sline)
        if m_kind:
            classes.append({"name": m_kind.group(1), "line": idx})
            continue
        m_node = re.search(
            r'^\s*(?:participant|actor|class|subgraph)\s+([A-Za-z0-9_$-]+)',
            sline,
            re.I,
        )
        if m_node:
            functions.append({"name": m_node.group(1), "line": idx})
    return {"classes": classes, "functions": functions, "hooks": sorted(list(hooks)), "imports": sorted(list(imports))}


def parse_markdown_file(content: str):
    """Index mermaid fences inside Markdown; skip files with none at map time."""
    classes, functions, hooks, imports = [], [], set(), set()
    for m in re.finditer(r"```mermaid[ \t]*\r?\n(.*?)```", content, re.S | re.I):
        offset_line = content[:m.start()].count("\n") + 1
        inner = parse_mermaid_file(m.group(1))
        for item in inner["classes"]:
            item["line"] = offset_line + item.get("line", 1) - 1
            classes.append(item)
        for item in inner["functions"]:
            item["line"] = offset_line + item.get("line", 1) - 1
            functions.append(item)
    return {"classes": classes, "functions": functions, "hooks": sorted(list(hooks)), "imports": sorted(list(imports))}


def parse_shell_file(content: str):
    functions, hooks, imports = [], set(), set()
    for idx, line in enumerate(content.splitlines(), start=1):
        sline = line.strip()
        if not sline or sline.startswith("#"):
            continue
        m_fn = re.search(r'^(?:function\s+([a-zA-Z0-9_:-]+)|\s*([a-zA-Z0-9_:-]+)\s*\(\s*\))', sline)
        if m_fn:
            functions.append({"name": m_fn.group(1) or m_fn.group(2), "line": idx})
        m_src = re.search(r'^(?:source|\.)\s+[\'"]?([^\s\'"]+)', sline)
        if m_src:
            imports.add(m_src.group(1))
        if re.search(r'\b(?:curl|wget|ssh|scp|kubectl|docker|nc|ncat)\b', sline):
            hooks.add("network/shell")
    return {"classes": [], "functions": functions, "hooks": sorted(list(hooks)), "imports": sorted(list(imports))}


def parse_sql_file(content: str):
    classes, functions = [], []
    for idx, line in enumerate(content.splitlines(), start=1):
        sline = line.strip()
        if not sline or sline.startswith("--"):
            continue
        m_obj = re.search(
            r'CREATE\s+(?:OR\s+REPLACE\s+)?(?:TEMP(?:ORARY)?\s+)?'
            r'(TABLE|VIEW|FUNCTION|PROCEDURE|TRIGGER|INDEX|SCHEMA)\s+'
            r'(?:IF\s+NOT\s+EXISTS\s+)?([a-zA-Z0-9_."]+)',
            sline,
            re.I,
        )
        if m_obj:
            kind = m_obj.group(1).upper()
            name = m_obj.group(2).strip('"')
            if kind in ("FUNCTION", "PROCEDURE"):
                functions.append({"name": name, "line": idx})
            else:
                classes.append({"name": name, "line": idx})
    return {"classes": classes, "functions": functions, "hooks": [], "imports": []}


def parse_hcl_file(content: str):
    classes, functions, hooks = [], [], set()
    for idx, line in enumerate(content.splitlines(), start=1):
        sline = line.strip()
        if not sline or sline.startswith("#") or sline.startswith("//"):
            continue
        m_block = re.search(
            r'^(resource|data|module|variable|output|provider|locals)\s+'
            r'(?:["\']([^"\']+)["\']\s+)?(?:["\']([^"\']+)["\'])?',
            sline,
        )
        if m_block:
            kind, first, second = m_block.group(1), m_block.group(2), m_block.group(3)
            label = ".".join([p for p in (kind, first, second) if p])
            classes.append({"name": label, "line": idx})
        if re.search(r'\b(?:http_request|remote-exec|local-exec|provisioner)\b', sline):
            hooks.add("provisioner/http")
    return {"classes": classes, "functions": functions, "hooks": sorted(list(hooks)), "imports": []}


def parse_dockerfile(content: str):
    classes, functions, hooks, imports = [], [], set(), set()
    for idx, line in enumerate(content.splitlines(), start=1):
        sline = line.strip()
        if not sline or sline.startswith("#"):
            continue
        m_from = re.search(r'^FROM\s+(\S+)(?:\s+AS\s+(\S+))?', sline, re.I)
        if m_from:
            classes.append({"name": m_from.group(2) or m_from.group(1), "line": idx})
        m_copy = re.search(r'^(?:COPY|ADD)\s+(.+)$', sline, re.I)
        if m_copy:
            imports.add(m_copy.group(1).split()[0])
        if re.search(r'\b(?:curl|wget|apk add|apt-get)\b', sline, re.I):
            hooks.add("network/pkg")
        m_entry = re.search(r'^(?:ENTRYPOINT|CMD|RUN)\b', sline, re.I)
        if m_entry:
            functions.append({"name": m_entry.group(0).split()[0].upper(), "line": idx})
    return {"classes": classes, "functions": functions, "hooks": sorted(list(hooks)), "imports": sorted(list(imports))}


def parse_make_file(content: str):
    functions = []
    for idx, line in enumerate(content.splitlines(), start=1):
        if not line or line.startswith("\t") or line.startswith("#") or line.startswith(" "):
            continue
        m = re.match(r'^([A-Za-z0-9_./%-]+)\s*:', line)
        if m and not m.group(1).startswith("."):
            functions.append({"name": m.group(1), "line": idx})
    return {"classes": [], "functions": functions, "hooks": [], "imports": []}


def parse_vue_svelte_file(content: str):
    scripts = re.findall(r"<script\b[^>]*>(.*?)</script>", content, re.S | re.I)
    parsed = parse_js_ts_file("\n".join(scripts))
    m_name = re.search(r"""name\s*:\s*['"]([^'"]+)['"]""", content)
    if m_name:
        parsed.setdefault("classes", [])
        parsed["classes"].append({"name": m_name.group(1), "line": 1})
    return parsed


def parse_generic_file(content: str, lang: str):
    """Generic symbol extraction for Go, Rust, Java, C#, Lua, Dart, GraphQL, proto, Solidity, R."""
    functions, classes, hooks, imports = [], [], set(), set()
    for idx, line in enumerate(content.splitlines(), start=1):
        sline = line.strip()
        if not sline:
            continue

        if lang == "go":
            m = re.search(r'func\s+(?:\([^)]+\)\s+)?([a-zA-Z0-9_]+)\s*\(([^)]*)\)', sline)
            if m:
                functions.append({"name": m.group(1), "line": idx})
            m_struct = re.search(r'type\s+([a-zA-Z0-9_]+)\s+(?:struct|interface)', sline)
            if m_struct:
                classes.append({"name": m_struct.group(1), "line": idx})
            m_imp = re.search(r'(?:import\s+)?[\'"]([^\'"]+)[\'"]', sline)
            if m_imp and ("/" in m_imp.group(1) or sline.startswith("import")):
                imports.add(m_imp.group(1))

        elif lang == "rust":
            m = re.search(r'fn\s+([a-zA-Z0-9_]+)\s*(?:<[^>]*>)?\s*\(([^)]*)\)', sline)
            if m:
                functions.append({"name": m.group(1), "line": idx})
            m_st = re.search(r'(?:struct|enum|trait)\s+([a-zA-Z0-9_]+)', sline)
            if m_st:
                classes.append({"name": m_st.group(1), "line": idx})
            m_imp = re.search(r'use\s+([a-zA-Z0-9_:]+)', sline)
            if m_imp:
                imports.add(m_imp.group(1))

        elif lang in ("csharp", "java"):
            m = re.search(r'(?:public|private|protected|internal)?\s*(?:static\s+)?class\s+([a-zA-Z0-9_]+)', sline)
            if m:
                classes.append({"name": m.group(1), "line": idx})
            m_fn = re.search(r'(?:public|private|protected|internal)\s+(?:static\s+)?(?:async\s+)?[\w<>\[\], ?]+\s+([a-zA-Z0-9_]+)\s*\(([^)]*)\)', sline)
            if m_fn:
                functions.append({"name": m_fn.group(1), "line": idx})
            m_imp = re.search(r'(?:using|import)\s+([a-zA-Z0-9_.]+)', sline)
            if m_imp:
                imports.add(m_imp.group(1))

        elif lang == "lua":
            m = re.search(r'(?:local\s+)?function\s+([a-zA-Z0-9_.:]+)\s*\(([^)]*)\)', sline)
            if m:
                functions.append({"name": m.group(1), "line": idx})

        elif lang == "dart":
            m_cls = re.search(r'(?:class|mixin|enum|extension)\s+([A-Za-z0-9_]+)', sline)
            if m_cls:
                classes.append({"name": m_cls.group(1), "line": idx})
            m_fn = re.search(
                r'(?:[\w<>,?\[\]\s]+)\s+([a-zA-Z0-9_]+)\s*\(([^)]*)\)\s*(?:async\s*)?\{?',
                sline,
            )
            if m_fn and m_fn.group(1) not in ("if", "for", "while", "switch", "catch"):
                functions.append({"name": m_fn.group(1), "line": idx})

        elif lang == "graphql":
            m = re.search(
                r'^(?:type|interface|enum|input|union|scalar|extend\s+type)\s+([A-Za-z0-9_]+)',
                sline,
            )
            if m:
                classes.append({"name": m.group(1), "line": idx})
            m_op = re.search(r'^(?:query|mutation|subscription)\s+([A-Za-z0-9_]+)', sline)
            if m_op:
                functions.append({"name": m_op.group(1), "line": idx})

        elif lang == "proto":
            m = re.search(r'^(?:message|service|enum)\s+([A-Za-z0-9_]+)', sline)
            if m:
                classes.append({"name": m.group(1), "line": idx})
            m_rpc = re.search(r'rpc\s+([A-Za-z0-9_]+)\s*\(', sline)
            if m_rpc:
                functions.append({"name": m_rpc.group(1), "line": idx})
            m_imp = re.search(r'import\s+"([^"]+)"', sline)
            if m_imp:
                imports.add(m_imp.group(1))

        elif lang == "solidity":
            m = re.search(r'^(?:contract|interface|library|abstract\s+contract)\s+([A-Za-z0-9_]+)', sline)
            if m:
                classes.append({"name": m.group(1), "line": idx})
            m_fn = re.search(r'function\s+([A-Za-z0-9_]+)\s*\(', sline)
            if m_fn:
                functions.append({"name": m_fn.group(1), "line": idx})

        elif lang == "r":
            m = re.search(r'^([A-Za-z.][A-Za-z0-9._]*)\s*(?:<-|=)\s*function\s*\(', sline)
            if m:
                functions.append({"name": m.group(1), "line": idx})

    return {
        "classes": classes,
        "functions": functions,
        "hooks": sorted(list(hooks)),
        "imports": sorted(list(imports))
    }


def parse_file_content(lang, content):
    """Dispatch to the language extractor. Returns None if the language is unknown."""
    if lang == "python":
        return parse_python_file(content)
    if lang in ("javascript", "typescript", "google-apps-script"):
        return parse_js_ts_file(content)
    if lang == "powershell":
        return parse_powershell_file(content)
    if lang == "vbscript":
        return parse_vbscript_file(content)
    if lang == "kotlin":
        return parse_kotlin_file(content)
    if lang == "swift":
        return parse_swift_file(content)
    if lang in ("c", "cpp"):
        return parse_c_cpp_file(content)
    if lang == "ruby":
        return parse_ruby_file(content)
    if lang == "php":
        return parse_php_file(content)
    if lang == "scala":
        return parse_scala_file(content)
    if lang == "elixir":
        return parse_elixir_file(content)
    if lang == "jinja":
        return parse_jinja_file(content)
    if lang == "mermaid":
        return parse_mermaid_file(content)
    if lang == "markdown":
        return parse_markdown_file(content)
    if lang == "shell":
        return parse_shell_file(content)
    if lang == "sql":
        return parse_sql_file(content)
    if lang == "terraform":
        return parse_hcl_file(content)
    if lang == "dockerfile":
        return parse_dockerfile(content)
    if lang == "make":
        return parse_make_file(content)
    if lang in ("vue", "svelte"):
        return parse_vue_svelte_file(content)
    if lang in _GENERIC_LANGS:
        return parse_generic_file(content, lang)
    if lang == "json":
        return {"classes": [], "functions": [], "hooks": [], "imports": []}
    return None

# --- Semantic Dependency Graph & Topological Engine ---

def build_dependency_graph(files_dict: dict):
    """
    Builds directed dependency graph from extracted import declarations.
    Identifies entry points, detects circular dependency cycles, and computes
    a recommended topological edit sequence.
    """
    all_files = list(files_dict.keys())
    # Maps stem and relative path to canonical path in files_dict
    stem_map = {}
    for f in all_files:
        stem = Path(f).stem
        if stem not in stem_map:
            stem_map[stem] = []
        stem_map[stem].append(f)

    # Graph adjacencies: source -> targets (source depends on target)
    graph = {f: set() for f in all_files}
    in_degrees = {f: 0 for f in all_files}

    for src, info in files_dict.items():
        src_parent = Path(src).parent
        for imp in info.get("imports", []):
            imp_norm = imp.replace("\\", "/").rstrip(";")
            matched_target = None

            # 1. Exact match
            if imp_norm in files_dict and imp_norm != src:
                matched_target = imp_norm
            # 2. Relative match
            elif (src_parent / imp_norm).as_posix() in files_dict:
                matched_target = (src_parent / imp_norm).as_posix()
            else:
                # 3. Stem matching (e.g. "engine" -> "src/engine.py")
                target_stem = Path(imp_norm).stem.split(".")[-1]
                if target_stem in stem_map:
                    candidates = [c for c in stem_map[target_stem] if c != src]
                    if candidates:
                        matched_target = candidates[0]

            if matched_target and matched_target != src:
                if matched_target not in graph[src]:
                    graph[src].add(matched_target)
                    in_degrees[matched_target] += 1

    # Cycle Detection using 3-color DFS
    # 0 = unvisited, 1 = visiting, 2 = visited
    state = {f: 0 for f in all_files}
    cycles = []

    def dfs(node, path):
        state[node] = 1
        path.append(node)
        for neighbor in graph[node]:
            if state[neighbor] == 1:
                cycle_start = path.index(neighbor)
                cycles.append(path[cycle_start:] + [neighbor])
            elif state[neighbor] == 0:
                dfs(neighbor, path)
        path.pop()
        state[node] = 2

    for f in all_files:
        if state[f] == 0:
            dfs(f, [])

    # Entry points: files that are NOT imported by other project files (in_degree == 0)
    entry_points = [f for f, count in in_degrees.items() if count == 0]
    # Prioritize common entry names if present
    entry_patterns = re.compile(r'(?:main|app|index|cli|server|deploy|run)', re.I)
    entry_points.sort(key=lambda x: (0 if entry_patterns.search(x) else 1, x))

    # Topological sort (Kahn's algorithm on dependency graph)
    # Prerequisite order: files with 0 outgoing dependencies (leaves) are built/understood first
    out_degrees = {f: len(graph[f]) for f in all_files}
    rev_graph = {f: set() for f in all_files}
    for src, targets in graph.items():
        for t in targets:
            rev_graph[t].add(src)

    ready = [f for f, count in out_degrees.items() if count == 0]
    topological_order = []

    while ready:
        node = ready.pop(0)
        topological_order.append(node)
        for dependent in rev_graph[node]:
            out_degrees[dependent] -= 1
            if out_degrees[dependent] == 0:
                ready.append(dependent)

    # If cycles exist, append any remaining nodes
    for f in all_files:
        if f not in topological_order:
            topological_order.append(f)

    total_edges = sum(len(targets) for targets in graph.values())

    return {
        "total_nodes": len(all_files),
        "total_edges": total_edges,
        "entry_points": entry_points[:8],
        "circular_dependencies": cycles[:5],
        "topological_order": topological_order
    }

# --- Core Engine Commands ---

def cmd_map(workspace_path: Path):
    """Scans repository and generates minified .agent-context.json metadata map."""
    start_time = time.time()
    workspace_path = workspace_path.resolve()
    if is_unsafe_workspace(workspace_path):
        print(
            f"\033[1;31m[ctx map]\033[0m Refusing to index filesystem root or home directory: {workspace_path}",
            file=sys.stderr,
        )
        return 1

    index_data = {
        "meta": {
            "version": VERSION,
            # Absolute on purpose: MCP clients pass this path back as workspace_path.
            # The index is gitignored so this machine path is not committed.
            "root": str(workspace_path).replace("\\", "/"),
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "total_files": 0,
            "total_lines": 0,
            "total_symbols": 0,
        },
        "files": {},
        "graph": {}
    }

    total_lines = 0
    total_symbols = 0
    raw_size_bytes = 0
    truncated = False
    stop_walk = False

    for root, dirs, files in os.walk(workspace_path):
        if stop_walk:
            dirs[:] = []
            continue
        # Prune ignored directories in-place
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS and not d.startswith(".")]

        for file in files:
            file_path = Path(root) / file
            ext = file_path.suffix.lower()

            if file_path.name == ".agent-context.json":
                continue
            lang = language_for_path(file_path)
            if ext in IGNORE_EXTENSIONS or lang is None:
                continue

            # Skip large files (> 500 KB)
            try:
                stat = file_path.stat()
                if stat.st_size > 500 * 1024 or stat.st_size == 0:
                    continue
                raw_size_bytes += stat.st_size
            except OSError:
                continue

            rel_path = file_path.relative_to(workspace_path).as_posix()

            try:
                with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
            except Exception:
                continue

            file_lines = len(content.splitlines())
            total_lines += file_lines

            parsed = parse_file_content(lang, content)
            if lang == "markdown" and parsed and not parsed.get("classes") and not parsed.get("functions"):
                total_lines -= file_lines
                continue

            if parsed:
                file_sym_count = len(parsed.get("classes", [])) + len(parsed.get("functions", []))
                total_symbols += file_sym_count

                entry = {
                    "lang": lang,
                    "lines": file_lines
                }
                if parsed.get("classes"):
                    entry["classes"] = parsed["classes"]
                if parsed.get("functions"):
                    entry["functions"] = parsed["functions"]
                if parsed.get("hooks"):
                    entry["hooks"] = parsed["hooks"]
                if parsed.get("constants"):
                    entry["constants"] = parsed["constants"]
                if parsed.get("imports"):
                    entry["imports"] = parsed["imports"]
                if parsed.get("error"):
                    entry["error"] = parsed["error"]

                index_data["files"][rel_path] = entry
                if len(index_data["files"]) >= MAP_MAX_FILES:
                    truncated = True
                    stop_walk = True
                    dirs[:] = []
                    break

    index_data["meta"]["total_files"] = len(index_data["files"])
    if truncated:
        index_data["meta"]["truncated"] = True
    index_data["meta"]["total_lines"] = total_lines
    index_data["meta"]["total_symbols"] = total_symbols

    # Compute dependency graph & topological sequence
    index_data["graph"] = build_dependency_graph(index_data["files"])

    out_file = workspace_path / ".agent-context.json"
    # Write minified JSON (zero extra whitespace) for minimum LLM token usage
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(index_data, f, separators=(",", ":"))

    out_size = out_file.stat().st_size
    duration = time.time() - start_time
    
    # Calculate estimated token savings (approx 4 chars per token)
    est_raw_tokens = raw_size_bytes // 4
    est_map_tokens = out_size // 4
    pct_savings = round((1 - (est_map_tokens / max(est_raw_tokens, 1))) * 100, 1) if est_raw_tokens > est_map_tokens else 0

    print(f"\033[1;32m[ctx map]\033[0m Workspace indexed in {duration:.2f}s")
    print(f"  Root:             {workspace_path}")
    print(f"  Indexed Files:    {index_data['meta']['total_files']} files ({total_lines:,} total lines)")
    print(f"  Extracted:        {total_symbols} symbols & cross-boundary hooks")
    print(f"  Dependency Graph: {index_data['graph']['total_nodes']} nodes, {index_data['graph']['total_edges']} internal edges")
    print(f"  Context Map:      {out_file.name} ({out_size / 1024:.1f} KB, ~{est_map_tokens:,} tokens)")
    print(f"  Token Savings:    ~{pct_savings}% reduction vs raw files (~{est_raw_tokens:,} tokens)")
    if truncated:
        print(f"  \033[1;33mTruncated:\033[0m hit {MAP_MAX_FILES}-file cap; re-run against a tighter directory.")
    return 0

def cmd_graph(workspace_path: Path):
    """Outputs dependency topology, entry points, cycles, and recommended edit order."""
    context_file = workspace_path / ".agent-context.json"
    if not context_file.is_file():
        if cmd_map(workspace_path) != 0:
            return 1

    try:
        with open(context_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"\033[1;31mError reading context map:\033[0m {e}", file=sys.stderr)
        return 1

    graph = data.get("graph", {})
    if not graph:
        print("\033[1;33m[ctx graph]\033[0m No graph metadata found. Re-run 'ctx map'.")
        return 1

    print(f"\033[1;36m=== Architectural Dependency Graph ===\033[0m")
    print(f"  Total Files (Nodes):  {graph.get('total_nodes', 0)}")
    print(f"  Internal Dependencies: {graph.get('total_edges', 0)}")

    entry_points = graph.get("entry_points", [])
    if entry_points:
        print(f"\n\033[1;32mEntry Points (Root Callers):\033[0m")
        for ep in entry_points:
            print(f"  \033[1;34m* {ep}\033[0m")

    cycles = graph.get("circular_dependencies", [])
    if cycles:
        print(f"\n\033[1;31mCircular Dependencies Detected ({len(cycles)}):\033[0m")
        for cycle in cycles:
            print(f"  \033[1;31m[!] {' -> '.join(cycle)}\033[0m")
    else:
        print(f"\n\033[1;32mCircular Dependencies: None detected (Clean Directed Acyclic Graph)\033[0m")

    order = graph.get("topological_order", [])
    if order:
        print(f"\n\033[1;33mRecommended Agent Edit Order (Dependency Prerequisites First):\033[0m")
        for idx, item in enumerate(order[:12], start=1):
            print(f"  {idx:2d}. {item}")
        if len(order) > 12:
            print(f"      ... and {len(order) - 12} more files")

    return 0

def cmd_check(workspace_path: Path, check_all: bool = False):
    """Executes native local compilation checks on changed or selected files."""
    workspace_path = workspace_path.resolve()
    if is_unsafe_workspace(workspace_path):
        print(
            f"\033[1;31m[ctx check]\033[0m Refusing to scan filesystem root or home directory: {workspace_path}",
            file=sys.stderr,
        )
        return 1
    changed_files = []

    if check_all:
        for root, dirs, files in os.walk(workspace_path):
            dirs[:] = [d for d in dirs if d not in IGNORE_DIRS and not d.startswith(".")]
            for f in files:
                p = Path(root) / f
                if _is_checkable_path(p):
                    changed_files.append(p)
    else:
        # Check git status first
        try:
            res = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=str(workspace_path),
                capture_output=True,
                text=True,
                timeout=5
            )
            if res.returncode == 0 and res.stdout.strip():
                for line in res.stdout.splitlines():
                    path_str = line[3:].strip().strip('"')
                    if " -> " in path_str:
                        path_str = path_str.split(" -> ")[-1]
                    p = workspace_path / path_str
                    if p.is_file() and _is_checkable_path(p):
                        changed_files.append(p)
        except Exception:
            pass

        # If not git or no git changes found, check recently modified files (last 30 minutes)
        if not changed_files:
            recent_cutoff = time.time() - (30 * 60)
            for root, dirs, files in os.walk(workspace_path):
                dirs[:] = [d for d in dirs if d not in IGNORE_DIRS and not d.startswith(".")]
                for f in files:
                    p = Path(root) / f
                    if _is_checkable_path(p):
                        try:
                            if p.stat().st_mtime >= recent_cutoff:
                                changed_files.append(p)
                        except OSError:
                            pass

    if not changed_files:
        print("\033[1;33m[ctx check]\033[0m No modified code files detected to validate.")
        return 0

    print(f"\033[1;36m[ctx check]\033[0m Validating syntax for {len(changed_files)} file(s)...")

    has_node = shutil.which("node") is not None
    has_ruby = shutil.which("ruby") is not None
    has_php = shutil.which("php") is not None
    has_bash = shutil.which("bash") is not None
    failures = []
    passes = 0

    for file_path in changed_files:
        rel_path = relposix(file_path, workspace_path)
        ext = file_path.suffix.lower()
        lang = language_for_path(file_path)

        # Python syntax validation via py_compile
        if ext == ".py":
            code, err_clean = _run_checker([sys.executable, "-m", "py_compile", str(file_path)])
            if code != 0:
                failures.append((rel_path, err_clean))
            else:
                passes += 1
                print(f"  \033[1;32m[PASS]\033[0m {rel_path} (Python)")

        # PowerShell syntax validation via native parser
        elif ext in (".ps1", ".psm1", ".psd1"):
            escaped_path = str(file_path).replace("'", "''")
            ps_script = f"""
$errors = $null
$tokens = $null
$content = [IO.File]::ReadAllText('{escaped_path}')
[System.Management.Automation.Language.Parser]::ParseInput($content, [ref]$tokens, [ref]$errors) | Out-Null
if ($errors.Count -gt 0) {{
    foreach ($err in $errors) {{
        [Console]::Error.WriteLine("Line " + $err.Extent.StartLineNumber + ": " + $err.Message)
    }}
    exit 1
}}
"""
            try:
                res = subprocess.run(
                    ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_script],
                    capture_output=True,
                    text=True,
                    timeout=CHECK_TIMEOUT_SEC,
                )
                if res.returncode != 0:
                    failures.append((rel_path, (res.stderr or res.stdout).strip()))
                else:
                    passes += 1
                    print(f"  \033[1;32m[PASS]\033[0m {rel_path} (PowerShell)")
            except subprocess.TimeoutExpired:
                failures.append((rel_path, f"Timed out after {CHECK_TIMEOUT_SEC}s"))

        # JavaScript / Apps Script via Node --check (not TS/JSX/Vue)
        elif ext in (".js", ".mjs", ".cjs", ".gs") and has_node:
            code, err_clean = _run_checker(["node", "--check", str(file_path)])
            if code != 0:
                failures.append((rel_path, err_clean))
            else:
                passes += 1
                print(f"  \033[1;32m[PASS]\033[0m {rel_path} (Node)")

        # Ruby syntax check
        elif ext in (".rb", ".rake") and has_ruby:
            code, err_clean = _run_checker(["ruby", "-c", str(file_path)])
            if code != 0:
                failures.append((rel_path, err_clean))
            else:
                passes += 1
                print(f"  \033[1;32m[PASS]\033[0m {rel_path} (Ruby)")

        # PHP syntax check
        elif ext == ".php" and has_php:
            code, err_clean = _run_checker(["php", "-l", str(file_path)])
            if code != 0:
                failures.append((rel_path, err_clean))
            else:
                passes += 1
                print(f"  \033[1;32m[PASS]\033[0m {rel_path} (PHP)")

        # JSON syntax validation
        elif ext == ".json":
            code, err_clean = _run_checker([sys.executable, "-m", "json.tool", str(file_path)])
            if code != 0:
                failures.append((rel_path, err_clean))
            else:
                passes += 1
                print(f"  \033[1;32m[PASS]\033[0m {rel_path} (JSON)")

        elif lang == "shell" and has_bash:
            code, err_clean = _run_checker(["bash", "-n", str(file_path)])
            if code != 0:
                failures.append((rel_path, err_clean))
            else:
                passes += 1
                print(f"  \033[1;32m[PASS]\033[0m {rel_path} (bash -n)")

        else:
            print(f"  \033[1;33m[SKIP]\033[0m {rel_path} (no local syntax checker)")

    print()
    if failures:
        print(f"\033[1;31m[ctx check FAIL]\033[0m {len(failures)} file(s) failed syntax validation:")
        for path, err in failures:
            print(f"  \033[1;31m* {path}\033[0m")
            for line in err.splitlines()[:5]:
                print(f"      {line}")
        return 1

    if passes == 0:
        print("\033[1;33m[ctx check]\033[0m No files had a local syntax checker available.")
        return 0

    print(f"\033[1;32m[ctx check SUCCESS]\033[0m All {passes} inspected file(s) passed syntax validation.")
    return 0

def cmd_slice(file_path: Path, start_line: int, end_line: int):
    """Slices a specific line-range from a file with 1-indexed line numbers."""
    if not file_path.is_file():
        print(f"\033[1;31mError:\033[0m File not found: {file_path}", file=sys.stderr)
        return 1

    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except Exception as e:
        print(f"\033[1;31mError reading file:\033[0m {e}", file=sys.stderr)
        return 1

    total = len(lines)
    if total == 0:
        print(f"\033[1;33m=== Slice: {file_path.name} (empty file) ===\033[0m")
        return 0

    try:
        start_line = int(start_line)
        end_line = int(end_line)
    except (TypeError, ValueError):
        print("\033[1;31mError:\033[0m start and end must be integers.", file=sys.stderr)
        return 1

    if end_line < start_line:
        start_line, end_line = end_line, start_line
    start_line = max(1, start_line)
    end_line = min(total, max(start_line, end_line))
    if end_line - start_line + 1 > SLICE_MAX_LINES:
        end_line = start_line + SLICE_MAX_LINES - 1
        print(
            f"\033[1;33m[ctx slice]\033[0m Range clamped to {SLICE_MAX_LINES} lines "
            f"({start_line}-{end_line} of {total}).",
            file=sys.stderr,
        )

    print(f"\033[1;36m=== Slice: {file_path.name} (Lines {start_line}-{end_line} of {total}) ===\033[0m")
    for idx in range(start_line - 1, end_line):
        line_no = idx + 1
        print(f"{line_no:5d} | {lines[idx].rstrip()}")
    return 0

def cmd_query(workspace_path: Path, query_term: str):
    """Queries the local .agent-context.json metadata map for a symbol."""
    context_file = workspace_path / ".agent-context.json"
    if not context_file.is_file():
        print(f"\033[1;33m[ctx]\033[0m No .agent-context.json found. Running 'ctx map' first...")
        if cmd_map(workspace_path) != 0:
            return 1

    try:
        with open(context_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"\033[1;31mError reading context map:\033[0m {e}", file=sys.stderr)
        return 1

    query_lower = query_term.lower()
    matches = []

    for rel_path, info in data.get("files", {}).items():
        for cls in info.get("classes", []):
            if query_lower in cls["name"].lower():
                matches.append((rel_path, cls["line"], f"class {cls['name']}", cls.get("methods", [])))
            for method in cls.get("methods", []):
                method_name = method if isinstance(method, str) else str(method.get("name", ""))
                if method_name and query_lower in method_name.lower():
                    matches.append(
                        (rel_path, cls.get("line", "-"), f"method {cls['name']}.{method_name}", [])
                    )
        for fn in info.get("functions", []):
            if query_lower in fn["name"].lower():
                args = ", ".join(fn.get("args", []))
                matches.append((rel_path, fn["line"], f"fn {fn['name']}({args})", []))
        for hook in info.get("hooks", []):
            if query_lower in hook.lower():
                matches.append((rel_path, "-", f"hook: {hook}", []))

    if not matches:
        print(f"\033[1;33m[ctx query]\033[0m No symbols matching '{query_term}' found in context map.")
        return 0

    print(f"\033[1;32m[ctx query]\033[0m Found {len(matches)} match(es) for '{query_term}':")
    for path, line, desc, methods in matches:
        line_str = f":{line}" if line != "-" else ""
        print(f"  \033[1;34m{path}{line_str}\033[0m -> \033[1m{desc}\033[0m")
        if methods:
            print(f"      methods: {', '.join(methods[:8])}")
    return 0

def main():
    parser = argparse.ArgumentParser(
        description="Agent Context Engine (ctx): Global Token Optimization & Verification Utility",
        prog="ctx"
    )
    parser.add_argument("--version", action="version", version=f"ctx {VERSION}")
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # map
    p_map = subparsers.add_parser("map", help="Scan workspace and create minified .agent-context.json")
    p_map.add_argument("workspace", nargs="?", default=".", help="Target workspace path (default: current dir)")

    # graph
    p_graph = subparsers.add_parser("graph", help="Analyze dependency topology, entry points, and topological order")
    p_graph.add_argument("workspace", nargs="?", default=".", help="Target workspace path (default: current dir)")

    # check
    p_check = subparsers.add_parser("check", help="Run local native syntax validation on changed files")
    p_check.add_argument("workspace", nargs="?", default=".", help="Target workspace path (default: current dir)")
    p_check.add_argument("--all", action="store_true", help="Validate all code files in workspace")

    # slice
    p_slice = subparsers.add_parser("slice", help="Read a surgical line-range from a file")
    p_slice.add_argument("file", help="Path to file")
    p_slice.add_argument("start", type=int, help="Start line (1-indexed)")
    p_slice.add_argument("end", type=int, help="End line (inclusive)")

    # query
    p_query = subparsers.add_parser("query", help="Look up a symbol in .agent-context.json")
    p_query.add_argument("symbol", help="Symbol name to search")
    p_query.add_argument("workspace", nargs="?", default=".", help="Target workspace path")

    # mcp
    p_mcp = subparsers.add_parser("mcp", help="Start or configure Model Context Protocol (MCP) server")
    p_mcp.add_argument("--install", action="store_true", help="Auto-configure MCP server in Antigravity, Cursor, Claude, and OpenCode")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 0

    if args.command == "map":
        return cmd_map(Path(args.workspace))
    elif args.command == "graph":
        return cmd_graph(Path(args.workspace))
    elif args.command == "check":
        return cmd_check(Path(args.workspace), check_all=args.all)
    elif args.command == "slice":
        return cmd_slice(Path(args.file), args.start, args.end)
    elif args.command == "query":
        return cmd_query(Path(args.workspace), args.symbol)
    elif args.command == "mcp":
        try:
            import mcp_server
        except ImportError:
            try:
                from . import mcp_server
            except ImportError:
                server_file = Path(__file__).resolve().parent / "mcp_server.py"
                import importlib.util
                spec = importlib.util.spec_from_file_location("mcp_server", server_file)
                mcp_server = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mcp_server)

        if getattr(args, "install", False):
            return mcp_server.cmd_install_mcp()
        mcp_server.run_stdio_server()
        return 0

    return 0

if __name__ == "__main__":
    sys.exit(main())
