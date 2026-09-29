# Task 4 接手记录（2026-09-30）

已接收团队 main 的 `1c8f0fb`。Task 2 的运行源码在 ZIP 内，Task 3 已实现
相机快照、阻塞运动适配、LLM 命令派发。继续复用它们。

## 本机运行

仓库：`D:\Users\NUS-courses\EE5112_minilab\team_repo`

Task 2 ZIP 已完整解压到相邻目录 `..\task2_runtime\task2`，没有覆盖团队仓库文件。
`--task2-root` 必须指向包含 `task2/platform.py`、`eg/`、`src/` 的运行项目根目录，
不能指向仅包含 ZIP 和报告的仓库 `task2/` 目录。

本机 `.venv` 使用 Python 3.12 并复用 Anaconda 的已装包；补装的 MuJoCo、ONNX Runtime
仅在 `.venv` 内。实跑版本为 MuJoCo 3.14.0、ONNX Runtime 1.30.0、
Ultralytics 8.3.111、PyTorch 2.6.0+cpu、NumPy 2.5.2、Pillow 10.4.0。
这与队友打包的参考环境不同；不能把本机结果当作对其原环境的完全复现。

在团队仓库根目录运行（PowerShell）：

```powershell
# 平台和相机启动检查，不调用 LLM
.\.venv\Scripts\python.exe -m task3.run --task2-root ..\task2_runtime\task2 --headless --no-chat --duration 2

# Task 4 实机仿真试验：目标已结构化指定，不调用 LLM
# output 必须是新目录，防止覆盖已有记录
.\.venv\Scripts\python.exe -u run_task4_trial.py --task2-root ..\task2_runtime\task2 --color green --output runs\green_next

# 目标初始不在视野：仅改变机器人出生朝向，使用同一个场景
.\.venv\Scripts\python.exe -u run_task4_trial.py --task2-root ..\task2_runtime\task2 --start 0 0 180 --output runs\hidden_next

# 最终英文聊天入口，需要本机已有 Ollama 服务和对应模型；本轮未验证该服务
.\.venv\Scripts\python.exe -m task3.run --task2-root ..\task2_runtime\task2 --gui --provider ollama --model qwen2.5:7b --duration 600
```

试验脚本保留唯一仿真线程，在工作线程执行 `goto_object`。输出初始/结束 RGB 和标注图、
控制器最后一次读取的原始帧、`result.json`；终端打印检测、技能和任务日志。
60 秒超时使用墙钟，`[FOUND] t` 使用仿真时间。
`final_distance_m` 是独立的任务结束后观测值，可能与控制器停止瞬间日志略有差别。
接触记录只用于评估，不参与导航。它不替代 Task 3 英文输入和终端可见的视频。

## 本轮修正与检查

- 恢复 C1：最后前进结束并停止后，必须从新帧重新检测到目标类别和颜色，才查询 C2 距离。
- 每个动作完成后丢弃已缓存相机帧，避免读取动作期间的旧帧。
- 优先选择高置信度匹配框。首次试跑发现“取最大框”会被包含背景的重复框误导；
  后续实跑说明仅改置信度仍不足以解决所有近距离误检。
- 新增停车后目标消失/颜色不匹配、缓存帧和重复框回归检查。
- 本机 Task 3 测试：`106 passed`；平台真实运行 2 秒仿真时间通过；真实 CPU YOLO 可识别起点的两把椅子。

## 调试证据，不是正式 10 次评估

原始日志、JSON 和图片在 [task4_evidence/2026-09-30](task4_evidence/2026-09-30/)。
这些试跑改变了选择策略、出生位姿或末段步数，不能合并成同一固定配置的成功率。
所有运行均使用原始 Task 2 场景和 `dog_front_camera`，未检测到物体接触。

| 记录 | 目标/出生位姿 x,y,yaw | 末段步数 | 结束后距离 m | 失败原因 |
|---|---|---:|---:|---|
| green_01 | 绿椅 / 0,0,0 | 7 | 0.907 | C2 距离过大；仍使用最大框选择 |
| green_02 | 绿椅 / 0,0,0 | 7 | 0.943 | C1 停车帧无匹配检测 |
| red_01 | 红椅 / 0,0,0 | 7 | 0.938 | C2 距离过大 |
| hidden_green_01 | 绿椅 / 0,0,180 | 7 | 0.825 | 已旋转搜索到目标；C1 停车帧无匹配检测 |
| red_02 | 红椅 / 0,0,0 | 11 | 0.627 | C2 范围内，但 C1 停车帧无匹配检测 |
| green_aligned_01 | 绿椅 / 1,1,0 | 11 | 0.773 | C2 范围内，但 C1 停车帧无匹配检测 |

前五次记录早于“保存最后控制器帧”功能，所以该额外图片只在 `green_aligned_01` 中。
所有失败都保留，不将场景真值距离作为到达成功的唯一证据。
旧的 `task3/evidence/step11_task4_integration.md` 是队友原始记录；其中略过停车重新识别的
0.69 m 成功日志不构成完整的 C1-C3 证据，本轮没有覆盖该历史文件。

## 下一步

1. 处理近距离椅子裁切和重复框，验证停车时仍能识别。若调整机载相机参数，必须在
   共用 Task 2 平台中统一配置并记录，再检查起点与近距离的检测；继续只用机载图像控制。
2. 稳定后固定参数，再开展至少 10 次正式试验，记录检测、颜色 grounding、成功率、距离和失败分析。
3. 最后用 Task 3 的真实英文命令录制终端与仿真同时可见的视频，覆盖同类颜色区分和初始不可见目标。

当前状态：接收、实际运行及判定修复完成；Task 4 导航验收仍未完成。

## 实时画面与相机调试（2026-09-30 续）

试验入口新增浏览器显示和相机 FOV 参数。运行后打开 <http://localhost:8765>，
Camera 下拉框可切换第三人称与 `dog_front_camera`；导航始终使用后者。
这是实际 MuJoCo 状态的实时渲染。观察时不要操作运动按键或场景重置，否则试验会受到人工干预。

```powershell
# 校准用参数，不是已冻结的正式配置；output 每次换一个新目录
.\.venv\Scripts\python.exe -u run_task4_trial.py --task2-root ..\task2_runtime\task2 --gui --start 1 1 0 --camera-fovy 100 --stop-box-height 0.97 --final-steps 4 --timeout 180 --start-delay 10 --hold-open 1800 --output runs\visual_next

# 在 IDE 终端查看本轮代理实跑日志（并行试跑日志可能交错，独立日志在各记录中）
Get-Content .\runs\live_debug.log -Tail 30 -Wait
```

`--start-delay` 是运动前预留观看时间；`--hold-open` 是结束后继续显示的墙钟秒数。
退出用页面的 Close Page。仅关闭浏览器标签不会立即退出仿真进程。
日志中的 `[VIEW] Trial finished` 表示任务结束后站立；此时画面仍实时更新，但没有新的导航任务。

### 本轮定位的原因

1. **近距离裁切**：相同位置约 0.75 m，原 80° 俯视相机未识别绿椅；100° 原俯角识别置信度约 0.69。
   110°/120° 水平相机近处表现改善，却会在远处漏检，不能只看停车截图选参数。
2. **转向后沿用旧框**：大框触发停车时，旧代码先转向再直接进入末段/停车。
   已改为先对齐、获取新帧，再判断停车；共享 `goto_object` 的所有入口均得到修复。
3. **停车瞬间漏检**：一次绿椅结束后距离 0.788 m，停车首帧没有匹配，随后又识别到。
   已改为停止期间最多等待三个新帧；无匹配仍失败，C2 只使用通过 C1 的同一快照。
4. **搜索耗时**：远处间歇漏检触发反复 30° 搜索与重新对齐。红椅原点出发的一次试跑在 120 秒墙钟超时，仍距 0.988 m。
5. **高度阈值不稳定**：100°、高度阈值 0.97 在正对绿椅时成功一次，但其他路线停在 0.823 m，红椅正对路线为 0.801 m。
   0.99 也不能独立解决斜视框和漏检问题，未选用该阈值作为候选默认值。

最新 `live_green_terminal4_01` 使用修复后的控制器、100°、0.97、4 个末段短步，
从 `(1, 1, 0°)` 出发，停车实时检测通过，`[FOUND] d=0.74 m`，无物体接触，成功。
同参数 `red_terminal4_01` 从 `(1, -1, 0°)` 出发也通过，`[FOUND] d=0.76 m`，无物体接触。
这组候选参数已统一到 `task4.py`、试验入口和 `task3.run` 的机载相机设置。
末段仍是固定短步校准，并非每一步都重新检测；只通过两条正对路线不能证明能推广到全部起点。

原始数据在 [camera-debug](task4_evidence/2026-09-30-camera-debug/summary.json)，
每项保留 `result.json`、图像与 `terminal.log`。`camera_probe` 为静态相机扫描，
其中设置出生位置仅用于校准评估，不用于导航控制。
`final_distance_m` 为任务后独立快照；最终验收以停车时 `[FOUND]` 和同帧 C1/C2 为准。
新增两个回归检查，完整 Task 3 测试为 `108 passed`。
同时修复试验脚本取消状态被工作线程异常覆盖的问题：现在用主线程独立的退出原因，
超时/关闭后直接保存失败结果，不再等待已经关闭的桥接器发布图像。
历史 `live_red_reobserve_099` 触发此问题，随后手动结束进程；只保留原始日志和图片，
没有补造最终距离或接触结果。

这批是改变参数/代码的调试记录，不能计算固定配置正式成功率。
下一步使用这组候选参数完成至少 10 次不同起点评估，优先原点、斜向、初始不可见目标，
确认搜索耗时、近距离识别与末段裕量后，再录真实英文指令视频。
