# Optional bonus：多目标任务与英语语音输入

这两个功能只在 `bonus-multigoal-speech` 分支新增，原有文字命令、单目标椅子任务和 Task 4 固定十次评估不依赖它们。**课程提交所需的 `Video_Bonus` 需另行录制；本仓库不包含视频。**

## 1. 多目标任务

输入一句英语，例如 `Visit the orange ball and then the green chair.`。本地 Qwen 或其他已配置的 LLM 输出两个有序 `goto_object` 动作；本地 validator 只接受场景中实际配置的 `orange sports ball`、`red chair`、`green chair`。执行器先完成第一个目标，再短暂后退脱离物体，才开始搜索第二个目标。前一步失败时，后续目标不会执行。

橙色球由机载相机画面识别：优先采用 YOLO 检测；当 YOLO 把近处的球叫作 `orange` 等标签时，使用橙色圆形像素连通区域作为视觉回退。机器人运动始终只根据实时画面；场景中的物体坐标只在停止后核验和记录距离，绝不用于导引。`[FOUND]` 仍要求停下后新画面看得到目标、目标距离不超过 0.80 m。多目标椅子任务有上限的近距离视觉接近；若目标已被画面边缘裁切，不再额外向前；停下后丢失目标时只允许最多两次短距离后退重新观察，绝不靠旧检测框或真值坐标宣称成功。原有单目标路径不变。

## 2. 英语语音输入

终端输入 `/voice` 后，程序从麦克风录制默认 7 秒，使用本地 `faster-whisper` 的 `base.en` 模型转录。`[STT] status=OK ... text=...` 后，转录文本直接进入**同一个** Task 3 英文命令入口：本地拒绝策略 → LLM JSON → validator → 执行器。语音识别本身不控制机器人；空音频或转录失败不会执行动作。也可用 `/voice-file /absolute/path/command.wav` 复测录好的英语音频。

Linux 录音优先使用系统 `arecord`，其他系统使用 Python `sounddevice`（须有可用 PortAudio/麦克风驱动）。首次转录时会下载语音模型；之后从本机缓存读取。语音识别和本地 Ollama/Qwen 不调用付费 API。

## Linux 本机运行

在仓库根目录：

```bash
conda activate ee5112-minilab
python -m pip install -r task3/requirements-bonus.txt
arecord -l                         # 应能列出录音设备
$HOME/.local/bin/ollama serve      # 如果服务尚未运行，另开一个终端
```

在另一个终端启动仿真；`--task2-root task2` 使用本仓库的 Task 2 包。请勿同时运行多个仿真进程占用端口。

```bash
python -m task3.run \
  --provider ollama --model qwen2.5:7b \
  --task2-root task2 --gui --dual-view \
  --voice --voice-duration 7 \
  --duration 600 --mission-timeout 150
```

界面地址通常是 `http://127.0.0.1:8766/`（双视图）；在终端输入下列任一项：

```text
Visit the orange ball and then the green chair.
/voice
/voice-file /absolute/path/english-command.wav
/stop
/quit
```

对 `/voice`，看到 `[STT] status=RECORDING` 后清楚说英语。录制前先确认 `[STT] status=OK` 的文字正确，再检查 `[CMD]`、逐个 `[EXEC]`、每个 `[FOUND]` 及最终 `[DONE] status=SUCCESS`。示例三目标句子是 `Visit the orange ball, then the red chair, and finally the green chair.`；三目标连续导航目前**尚未稳定通过实测**，因此演示建议先使用上面的两目标句子，不要把一次失败误写成成功。

若要在**同一个终端、同一段视频**里展示两条真正不同的多任务语音命令，建议第二次启动时使用 `--voice-duration 15`，以免较长句子被截断。第一条说 `Visit the orange ball and then the green chair.`；第一条完成后输入 `/reset`，等待 `[RESET] status=SUCCESS position=initial`，再输入第二次 `/voice` 并说 `Visit the orange ball, then the green chair. After reaching the chair, turn around by 180 degrees and move forward at speed 0.2 for one second.`。第二条应生成两个 `goto_object`、一个 `turn`、一个 `move`。重置只在没有命令执行时接受，由 MuJoCo 主线程完成；它会清除旧相机画面和上一条成功计划的上下文。不要在机器人还在移动时重置，也不要在重置完成前发下一条命令。

复杂四步命令的两次本地真实仿真复测中，一次在绿色椅子的最终视觉确认处停止，另一次完整执行四步成功。因此视频能展示动作组合与失败即停，但**不能仅凭一段成功视频声称系统已达到统计意义上的高鲁棒性**；这需要额外的重复试验与成功率。

无需麦克风的重复试验可用：

```bash
python -m task3.run --provider ollama --model qwen2.5:7b \
  --task2-root task2 --headless --duration 400 --mission-timeout 150 \
  --command "Visit the orange ball and then the green chair."
```

## 已验证范围与限制

- 自动化测试：`conda run -n ee5112-minilab python -m pytest -q task3`，共 136 项通过（含动作顺序、失败截断、语音交接、场景重置、近距离视觉恢复、颜色形状回退）。
- 本地 Ollama/Qwen 已把“球，然后两张椅子”解析成正确顺序。一次真实仿真中，“橙色球 → 绿色椅子”依次到达两目标，记录了两个 `[FOUND]` 和最终成功；真实视觉导航仍可能随起点、步态和检测结果波动，不能保证每次成功。
- 已用真实人声完成一次端到端录制：同一仿真会话中，第一条语音解析为两个有序目标并完成，`/reset` 后第二条语音解析为两个目标、180 度转向和 1 秒前进，四步均完成。终端日志包含两次 `[STT] status=OK`、`[CMD]`、逐步 `[EXEC]`、目标 `[FOUND]` 和最终 `[DONE] status=SUCCESS`。带麦克风音轨的 `Video_Bonus` 保存在本机，由组员单独传递，不在 GitHub 仓库内。
- 原 Task 4 报告的 8/10 是旧固定控制器修订的结果，不代表本 bonus 分支的新评估成绩。

本分支只提交代码、测试和说明，不提交模型缓存、音频、视频、API key 或本地原始运行日志。
