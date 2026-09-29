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
