#!/usr/bin/env bash
# Deploys Agent Context Engine globally to ~/.agent-context-engine and configures MCP across editors

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ENGINE_DIR="$HOME/.agent-context-engine"

echo ""
echo "=== Agent Context Engine Global Deployment ==="

# 1. Target Directory Creation
mkdir -p "$ENGINE_DIR"
echo "[+] Target engine directory: $ENGINE_DIR"

# 2. Deploy engine.py and mcp_server.py
cp "$REPO_ROOT/src/engine.py" "$ENGINE_DIR/engine.py"
cp "$REPO_ROOT/src/mcp_server.py" "$ENGINE_DIR/mcp_server.py"
echo "[+] Installed engine.py -> $ENGINE_DIR/engine.py"
echo "[+] Installed mcp_server.py -> $ENGINE_DIR/mcp_server.py"

# 3. Create Launcher
cat << 'EOF' > "$ENGINE_DIR/ctx"
#!/usr/bin/env bash
python3 "$HOME/.agent-context-engine/engine.py" "$@"
EOF
chmod +x "$ENGINE_DIR/ctx"
echo "[+] Created launcher -> $ENGINE_DIR/ctx"

# 4. PATH Check
if [[ ":$PATH:" != *":$ENGINE_DIR:"* ]]; then
    echo "[!] Tip: Add $ENGINE_DIR to your PATH in ~/.bashrc or ~/.zshrc:"
    echo "    export PATH=\"\$HOME/.agent-context-engine:\$PATH\""
fi

# 5. MCP Cross-Editor Configuration
python3 "$ENGINE_DIR/mcp_server.py" --install

echo "[✓] Deployment Successful! Verify via: ctx --help or ctx mcp"
