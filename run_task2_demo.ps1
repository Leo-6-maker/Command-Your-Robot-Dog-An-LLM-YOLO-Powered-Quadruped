Write-Host 'Keep this terminal visible in the recording. Open http://127.0.0.1:8765.'
Write-Host 'Show the object scene and dog_front_camera, then type m and k here.'
$python = (Resolve-Path .\.venv\Scripts\python.exe).Path
Push-Location ..\task2_runtime\task2
try {
    & $python -u -m task2.run --gui --duration 600
} finally {
    Pop-Location
}
