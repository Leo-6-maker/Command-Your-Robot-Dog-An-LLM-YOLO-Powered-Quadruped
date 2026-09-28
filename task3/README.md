# Task 3 — LLM command planning

本目录目前完成动作 JSON 协议、本地验证器、Task 2 非阻塞动作队列的阻塞适配器、串行动作执行器、OpenAI Structured Outputs 规划器和异步终端 chat loop。

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

`goto_object` 通过构造函数注入，当前尚未连接 Task 4：

```python
executor = PlanExecutor(adapter, goto_object=task4_callback)
```

## LLM 与终端 chat loop

终端 chat loop 是完整入口；LLM 是它内部把英文句子转换成动作 JSON 的环节：

```text
terminal → OpenAIPlanner → local validator → PlanExecutor → Task 2
```

先在当前终端临时设置 API key（不要写进代码或提交到 Git）：

```bash
export OPENAI_API_KEY="your-key-here"
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

只有执行成功的计划会成为下一句的上下文，因此 `Do that again slower` 可以引用上一次成功动作。OpenAI 请求记录延迟和 token 数，后续可直接用于两种 LLM 的实验对比。

## 测试

从仓库根目录运行：

```bash
conda run -n ee5112-minilab python -m pytest -q task3
```
