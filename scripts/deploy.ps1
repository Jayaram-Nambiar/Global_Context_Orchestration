<#
.SYNOPSIS
    Deploys the Agent Context Engine globally to the host machine.
.DESCRIPTION
    Installs engine.py, mcp_server.py, and shell launchers into ~/.agent-context-engine,
    creates PATH shims, configures the MCP server across Antigravity, Cursor, Claude,
    and OpenCode, and verifies/injects behavioral rulesets.
#>

[CmdletBinding()]
param(
    [switch]$SkipRules,
    [switch]$SkipMCP
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$engineSource = Join-Path $repoRoot 'src\engine.py'
$mcpSource = Join-Path $repoRoot 'src\mcp_server.py'
$engineDir = Join-Path $HOME '.agent-context-engine'

Write-Host "`n=== Agent Context Engine Global Deployment ===" -ForegroundColor Cyan

# 1. Target Directory Creation
if (-not (Test-Path $engineDir)) {
    New-Item -ItemType Directory -Path $engineDir -Force | Out-Null
    Write-Host "[+] Created target engine directory: $engineDir" -ForegroundColor Green
} else {
    Write-Host "[*] Engine directory exists: $engineDir" -ForegroundColor Gray
}

# 2. Deploy engine.py and mcp_server.py
Copy-Item -Path $engineSource -Destination (Join-Path $engineDir 'engine.py') -Force
Write-Host "[+] Installed engine.py -> $engineDir\engine.py" -ForegroundColor Green

Copy-Item -Path $mcpSource -Destination (Join-Path $engineDir 'mcp_server.py') -Force
Write-Host "[+] Installed mcp_server.py -> $engineDir\mcp_server.py" -ForegroundColor Green

# 3. Create Launchers in ~/.agent-context-engine
$cmdLauncher = "@echo off`r`npython `"%USERPROFILE%\.agent-context-engine\engine.py`" %*`r`n"
[IO.File]::WriteAllText((Join-Path $engineDir 'ctx.cmd'), $cmdLauncher)

$ps1Launcher = "& python `"`$HOME\.agent-context-engine\engine.py`" @args`r`n"
[IO.File]::WriteAllText((Join-Path $engineDir 'ctx.ps1'), $ps1Launcher)

$bashLauncher = "#!/usr/bin/env bash`npython `"`$HOME/.agent-context-engine/engine.py`" `"`$@`"`n"
[IO.File]::WriteAllText((Join-Path $engineDir 'ctx'), $bashLauncher)

Write-Host "[+] Created shell launchers (ctx.cmd, ctx.ps1, ctx)" -ForegroundColor Green

# 4. PATH Shim Integration (Scoop / User PATH)
$shimsDir = Join-Path $HOME 'scoop\shims'
if (Test-Path $shimsDir) {
    Copy-Item -Path (Join-Path $engineDir 'ctx.cmd') -Destination (Join-Path $shimsDir 'ctx.cmd') -Force
    Copy-Item -Path (Join-Path $engineDir 'ctx.ps1') -Destination (Join-Path $shimsDir 'ctx.ps1') -Force
    Write-Host "[+] Synchronized shims to $shimsDir" -ForegroundColor Green
}

$userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
if ($userPath -notmatch [regex]::Escape($engineDir)) {
    $newUserPath = "$userPath;$engineDir"
    [Environment]::SetEnvironmentVariable('Path', $newUserPath, 'User')
    Write-Host "[+] Added $engineDir to User PATH" -ForegroundColor Green
} else {
    Write-Host "[*] User PATH already includes $engineDir" -ForegroundColor Gray
}

# 5. Model Context Protocol (MCP) Cross-Editor Configuration
if (-not $SkipMCP) {
    & python (Join-Path $engineDir 'mcp_server.py') --install
}

# 6. Global Rules Injection
if (-not $SkipRules) {
    Write-Host "`n[*] Verifying Global Editor Rulesets..." -ForegroundColor Cyan

    $sectionBlock = @"

---

## 8. Agent Context Engine & Token Optimization Protocol

To minimize LLM token consumption and prevent context exhaustion/hallucination loops:
- **Map Before Read (`ctx map`)**: ALWAYS run `ctx map` via terminal tools before inspecting or editing files. Consult `.agent-context.json` to identify function signatures, classes, and cross-boundary hooks without dumping raw file bodies.
- **Surgical Line-Range Slicing**: NEVER dump or read full files exceeding 150 lines. Rely strictly on line-range slicing (`ctx slice <file> <start> <end>` or line-bounded tool reads) targeting only the specific functions/blocks needed.
- **Pre-Completion Syntax Interception (`ctx check`)**: ALWAYS execute `ctx check` automatically after code updates. Intercept compilation and syntax errors locally before returning to the user or claiming completion.
"@

    $targetProfiles = @(
        (Join-Path $HOME '.gemini\config\rules\global-guidelines.md'),
        (Join-Path $HOME '.cursorrules'),
        (Join-Path $HOME '.cursor\rules\global-rules.mdc'),
        (Join-Path $HOME '.config\opencode\AGENTS.md')
    )

    foreach ($profile in $targetProfiles) {
        if (Test-Path $profile) {
            $content = [IO.File]::ReadAllText($profile)
            if ($content -notmatch 'Agent Context Engine & Token Optimization Protocol') {
                $newContent = $content.TrimEnd() + "`r`n" + $sectionBlock + "`r`n"
                [IO.File]::WriteAllText($profile, $newContent)
                Write-Host "[+] Injected rules into: $profile" -ForegroundColor Green
            } else {
                Write-Host "[*] Profile already configured: $profile" -ForegroundColor Gray
            }
        }
    }
}

Write-Host "`n[+] Deployment Successful! Verify via: ctx --help or ctx mcp" -ForegroundColor Green
