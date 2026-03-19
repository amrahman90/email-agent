# Email Agent - Windows Runner Script
#
# Usage: .\scripts\run_windows.ps1 [arguments]
#
# Runs the email-agent with uv, capturing output to email-agent.log.
# All command-line arguments are passed through to the agent.
#
# Example:
#   .\scripts\run_windows.ps1 --once --verbose
#   .\scripts\run_windows.ps1 --dry-run

param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Arguments
)

$ErrorActionPreference = "Stop"

# Detect script directory (resolve symlinks)
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $ScriptDir) {
    $ScriptDir = $PSScriptRoot
}
$ProjectRoot = (Resolve-Path (Join-Path $ScriptDir "..")).Path

Write-Host "Email Agent - Windows Runner" -ForegroundColor Cyan
Write-Host "Project root: $ProjectRoot"
Write-Host ""

# Change to project root
Set-Location $ProjectRoot

# Build the command
$PythonCmd = "python"
$ModuleArgs = "-m email_agent"

if ($Arguments.Count -gt 0) {
    $ModuleArgs = "$ModuleArgs $($Arguments -join ' ')"
    Write-Host "Running: uv run $PythonCmd $ModuleArgs" -ForegroundColor Yellow
} else {
    Write-Host "Running: uv run $PythonCmd $ModuleArgs" -ForegroundColor Yellow
    Write-Host "(Press Ctrl+C to stop)" -ForegroundColor Gray
}

Write-Host ""

# Run with uv, tee output to console and log file
$LogFile = Join-Path $ProjectRoot "email-agent.log"

try {
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = "uv"
    $psi.Arguments = "run $PythonCmd $ModuleArgs"
    $psi.WorkingDirectory = $ProjectRoot
    $psi.UseShellExecute = $false
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.CreateNoWindow = $true

    $process = New-Object System.Diagnostics.Process
    $process.StartInfo = $psi

    $process.Start() | Out-Null

    # Stream output to console and log file
    $logStream = [System.IO.File]::OpenWrite($LogFile)
    $logWriter = New-Object System.IO.StreamWriter($logStream)

    # Copy stdout asynchronously
    $stdoutTask = $process.StandardOutput.ReadToEndAsync()
    $stderrTask = $process.StandardError.ReadToEndAsync()

    # Wait for process to complete while streaming
    while (-not $process.HasExited) {
        Start-Sleep -Milliseconds 100
    }

    # Get remaining output
    $stdout = $stdoutTask.Result
    $stderr = $stderrTask.Result

    if ($stdout) {
        $logWriter.Write($stdout)
        $stdout
    }

    if ($stderr) {
        $logWriter.Write($stderr)
        $stderr | Write-Host -ForegroundColor Red
    }

    $logWriter.Close()
    $logStream.Close()

    Write-Host ""
    Write-Host "Exit code: $($process.ExitCode)" -ForegroundColor $(if ($process.ExitCode -eq 0) { "Green" } else { "Red" })
    Write-Host "Log file: $LogFile" -ForegroundColor Gray

    exit $process.ExitCode
}
catch {
    Write-Host "ERROR: Failed to run email-agent: $_" -ForegroundColor Red
    Write-Host ""
    Write-Host "Make sure uv is installed: https://github.com/astral-sh/uv" -ForegroundColor Yellow
    exit 1
}
