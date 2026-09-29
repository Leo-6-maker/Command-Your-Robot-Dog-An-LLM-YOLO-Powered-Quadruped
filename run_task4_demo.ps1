param(
    [ValidateSet('green','red')] [string] $Color = 'red',
    [ValidatePattern('^[a-z0-9_]+$')] [string] $RunId = 'demo'
)

$Host.UI.RawUI.WindowTitle = 'EE5112 Task4 Terminal'
if ($Color -eq 'red') {
    $pose = @(1, -1, 180)
} else {
    $pose = @(1, 1, 0)
}
Write-Host "Task 4: type Go to the $Color chair. after [CHAT] READY"
& .\.venv\Scripts\python.exe -u -m task3.run `
    --task2-root ..\task2_runtime\task2 `
    --provider deepseek --model deepseek-chat `
    --gui --port 8765 --duration 300 --mission-timeout 180 --start $pose `
    2>&1 | Tee-Object -FilePath "runs\task4_demo_$RunId.log"
