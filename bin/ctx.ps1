$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$enginePath = Join-Path (Split-Path -Parent $scriptDir) 'src\engine.py'
& python "$enginePath" @args
