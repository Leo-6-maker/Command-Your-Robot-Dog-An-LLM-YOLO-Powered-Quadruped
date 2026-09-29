param(
    [ValidateSet('green','red')] [string] $Color,
    [ValidatePattern('^[a-z0-9_]+$')] [string] $RunId
)

$ErrorActionPreference = 'Stop'
$workspace = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $workspace
$trialLog = Join-Path $workspace "runs\task4_demo_$RunId.log"
$video = Join-Path $workspace "task4_evidence\video_clip_$RunId.mp4"
$stopFile = Join-Path $workspace "runs\stop_record_$RunId.flag"
if ((Test-Path $trialLog) -or (Test-Path $video) -or (Test-Path $stopFile)) {
    throw "RunId already exists: $RunId"
}

$terminal = Start-Process powershell.exe -WindowStyle Normal -PassThru `
    -WorkingDirectory $workspace -ArgumentList @(
        '-NoExit', '-ExecutionPolicy', 'Bypass', '-File',
        (Join-Path $workspace 'run_task4_demo.ps1'), '-Color', $Color,
        '-RunId', $RunId)
$readyUntil = (Get-Date).AddSeconds(45)
while ((Get-Date) -lt $readyUntil) {
    if ((Test-Path $trialLog) -and
        (Select-String -Path $trialLog -Pattern '[CHAT] event=READY' -SimpleMatch -Quiet)) {
        break
    }
    Start-Sleep -Milliseconds 500
}
if ((Get-Date) -ge $readyUntil) { throw 'Task 3 chat did not become ready' }
& .\.venv\Scripts\python.exe type_task4_demo_command.py arrange

$recorder = Start-Process -FilePath (Join-Path $workspace '.venv\Scripts\python.exe') `
    -ArgumentList @('record_task4_desktop.py', $video, '--stop-file',
                    $stopFile, '--max-seconds', '240') `
    -WorkingDirectory $workspace -WindowStyle Hidden -PassThru `
    -RedirectStandardOutput (Join-Path $workspace "runs\record_$RunId.log") `
    -RedirectStandardError (Join-Path $workspace "runs\record_$RunId.err")
try {
    Start-Sleep -Seconds 3
    & .\.venv\Scripts\python.exe type_task4_demo_command.py $Color
    $missionUntil = (Get-Date).AddSeconds(215)
    $mission = 'NO_RESULT'
    while ((Get-Date) -lt $missionUntil) {
        if (Select-String -Path $trialLog -Pattern '[MISSION] status=SUCCESS' -SimpleMatch -Quiet) {
            $mission = 'SUCCESS'; break
        }
        if (Select-String -Path $trialLog -Pattern '[MISSION] status=FAIL' -SimpleMatch -Quiet) {
            $mission = 'FAIL'; break
        }
        Start-Sleep -Seconds 1
    }
    Start-Sleep -Seconds 4
    & .\.venv\Scripts\python.exe type_task4_demo_command.py quit
    Start-Sleep -Seconds 4
    Write-Output "[VIDEO] run=$RunId mission=$mission terminal=$trialLog video=$video"
} finally {
    New-Item -ItemType File -Path $stopFile | Out-Null
    $recorder.WaitForExit(30000) | Out-Null
}
