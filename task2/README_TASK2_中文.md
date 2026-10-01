# EE5112 MiniLab 1.3 — Task 2

这是 Task 2 的实现、实测数据及报告素材。保留课程指定平台的 ONNX 步态、观测和 PD 控制算法，新增文件在 `task2/`。Task 3/4 应直接使用此平台和场景。

## 1. 安装（Linux，Python 3.12 实测）

在本目录打开终端：

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
python -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
python -m pip install -r requirements-task2.txt
```

ONNX 和 YOLO 权重已经包含。无需 API key。使用 CPUExecutionProvider 和 YOLO device=cpu；MuJoCo 仍需要可用的 OpenGL/EGL 驱动。

## 2. 最快运行

```bash
# 原生 MuJoCo 窗口
python -m task2.run
# 浏览器控制界面（手动打开 http://localhost:8765）
MUJOCO_GL=egl python -m task2.run --gui --duration 600
# 自动演示并导出视频：仿真画面+前置相机+同步控制台日志
MUJOCO_GL=egl python -m task2.run --headless --demo --duration 22 --record evidence/Video_Task2.mp4
```

M：排队前进 3 秒；J：左转 90°；K：左转 180°；X：清空队列。浏览器有对应按钮及键盘快捷键；终端可以输入 m/j/k/x 后回车。原生窗口 W/S/A/D/Q/E 为每次按键 0.25 秒脉冲，浏览器为按住移动、松开停止。运动技能执行期间优先使用队列命令。浏览器的 Cancel skills / X 用于中断技能；上游 Stop 按钮仅停止手动命令。

地图下拉框可选择 Race Track、Stairs、Cross Slope，再切回 Task 2 Object Lab。相机下拉框可选择前置、后上方和俯视机载相机。

课程原始 demo 也保留，可运行 `python eg/play.py` 和 `python eg/play.py --gui`。原始原生窗口连续方向键依赖 evdev/设备权限；本次新增程序提供无需修改设备权限的按键脉冲。

## 3. 验证

```bash
MUJOCO_GL=egl python -m task2.verify_scene
MUJOCO_GL=egl python -m task2.evaluate
python -m pytest -q task2/test_skills.py
```

`verify_scene` 在真实仿真运行 2 秒后读取机载 RGB，转换 BGR 后交给 YOLO。必须检测到两把椅子和一个 sports ball，否则以失败退出。`evidence/detections.png` 是实际检测结果，不是人工绘制的标签。场景是原创几何组合：椅子具有座面、靠背、四条腿，篮球具有接缝；不是把普通方块标成椅子。其可检测性已经实测通过，但不保证所有距离、视角均可检测。

`evaluate` 先用 4 秒左转测量参考角速度，再比较 +90/+180/-90 度的开环与闭环。CSV 中误差在停止后 1 秒读取；[TURN] 记录的是控制器结束瞬间误差，两者不能混用。结果证明方向变化时固定计时不可靠，不代表闭环在每个条件下都优于已校准的开环。

## 4. 交接给 Task 3 / Task 4

```python
from task2.platform import Platform
p = Platform()
# 可在独立命令线程调用，立即返回，不阻塞仿真：
p.skills.move(0.5, 0, 0, 3.0)
p.skills.turn(180)
# 以下循环由唯一仿真线程持续运行：
while running:
    p.step()
    frame = p.camera.latest()  # None，或 CameraFrame(rgb, sim_time, sequence)
    # perception 线程只读取 latest()，按 sequence 去重。
p.close()
```

速度为 [-1,1] 的归一化命令，不是实测 m/s 或 rad/s；+vx 前、+vy 左、+wz 逆时针。角度单位为度。队列空闲返回零速度，但保持站立策略/PD。`p.skills.busy` 表示是否还有动作；`p.skills.results` 保存转向状态，Task 3 在结果为 FAIL 时应中止任务，不应打印成功。[TURN] 同时包含 status。

Task 4 可以连续排入短时间 `move` 指令实现视觉控制，但不得积压长队列；调整方向前可用 `stop()` 取消剩余动作。`task2/assets/objects.json` 只允许用于距离日志及评估，不能用于导航方向计算。摄像头固定在 trunk，唯一视觉入口为 `p.camera.latest()`，返回复制的 RGB uint8 数组，640×480，10 Hz **仿真时间**。渲染速度慢时仿真会慢于实时，不能把此频率称为已测得的墙钟 10 Hz。

## 5. 文件和提交

- `task2/skills.py`：带锁的队列、基于仿真时间的 move、累计实际 yaw 的 turn。
- `task2/platform.py`：复用原始策略、重排、观测、PD，连接技能和相机。
- `task2/camera.py`：机载 RGB 帧缓存。
- `task2/assets/scene.xml`、`objects.json`：场景与真值物体中心。
- `task2/run.py`：原生/浏览器/无窗口演示及视频输出。
- `task2/verify_scene.py`、`evaluate.py`、`test_skills.py`：实测工具。
- `evidence/`：仓库保留检测图与数值表；完整运行日志和视频仅保存在本地。
- `Task2_Report.md`：英文报告章节，合并到小组报告；生成的 PDF 不提交 Git。

视频由仿真离屏渲染生成，底部是同次执行产生的同步日志面板，并非桌面终端录屏。为严格满足题目“终端可见”，提交前请运行 `--gui`，把终端和浏览器并排，按 M、K 录制一遍桌面；看到 [TURN] SUCCESS 后结束录制。原生窗口已启动测试，浏览器地图/键盘/相机接口另有日志。不要将接口测试写成你本人已经手动演示。

请填写 Student A 的真实姓名、学号及实际贡献，并与队友合并 Task 1/3/4/5。此压缩包仅为 Task 2，不能冒充完整小组提交。报告中的 AI Usage Declaration 需要按你实际使用情况确认。所有新增源码头部标记了 Student A。

## 6. 来源

- 课程平台：https://github.com/aoqianz/quadruped_mujoco ，commit `dd40180f1121a66373d261e64a9a09eb69b1b2a7`。
- MuJoCo：https://mujoco.readthedocs.io/
- Ultralytics YOLO：https://docs.ultralytics.com/ ，YOLO11n COCO 权重。
- 具体检测输出和转向结果由随包脚本生成；新场景几何是原创，无外部网格下载依赖。

报告重新生成（可选）：安装 `reportlab`，运行 `python -m task2.create_report`。Linux 下优先嵌入 Liberation Serif（Times New Roman 的兼容替代字体）。
