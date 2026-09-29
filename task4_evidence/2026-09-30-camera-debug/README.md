# 相机与停车调试

这些是校准记录，不是固定参数的正式 10 次评估。环境见仓库 `TASK4_HANDOFF.md`。
保留失败；`summary.json` 汇总全部已归档记录，参数与出生位置在每次 `result.json`。
距离是结束后独立观测，`terminal.log` 中停车时的 C1/C2/C3 决定任务成功。
例如停车首帧漏检后，独立结束帧重新识别到目标，也不会反向修改该次失败结论。

共同设置：Task 2 原场景、同一个 `dog_front_camera`、垂直 FOV 100°、原相机俯角。
没有使用第三人称图像、物体真值坐标导航、LLM 或人工移动控制。
`reobserve_fix` 指转向后先重新取图；`stopped_frame_retry` 指停止期间最多取三个新帧。
两项布尔值说明运行时的控制器版本；旧结果不因后续代码修复而重新标记。

每条记录都可在团队仓库根目录按以下命令重新运行，使用 JSON 中的参数和**新**输出目录：

```powershell
.\.venv\Scripts\python.exe -u run_task4_trial.py --task2-root ..\task2_runtime\task2 --color green --start 1 1 0 --camera-fovy 100 --stop-box-height 0.97 --final-steps 0 --timeout 180 --gui --hold-open 1800 --output runs\new_trial
```

代码、并行负载和墙钟超时均可能影响轨迹，重跑不是逐帧确定性复现。
GUI 版本显示浏览器实时 MuJoCo 画面；任务完成后保持站立的时间不属于任务评估时间。
切换/关闭浏览器流可能在原 Task 2 HTTP 服务中打印 `ConnectionAbortedError`，它与 `[MISSION]` 失败原因不同。

`camera_probe/` 为单独的静态校准：`source.py` 保存实际执行脚本，`results.json` 和图片保存原始结果。
脚本依次使用距绿椅名义 3、1、0.75 m 的初始位置并站立，改变 FOV 和俯角。
文件名中的距离是名义出生距离，站立后可能有小幅漂移。
脚本的输出路径是历史路径；复现实验时先改为新目录，避免覆盖。
