param(
    [ValidatePattern('^[a-z0-9_]+$')] [string] $RunId = "demo_$(Get-Date -Format 'yyyyMMdd_HHmmssfff')"
)

Write-Host 'After [CHAT] READY, type: Move forward at speed 0.4 for one second, then turn left 45 degrees.'
Write-Host 'After [DONE] status=SUCCESS actions=2, type: Write a poem about robot dogs.'
& .\.venv\Scripts\python.exe -u -m task3.run `
    --task2-root ..\task2_runtime\task2 `
    --provider deepseek --model deepseek-chat `
    --gui --port 8765 --duration 300 `
    --log-file "runs\task3_demo_$RunId.log"
