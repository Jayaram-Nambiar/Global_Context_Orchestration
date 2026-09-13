<#
.SYNOPSIS
    Runs the automated unit test suite for the Agent Context Engine.
#>

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot
Write-Host "Running Agent Context Engine test suite..." -ForegroundColor Cyan
python -m unittest discover -s tests -p "test_*.py" -v
if ($LASTEXITCODE -eq 0) {
    Write-Host "`n[✓] All tests passed!" -ForegroundColor Green
} else {
    Write-Host "`n[✗] Test suite failed with exit code $LASTEXITCODE" -ForegroundColor Red
}
exit $LASTEXITCODE
