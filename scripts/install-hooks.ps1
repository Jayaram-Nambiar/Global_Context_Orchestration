<#
.SYNOPSIS
    Installs the Agent Context Engine pre-commit hook into the current Git repository.
.DESCRIPTION
    Creates or updates .git/hooks/pre-commit to automatically execute 'ctx check'
    before staged files are committed, preventing syntax bugs from entering version control.
#>

[CmdletBinding()]
param(
    [string]$RepoRoot = ""
)

$ErrorActionPreference = 'Stop'

if (-not $RepoRoot) {
    if ($PSScriptRoot) {
        $RepoRoot = Split-Path -Parent $PSScriptRoot
    } else {
        $RepoRoot = (Get-Location).Path
    }
}
$gitHooksDir = Join-Path $RepoRoot '.git\hooks'

if (-not (Test-Path $gitHooksDir)) {
    Write-Host "[!] Not a Git repository (missing .git\hooks): $RepoRoot" -ForegroundColor Yellow
    exit 0
}

$hookFile = Join-Path $gitHooksDir 'pre-commit'

$hookScript = @'
#!/bin/sh
# Agent Context Engine (ctx) Pre-Commit Syntax Interceptor
# Bypassed via: git commit -n OR export SKIP_CTX=1

if [ "$SKIP_CTX" = "1" ]; then
    exit 0
fi

echo "[ctx-hook] Intercepting syntax errors via local compiler checks..."

# Check if ctx is available on PATH, otherwise use python engine directly
if command -v ctx >/dev/null 2>&1; then
    ctx check
    EXIT_CODE=$?
else
    python "$HOME/.agent-context-engine/engine.py" check
    EXIT_CODE=$?
fi

if [ $EXIT_CODE -ne 0 ]; then
    echo ""
    echo "\033[1;31m[ctx-hook BLOCKED]\033[0m Staged files contain syntax errors."
    echo "Fix errors above or bypass using: git commit --no-verify"
    exit 1
fi

exit 0
'@

[IO.File]::WriteAllText($hookFile, $hookScript)
Write-Host "[+] Installed pre-commit hook -> $hookFile" -ForegroundColor Green
