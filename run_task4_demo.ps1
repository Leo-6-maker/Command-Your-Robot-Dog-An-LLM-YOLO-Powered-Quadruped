param(
    [ValidatePattern('^[a-z0-9_]+$')] [string] $RunId = "demo_$(Get-Date -Format 'yyyyMMdd_HHmmssfff')",
    [double] $StartX = 0,
    [double] $StartY = 0,
    [double] $StartYaw = 0,
    [switch] $RandomStart,
    [int] $Seed
)

$Host.UI.RawUI.WindowTitle = 'EE5112 Task4 Terminal'
if ($RandomStart -and ($PSBoundParameters.ContainsKey('StartX') -or
                       $PSBoundParameters.ContainsKey('StartY') -or
                       $PSBoundParameters.ContainsKey('StartYaw'))) {
    throw 'Choose either -RandomStart or explicit -StartX/-StartY/-StartYaw.'
}
if (-not $RandomStart -and $PSBoundParameters.ContainsKey('Seed')) {
    throw '-Seed requires -RandomStart.'
}
if ($RandomStart) {
    $poses = @(
        @{ X = 0.0; Y = 0.0; Yaw = 0.0 },
        @{ X = 0.0; Y = 0.0; Yaw = 180.0 },
        @{ X = 0.5; Y = 0.4; Yaw = 90.0 },
        @{ X = 0.5; Y = -0.4; Yaw = -90.0 }
    )
    $random = if ($PSBoundParameters.ContainsKey('Seed')) {
        [System.Random]::new($Seed)
    } else {
        [System.Random]::new()
    }
    $selected = $poses[$random.Next($poses.Count)]
    $pose = @($selected.X, $selected.Y, $selected.Yaw)
} else {
    $pose = @($StartX, $StartY, $StartYaw)
}
Write-Host "Task 4 start pose: x=$($pose[0]) y=$($pose[1]) yaw=$($pose[2]) deg; RunId=$RunId"
Write-Host 'After [CHAT] READY, type Go to the red chair. or Go to the green chair.'
& .\.venv\Scripts\python.exe -u -m task3.run `
    --task2-root .\task2 `
    --provider deepseek --model deepseek-chat `
    --gui --dual-view --port 8765 --duration 300 --mission-timeout 180 --start $pose `
    --log-file "runs\task4_demo_$RunId.log"
