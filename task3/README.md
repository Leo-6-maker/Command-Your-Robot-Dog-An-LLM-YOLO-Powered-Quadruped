# Task 3 — LLM command planning

本目录目前完成动作 JSON 协议、本地验证器，以及 Task 2 非阻塞动作队列的阻塞适配器。LLM、终端循环和动作执行器将在后续步骤接入。

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

## 测试

从仓库根目录运行：

```bash
conda run -n ee5112-minilab python -m pytest -q task3
```
