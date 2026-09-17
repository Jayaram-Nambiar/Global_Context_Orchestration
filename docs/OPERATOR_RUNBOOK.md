# Agent Context Engine (`ctx`) - Operator Runbook

Welcome to the **Agent Context Engine (`ctx`)** Operator Runbook! This guide is designed to be beginner-friendly while providing comprehensive instructions for installing, operating, and troubleshooting the engine across all major operating systems (Windows, macOS, and Linux).

---

## Table of Contents
1. [What is the Agent Context Engine?](#1-what-is-the-agent-context-engine)
2. [Prerequisites](#2-prerequisites)
3. [Installation & Deployment](#3-installation--deployment)
4. [AI Editor Integration (MCP)](#4-ai-editor-integration-mcp)
5. [Day-to-Day Operations (CLI Guide)](#5-day-to-day-operations-cli-guide)
6. [Troubleshooting & FAQs](#6-troubleshooting--faqs)
7. [Maintenance & Uninstallation](#7-maintenance--uninstallation)

---

## 1. What is the Agent Context Engine?

When using AI coding assistants (like Cursor, Claude Code, or Antigravity), giving the AI an entire codebase to read consumes massive amounts of "tokens" (memory), costs money, and often causes the AI to hallucinate or forget important details.

The **Agent Context Engine (`ctx`)** solves this by generating a lightweight, structural "map" of your codebase locally on your machine. It extracts classes, functions, and cross-boundary network hooks in milliseconds without sending any of your code to the cloud. It also provides local syntax validation, ensuring that AI agents don't accidentally break your code.

---

## 2. Prerequisites

The engine is designed with **zero external dependencies**. You do not need Node.js, pip packages, or Docker.

You only need:
- **Python 3.8 or higher**: Installed and accessible in your system's `PATH`.
- **Git** (Optional but recommended): For repository tracking and Git hooks.

To verify Python is installed, open your terminal and run:
```bash
python --version
```

---

## 3. Installation & Deployment

The deployment script will copy the engine to your home directory (`~/.agent-context-engine`) and add the `ctx` command to your system `PATH`.

### Windows (PowerShell)
1. Open **PowerShell** (no administrator rights needed).
2. Navigate to the folder where you downloaded or cloned this repository.
3. Run the deployment script:
   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts\deploy.ps1
   ```
4. Restart your PowerShell terminal. You can now use the `ctx` command anywhere!

### macOS & Linux (Bash / Zsh)
1. Open your **Terminal**.
2. Navigate to the folder where you downloaded or cloned this repository.
3. Run the deployment script:
   ```bash
   bash scripts/deploy.sh
   ```
4. Restart your terminal or run `source ~/.bashrc` (or `~/.zshrc`). You can now use the `ctx` command anywhere!

---

## 4. AI Editor Integration (MCP)

To connect the engine directly to your AI IDEs (Antigravity, Cursor, Claude Desktop, or OpenCode), we use the **Model Context Protocol (MCP)**. 

### Automated Setup (All OS)
Once installed, simply run this command in your terminal:
```bash
ctx mcp --install
```
This command automatically detects installed AI editors and configures them to use the engine. 

*(Note: Restart your AI editor after running this command for the changes to take effect).*

### Manual Setup
If you prefer to configure an editor manually, the MCP server is located at:
- **Windows**: `C:\Users\<YourUsername>\.agent-context-engine\mcp_server.py`
- **macOS/Linux**: `/Users/<YourUsername>/.agent-context-engine/mcp_server.py`

You can add this to your editor's MCP settings using the command `python` and passing the absolute path to `mcp_server.py` as an argument. For detailed manual paths, see [EDITOR_INTEGRATION.md](./EDITOR_INTEGRATION.md).

---

## 5. Day-to-Day Operations (CLI Guide)

You can run these commands from any folder containing your code.

### `ctx map`
Scans your project and creates a tiny `.agent-context.json` map file.
- **Usage**: `ctx map` or `ctx map <path/to/folder>`
- **When to use**: Whenever you start a new coding session or after pulling massive updates from Git.

### `ctx query`
Quickly find where a function, class, or API hook is located without searching through files.
- **Usage**: `ctx query <symbol_name>`
- **Example**: `ctx query calculateTotal`

### `ctx check`
Runs a lightning-fast local syntax check on all recently changed files (preventing you or the AI from saving broken code).
- **Usage**: `ctx check` (checks only changed files)
- **Usage**: `ctx check --all` (checks every file in the project)

### `ctx slice`
Views a specific chunk of lines from a file. (Useful for AI agents to save tokens).
- **Usage**: `ctx slice <filename> <start_line> <end_line>`
- **Example**: `ctx slice src/main.py 10 50`
- Ranges are clamped to **150 lines**. Reversed start/end values are swapped.

### `ctx graph`
Analyzes your project to find circular dependencies and maps out the optimal order to edit files.
- **Usage**: `ctx graph`

### `ctx --version`
Prints the installed engine version.

---

## 6. Troubleshooting & FAQs

### Issue: "ctx is not recognized as an internal or external command"
- **Cause**: The folder `~/.agent-context-engine/bin` (or Scoop shims on Windows) hasn't been loaded into your terminal's `PATH`.
- **Fix (Windows)**: Restart your computer or manually add `C:\Users\<YourUsername>\.agent-context-engine\bin` to your System Environment Variables.
- **Fix (macOS/Linux)**: Ensure `export PATH="$HOME/.agent-context-engine/bin:$PATH"` is in your `~/.bashrc` or `~/.zshrc`, then run `source ~/.zshrc`.

### Issue: "Python is not found"
- **Cause**: Python is either not installed or not in your system `PATH`.
- **Fix**: Download Python from python.org. During Windows installation, ensure you check the box that says **"Add Python to PATH"**.

### Issue: `ctx mcp --install` says "skipped (not installed)" for my editor
- **Cause**: The configuration file for that specific editor does not exist on your machine, usually because the editor has never been opened.
- **Fix**: Open the AI editor (e.g., Cursor or OpenCode) at least once so it generates its default configuration files, then run `ctx mcp --install` again.

### Issue: The MCP tool shows "failed during live tool discovery" or `Unexpected token '[ctx map]' is not valid JSON`
- **Cause**: The host (Cursor, Claude Desktop, OpenCode) parses every stdout line as JSON-RPC. If the server prints CLI banners to stdout, the connection is killed.
- **Fix**: Update to engine 1.1.1+, redeploy, then run `ctx mcp --install`. Reload the editor's MCP servers. stdout is reserved for JSON-RPC; banners go to stderr.

### Issue: `ctx map` refuses to run on my home folder
- **Cause**: Mapping `$HOME` or a drive root would walk tens of thousands of files and time out MCP clients.
- **Fix**: Run `ctx map` from the project repository root, or pass that directory explicitly.

### Issue: `ctx mcp --install` skipped an editor with "invalid existing config"
- **Cause**: The editor config file exists but is not valid JSON (for example a trailing comma). The installer will not overwrite it.
- **Fix**: Repair the JSON, then re-run `ctx mcp --install`.

### Issue: Git Commits are being blocked by a syntax error
- **Cause**: The pre-commit hook runs `ctx check` automatically. You have a syntax error in your code!
- **Fix**: Fix the syntax error. If you *must* commit broken code temporarily, bypass the hook by adding `--no-verify` to your commit command:
  ```bash
  git commit -m "WIP" --no-verify
  ```

---

## 7. Maintenance & Uninstallation

### Updating the Engine
To update the engine to a newer version:
1. Pull the latest changes from the Git repository.
2. Run the deployment script again (`scripts/deploy.ps1` or `scripts/deploy.sh`).
3. Run `ctx mcp --install` to update the MCP server configurations.

### Uninstalling
If you wish to remove the Agent Context Engine from your system:
1. Delete the `~/.agent-context-engine` directory.
2. Remove any `export PATH=...` lines you may have manually added to your `~/.bashrc` or `~/.zshrc`.
3. Open your AI editors' MCP settings and remove the `agent-context-engine` entry.
4. If you installed the Git hooks, navigate to your repository's `.git/hooks/` folder and delete the `pre-commit` file.
