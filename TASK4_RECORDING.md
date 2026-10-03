# Task 4 最终录制步骤（Group 3）

最终保存为 `video/Video_Task4.mp4`。同一段视频展示隐藏红椅和绿椅；两张同类别、不同颜色的椅子证明颜色消歧。选用固定十次试验中的成功起点，运行结果仍须以当次日志为准。

## 1. 准备环境和画面

在 PowerShell 中执行：

```powershell
cd 'D:\Users\NUS-courses\EE5112_minilab\team_repo'
.\.venv\Scripts\python.exe -m pip install -r .\task3\requirements-task3.txt
Test-Path Env:DEEPSEEK_API_KEY
```

最后一行应为 `True`，只检查是否存在，不显示密钥。如为 `False`，在同一终端使用以下隐藏输入设置你已有的 DeepSeek 密钥（不要录下设置过程）：

```powershell
$demoApiSecret = Read-Host 'DeepSeek API key' -AsSecureString
$env:DEEPSEEK_API_KEY = [System.Net.NetworkCredential]::new('', $demoApiSecret).Password
Remove-Variable demoApiSecret
```

关闭之前的仿真，避免占用端口。用 OBS 的“显示器采集”录制同一屏幕；左侧浏览器，右侧终端，两者始终可见。输出建议 1920×1080、30 fps，终端字体调到回放时可读；需要配音时启用麦克风。OBS 录制与声音配置见[官方快速指南](https://obsproject.com/kb/quick-start-guide)。可先用 MKV 录制，再通过“文件 → 录像转封装”转为 MP4。

## 2. 演示 A：红椅最初在身后

执行（自动生成新 RunId，避免旧日志冲突）：

```powershell
.\run_task4_demo.ps1 -StartX 1 -StartY -1 -StartYaw 180
```

打开 `http://127.0.0.1:8766/`，上方为后上方视角，下方为带检测框的机载相机。等终端出现 `[CHAT] event=READY`。确认机载画面最初看不到红椅，再开始录制。

在终端**手动输入并回车**：

```text
Go to the red chair.
```

配音示例：“目标红色椅子最初不在机载相机视野内。语言模型把命令解析为目标动作，机器人通过转向搜索、视觉对准和短步前进自主接近。”

执行期间不按浏览器 W/A/S/D/Q/E，不使用遥控。观察 `[CMD]` → `[SEARCH]`/`[DETECT]` → `[FOUND]` → `[MISSION] status=SUCCESS` → `[DONE] status=SUCCESS`。`[FOUND]` 中距离须不超过 0.80 m。成功后保留画面和日志 3–5 秒。

## 3. 演示 B：寻找绿椅，区分同类不同颜色

第一条任务完成后输入：

```text
/quit
```

等待程序返回 PowerShell 提示符，再执行：

```powershell
.\run_task4_demo.ps1 -StartX 1 -StartY 1 -StartYaw 0
```

重启间隙可暂停 OBS 录制；不要在任务执行过程中剪掉搜索、停步或失败过程。重新打开/刷新 `http://127.0.0.1:8766/`，等 READY，然后继续录制并输入：

```text
Go to the green chair.
```

配音示例：“场景中有两张椅子。YOLO 提供类别和检测框，框内颜色分析区分红椅与绿椅。本次只接近绿色目标；停止时还需满足实时检测、躯干距离和 FOUND 日志三项条件。”

等绿椅 `[FOUND]`、`[MISSION] status=SUCCESS` 和 `[DONE] status=SUCCESS` 出现，保留 3–5 秒，然后**先停止录制**，再退出仿真。输出/转封装为 `video/Video_Task4.mp4`。

如果任务 FAIL，保留日志诊断，并退出仿真后以相同起点重新录制；不能把失败的终端输出改成成功。最终演示可以选用成功录像，报告的十次固定评估及失败率仍保持不变。

## 4. 最终回放检查

- 两条英文命令输入过程清楚可见；终端在两次任务全过程中始终可见。
- 红椅最初不可见，有自主搜索过程；绿椅任务证明颜色区分。
- 两次均有正确目标 `[DETECT]`、`[FOUND] d<=0.80 m`、`[MISSION] status=SUCCESS`，无物体接触。
- 第一人称图像、YOLO 框和机器人移动可见；没有人工操纵运动。
- 配音不遮盖日志，任务开始前没有显示密钥。

录制工具 `record_task4_desktop.py` 只能生成无声桌面视频；需要本人配音时直接用 OBS。完成后可运行下面的本地打包命令（不会上传视频）：

```powershell
py -3.12 render_group_report.py --final
py -3.12 prepare_submission.py 3 --report .\GROUP_REPORT.pdf --video-task2 .\video\Video_Task2.mp4 --video-task3 .\video\Video_Task3_reviewed.mp4 --video-task4 .\video\Video_Task4.mp4 --video-bonus .\video\Video_bonus.mp4
```

该命令只打包 Git 已跟踪的源文件，所以正式打包前要先把本次确认后的源代码/文档变更加入 Git；视频和 PDF 保持本地。若同名 ZIP 已存在，脚本会拒绝覆盖，请先人工保留或改名旧 ZIP。
