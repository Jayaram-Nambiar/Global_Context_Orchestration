#!/usr/bin/env bash
# Installs the Agent Context Engine pre-commit hook into .git/hooks/pre-commit

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
HOOKS_DIR="$REPO_ROOT/.git/hooks"

if [ ! -d "$HOOKS_DIR" ]; then
    echo "[!] Not a git repository: $REPO_ROOT"
    exit 0
fi

HOOK_FILE="$HOOKS_DIR/pre-commit"

cat << 'EOF' > "$HOOK_FILE"
#!/bin/sh
# Agent Context Engine (ctx) Pre-Commit Syntax Interceptor
if [ "$SKIP_CTX" = "1" ]; then
    exit 0
fi

echo "[ctx-hook] Intercepting syntax errors via local compiler checks..."

if command -v ctx >/dev/null 2>&1; then
    ctx check
    EXIT_CODE=$?
else
    python "$HOME/.agent-context-engine/engine.py" check
    EXIT_CODE=$?
fi

if [ $EXIT_CODE -ne 0 ]; then
    echo ""
    echo "[ctx-hook BLOCKED] Staged files contain syntax errors."
    echo "Fix errors above or bypass using: git commit --no-verify"
    exit 1
fi

exit 0
EOF

chmod +x "$HOOK_FILE"
echo "[+] Installed pre-commit hook -> $HOOK_FILE"
