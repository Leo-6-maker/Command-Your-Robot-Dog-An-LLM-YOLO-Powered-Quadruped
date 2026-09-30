# Task 3 — LLM command planning

本目录目前完成动作 JSON 协议、本地验证器、Task 2 非阻塞动作队列的阻塞适配器、串行动作执行器、OpenAI Structured Outputs 与本地 Ollama/Qwen 规划器，以及异步终端 chat loop。

## 动作协议

LLM 只能生成四种动作：

- `move(vx, vy, wz, duration_s)`：归一化速度均为 `[-1, 1]`，持续时间为 `(0, 60]` 秒；
- `turn(angle_deg)`：基于 Task 2 闭环转向，范围为 `[-720, 720]` 度且不能为零；
- `goto_object(class, color)`：当前 Task 4 只支持 `red chair` 和 `green chair`；
- `stop`：停止并清空动作队列；为避免停止后又继续运动，它必须是计划中的唯一动作。

一份合法的多步计划示例：

```json
{
  "accepted": true,
  "message": "Moving forward, then turning left.",
  "actions": [
    {"type": "move", "vx": 0.5, "vy": 0.0, "wz": 0.0, "duration_s": 3.0},
    {"type": "turn", "angle_deg": 90.0}
  ]
}
```

拒绝无关、非英文或不安全命令时，`accepted` 必须为 `false`，且 `actions` 必须为空：

```json
{
  "accepted": false,
  "message": "Please enter a safe English robot command.",
  "actions": []
}
```

`action_plan.schema.json` 用于 LLM Structured Outputs；`validator.py` 是独立的本地安全检查。即使云端返回符合 JSON Schema 的结果，执行前仍必须调用本地验证器。

## Task 2 动作适配器

Task 2 的 `p.skills.move()` 和 `p.skills.turn()` 只负责把动作放进队列，调用后会立即返回。Task 3 的执行器需要知道每一步何时真正结束，因此使用阻塞适配器：

```python
from task3.task2_adapter import Task2MotionAdapter

adapter = Task2MotionAdapter(platform)

# 只能在 Task 3 命令工作线程调用；MuJoCo 主线程必须持续 platform.step()。
adapter.move(0.5, 0.0, 0.0, 3.0)
turn_result = adapter.turn(90.0)
```

适配器会：

- 拒绝和已经存在的 Task 2 动作队列混合；
- 等待动作真正完成，而不是仅等待入队；
- 检查闭环转向的 `SUCCESS` / `FAIL` 结果；
- 在墙钟超时后清空队列；
- 把其他线程调用的 `stop()` 识别为取消，而不是误报成功。

## 动作执行器

`PlanExecutor` 只接收 Validator 返回的 `CommandPlan`，按顺序把动作交给 Adapter：

```python
from task3.executor import PlanExecutor

executor = PlanExecutor(adapter, logger=print)
result = executor.execute(validated_plan)  # 在 Task 3 工作线程调用
```

每一步开始和结束都会打印 `[EXEC]`；整份计划最终打印一次 `[DONE]`。任意一步失败都会立即调用 `stop()`、跳过剩余动作并返回 `ExecutionResult(status="FAIL", ...)`。另一个线程可以调用 `executor.cancel()` 中断当前计划。

`goto_object` 通过构造函数注入；完整运行入口会连接现有 Task 4：

```python
executor = PlanExecutor(adapter, goto_object=task4_callback)
```

## LLM 与终端 chat loop

终端 chat loop 是完整入口；LLM 是它内部把英文句子转换成动作 JSON 的环节：

```text
terminal → OpenAIPlanner / OllamaPlanner → local validator → PlanExecutor → Task 2
```

先在当前终端临时设置 API key（不要写进代码或提交到 Git）：

```bash
export OPENAI_API_KEY="your-key-here"
```

如果密钥已保存在仓库外的本机配置文件，可以在启动前加载：

```bash
source "$HOME/.config/ee5112/task3.env"
```

然后在未来的仿真入口中创建 chat loop：

```python
import threading
from task3.chat_loop import build_openai_chat_loop

chat = build_openai_chat_loop(executor)
threading.Thread(target=chat.run, daemon=True).start()

# 主线程继续运行 MuJoCo / platform.step()，不能在这里等待 LLM。
```

每条普通指令会在独立 worker 中依次完成 LLM、验证和执行。运行期间可输入：

- `/status`：查看当前是否忙碌；
- `/stop`：立即取消当前计划并清空 Task 2 动作；
- `/help`：显示本地控制命令；
- `/quit`：停止并退出终端循环。

只有执行成功的计划会成为下一句的上下文，因此 `Do that again slower` 可以引用上一次成功动作。OpenAI 和 Ollama 请求都记录供应商、模型、延迟和 token 数，后续可直接用于两种 LLM 的实验对比。

## 本地 Qwen（Ollama）

本机 Windows 没有队友 Linux 上的 Ollama 服务时，也可用已有的
`DEEPSEEK_API_KEY` 调用真实文本 LLM。新增 `--provider deepseek` 走
OpenAI 兼容 Chat Completions 的 JSON 模式，沿用本目录同一份 prompt、
`parse_and_validate`、`PlanExecutor` 和 Task 4 回调；密钥仅从环境变量读取。
统一演示入口（默认从场地中央出发）：

```powershell
.\run_task4_demo.ps1
```

出现 `[CHAT] event=READY` 后，在同一个终端输入英文
`Go to the red chair.` 或 `Go to the green chair.`；目标由指令决定。
随机起点可用 `.\run_task4_demo.ps1 -RandomStart -Seed 42`（相同种子复现同一候选起点），
手工起点可用 `.\run_task4_demo.ps1 -StartX 0 -StartY 0 -StartYaw 180`。
随机起点用于探索，尚未纳入固定十次评估；物品位置仍是 Task 2 的固定共享场景。
从仓库根目录运行。
脚本会打开 `http://127.0.0.1:8766/`：上方固定选择后上方跟拍，
下方显示 Task 4 真正读取的 `dog_front_camera`。把浏览器放在屏幕左侧、
终端放在右侧，开始你自己的屏幕录制后再输入指令。录制结束前在终端
确认出现 `[FOUND]` 和 `[MISSION] status=SUCCESS`，然后输入 `/quit`。
不传 `-RunId` 时脚本自动生成时间戳；指定时须使用未用过的名字，避免日志重名。
阿里云百炼可用 `--provider dashscope --model qwen-plus`，但该机器现有
百炼账户返回 `Arrearage`，不能用于本机最终视频。队友此前在 Linux
运行的本地 Ollama 记录仍见下文。

第二个 LLM 使用 `qwen2.5:7b`，通过本机 Ollama 的 `http://127.0.0.1:11434/api/chat` 接口运行。Ollama 负责加载模型和使用 GPU 推理；Task 3 仍负责 prompt、JSON Schema、本地 validator、上下文和动作执行。两种 LLM 共用同一套安全边界。

本项目的用户本地安装位置为 `$HOME/.local/ollama`，可执行文件为 `$HOME/.local/bin/ollama`。重启电脑后先在一个终端启动本地服务：

```bash
$HOME/.local/bin/ollama serve
```

如果还没有模型，只需下载一次：

```bash
$HOME/.local/bin/ollama pull qwen2.5:7b
```

然后在另一个终端运行 Task 3：

```bash
conda activate ee5112-minilab
python -m task3.run \
  --provider ollama \
  --model qwen2.5:7b \
  --task2-root /path/to/extracted/task2-project \
  --gui
```

本地 Qwen 不需要 `OPENAI_API_KEY`，不会产生 OpenAI API 费用；代价是模型会占用本地磁盘、GPU 显存和电力。如果 Ollama 未启动，程序会输出 `[DONE] status=ERROR` 及本地连接错误，不会退回到付费的 OpenAI 服务。

## 拒绝与上下文策略

输入先经过供应商无关的本地策略，再交给 LLM：

- 空白输入立即输出 `status=REJECTED`；
- 含非 ASCII 字母的明显非英文输入在本地拒绝；
- `attack`、`crash`、`damage`、`run over` 等明显危险请求在本地拒绝；
- 其余模糊、无关或不支持的英文请求由 LLM 按 JSON 协议拒绝，随后仍经过本地 validator。

模型输出通过 JSON validator 后还会经过显式方向一致性检查。对于单动作命令，`forward`、
`backward`、`left`、`right` 以及左右转必须与 `vx`、`vy`、`angle_deg` 的符号一致；若文字和
数值方向冲突，程序打印 `[GUARD] status=REJECTED` 并且绝不执行该动作。这一层用于拦截
“文字说向右、JSON 却给出正 `vy`”一类 schema 合法但语义错误的模型输出。

本地拒绝不会调用付费 API。上下文只保存最近一份 `accepted=true` 且执行结果为
`SUCCESS` 的不可变计划；被拒绝、失败或取消的请求都不能覆盖它。发送给模型的上下文只包含
这一份已经验证的动作 JSON，API 请求使用 `store=False`。例如，上一次成功计划是
`move(vx=0.4, duration_s=2)` 时，`Do that again, but slower` 会生成
`move(vx=0.2, duration_s=4)`，以大致保持移动距离。

## Task 4 对接

`Task4Integration` 把 Task 2 的相机、机器人平面位置和仿真时间组合成 Task 4 要求的同一步快照，并把 `task4.goto_object()` 包装为执行器回调：

```python
from task3 import PlanExecutor, Task2MotionAdapter, Task4Integration
from task3.task4_integration import load_object_positions

motion = Task2MotionAdapter(platform)
task4 = Task4Integration(
    platform,
    motion,
    load_object_positions(task2_assets / "objects.json"),
    weights=str(task2_assets / "yolo11n.pt"),
)
executor = PlanExecutor(motion, goto_object=task4.goto_object)

# MuJoCo 主循环：
fresh_camera_frame = platform.step()
task4.capture_after_step(fresh_camera_frame)
```

`capture_after_step()` 必须紧接 `platform.step()` 并在仿真主线程中调用。`goto_object()` 仍在 Task 3 工作线程运行并等待新快照，因此 YOLO、LLM 和导航任务都不会接管 MuJoCo。场景中的目标坐标只在视觉停止后计算最终距离，用于课程 C2 验证，不参与转向或前进决策。

近距离时椅子会被低位相机裁切，YOLO 也可能为同一目标输出重叠框。导航会选面积最大的匹配框做视觉距离判断；框高达到标定阈值后，基于最后一个可靠画面完成一次对准和固定的低速末端接近，再停车验收。末端动作不读取物体真值坐标。

## 完整运行入口

`task3.run` 会一次性组装 Task 2 平台、Task 3 LLM/chat/executor 和 Task 4：

```bash
conda activate ee5112-minilab
export OPENAI_API_KEY="your-key-here"
python -m task3.run \
  --task2-root /path/to/extracted/task2-project
```

浏览器模式和无窗口模式分别使用 `--gui`、`--headless`。首次检查建议先禁用 chat，确认仿真、相机和 YOLO 全部能启动且绝不会调用 API：

```bash
python -m task3.run \
  --task2-root /path/to/extracted/task2-project \
  --headless --no-chat --duration 5
```

`--task2-root` 指向包含 `task2/platform.py` 的项目目录；也可以设置 `TASK2_ROOT` 环境变量。默认从 Task 2 包的 `assets/` 自动读取 `objects.json` 和 `yolo11n.pt`。终端输入 `/quit` 会取消正在执行的动作并让 MuJoCo 主循环安全退出。

`--provider openai` 是默认值；使用本地模型时显式传入 `--provider ollama`。也可用 `TASK3_PROVIDER`、`TASK3_OLLAMA_MODEL` 和 `OLLAMA_HOST` 环境变量覆盖默认值。

## 测试

从仓库根目录运行：

```bash
conda run -n ee5112-minilab python -m pytest -q task3
```

测试覆盖 JSON/schema 边界、本地拒绝、方向语义一致性、两种 provider 的响应边界、上下文、动作严格顺序、失败停止、Task 4 回调、benchmark 语义评分和成本计算。当前结果为 `102 passed`。

## 终端日志协议

每条日志必须只占一行，使用固定前缀和 `key=value`字段。用户输入、模型 message 和 exception 会先折叠换行与多余空白，防止伪造 `[EXEC]` 或 `[DONE]` 证据行。

```text
[RUNTIME] event=START mode=browser duration_s=120.0
[CHAT] event=READY input=english hint=/help
[CMD] text=Move forward for one second.
[LLM] provider=ollama model=qwen2.5:7b latency_s=1.246 input_tokens=1120 output_tokens=48 accepted=true actions=1
[PLAN] accepted=true actions=1 message=Moving forward.
[EXEC] step=1/1 type=move vx=0.40 vy=0.00 wz=0.00 duration_s=1.00
[EXEC] step=1/1 type=move status=SUCCESS
[DONE] status=SUCCESS actions=1
[RUNTIME] event=STOP steps=24001 sim_time=120.00
```

前缀含义：

- `[RUNTIME]`：MuJoCo 主循环开始或结束；
- `[CHAT]`：终端循环状态和本地控制命令；
- `[CMD]`：当次用户英文指令；
- `[LLM]`：供应商、模型、延迟、token 与计划大小；
- `[PLAN]`：经本地 validator 确认的计划；
- `[EXEC]`：每个动作的开始参数和完成状态；
- `[DONE]`：一条指令的最终 `SUCCESS` / `REJECTED` / `FAIL` / `CANCELLED` / `ERROR`。

## 20 条 LLM benchmark

`benchmark_cases.json` 固定了 10 条基础命令、5 条同义改写和 5 条无效/越界命令。每条都使用独立上下文，只测试 LLM 规划和本地 validator，不会调用动作执行器或 MuJoCo。

```bash
source "$HOME/.config/ee5112/task3.env"
$HOME/.local/bin/ollama serve  # 如果 Ollama 还没启动

python -m task3.benchmark \
  --provider both \
  --openai-model gpt-4o-mini \
  --ollama-model qwen2.5:7b \
  --output-json task3/evidence/step13_benchmark_results.json \
  --output-markdown task3/evidence/step13_benchmark.md
```

正式结果为 OpenAI `15/20 (75%)`、本地 Qwen `16/20 (80%)`。OpenAI 对 5 条无效/越界请求全部正确拒绝；Qwen 的基础命令和同义改写得分更高，但对数值边界不够安全。详细 JSON、逐条延迟、token、成本和失败分析见下方 Step 13 记录。

真实浏览器纯运动演示的命令、结果和失败修正记录见
[`evidence/step10_pure_motion.md`](evidence/step10_pure_motion.md)。

本地 Qwen 接入、选型和真实执行记录见
[`evidence/step12_local_qwen.md`](evidence/step12_local_qwen.md)。

20 条双模型 benchmark 的可读报告和原始结果分别见
[`evidence/step13_benchmark.md`](evidence/step13_benchmark.md) 和
[`evidence/step13_benchmark_results.json`](evidence/step13_benchmark_results.json)。

第 14 步的自动测试范围、日志协议和验证结果见
[`evidence/step14_tests_logs.md`](evidence/step14_tests_logs.md)。

最终录屏命令、MP4 参数和文件校验值见
[`evidence/step15_video_script.md`](evidence/step15_video_script.md)。

完整提交摘要、架构、复现命令、两模型比较和限制分析见
[`Task3_Report.md`](Task3_Report.md)。
