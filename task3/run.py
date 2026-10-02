"""Complete Task 2 + Task 3 + Task 4 simulator entry point."""

import argparse
import importlib
import math
import os
from pathlib import Path
import sys
import threading
import time
import webbrowser
from typing import Callable, Protocol

from task4 import CAMERA_FOVY_DEG
from .chat_loop import (
    TerminalChatLoop,
    build_ollama_chat_loop,
    build_openai_chat_loop,
    build_qwen_cloud_chat_loop,
    build_deepseek_chat_loop,
)
from .executor import PlanExecutor
from .task2_adapter import Task2MotionAdapter
from .task4_integration import Task4Integration, load_object_positions
from .speech_input import LocalSpeechInput


class ViewerLike(Protocol):
    def is_running(self) -> bool: ...

    def sync(self) -> None: ...


class _TeeOutput:
    """Mirror live terminal output without redirecting interactive stdin."""

    def __init__(self, terminal, log_file):
        self.terminal, self.log_file = terminal, log_file

    def write(self, text):
        self.terminal.write(text)
        self.log_file.write(text)
        return len(text)

    def flush(self):
        self.terminal.flush()
        self.log_file.flush()

    def isatty(self):
        return self.terminal.isatty()

    def fileno(self):
        return self.terminal.fileno()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the integrated EE5112 Task 3 command interface"
    )
    display = parser.add_mutually_exclusive_group()
    display.add_argument("--gui", action="store_true", help="use Task 2 browser GUI")
    display.add_argument("--headless", action="store_true", help="run without a viewer")
    parser.add_argument(
        "--duration",
        type=float,
        default=120.0,
        help="maximum simulation seconds (default: 120)",
    )
    parser.add_argument("--port", type=int, default=8765, help="Task 2 browser port")
    parser.add_argument("--dual-view", action="store_true",
                        help="show rear overhead and onboard camera together in the browser")
    parser.add_argument("--log-file", type=Path,
                        help="write the same runtime log lines to a new UTF-8 file")
    parser.add_argument("--mission-timeout", type=float, default=120,
                        help="Task 4 mission wall-clock timeout in seconds")
    parser.add_argument("--start", type=float, nargs=3, default=(0, 0, 0),
                        metavar=("X", "Y", "YAW_DEG"),
                        help="robot start pose for the shared Task 2 scene")
    parser.add_argument(
        "--task2-root",
        type=Path,
        default=Path(os.environ["TASK2_ROOT"]) if os.getenv("TASK2_ROOT") else None,
        help="directory containing the task2 Python package",
    )
    parser.add_argument(
        "--assets-dir",
        type=Path,
        help="override Task 2 assets directory containing objects.json and yolo11n.pt",
    )
    parser.add_argument(
        "--provider",
        choices=("openai", "ollama", "dashscope", "deepseek"),
        default=os.getenv("TASK3_PROVIDER", "openai"),
        help="LLM provider (default: TASK3_PROVIDER or openai)",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="provider model override",
    )
    parser.add_argument(
        "--ollama-host",
        default=None,
        help="Ollama URL override (default: OLLAMA_HOST or http://127.0.0.1:11434)",
    )
    parser.add_argument(
        "--no-chat",
        action="store_true",
        help="test simulator/camera/YOLO wiring without creating an API client",
    )
    parser.add_argument("--voice", action="store_true",
                        help="enable local microphone commands with /voice")
    parser.add_argument("--voice-model", default="base.en",
                        help="local faster-whisper model (default: base.en)")
    parser.add_argument("--voice-duration", type=float, default=7.0,
                        help="microphone recording seconds per /voice command")
    parser.add_argument("--command", type=str,
                        help="submit one English command at startup and exit when it finishes")
    return parser


def run_simulation_loop(
    platform: object,
    task4: Task4Integration,
    viewer: ViewerLike,
    *,
    duration_s: float,
    browser_only: bool,
    pace_wall_clock: bool = False,
    chat: TerminalChatLoop | None = None,
    reset_scene: Callable[[], None] | None = None,
    exit_when_idle: bool = False,
    monotonic: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> int:
    """Own MuJoCo stepping on the caller thread until one exit condition."""
    if not math.isfinite(duration_s) or duration_s <= 0:
        raise ValueError("duration_s must be finite and positive")
    end_sim_time = float(platform.data.time) + duration_s
    steps = 0
    while viewer.is_running() and float(platform.data.time) < end_sim_time:
        if chat is not None and chat.quit_requested:
            break
        if chat is not None and getattr(chat, "reset_requested", False):
            try:
                if reset_scene is None:
                    raise RuntimeError("scene reset is not configured")
                reset_scene()
            except Exception as exc:
                chat.finish_reset(error=exc)
                raise
            chat.finish_reset()
        started = monotonic()
        fresh = platform.step()
        task4.capture_after_step(bool(fresh))
        steps += 1
        if exit_when_idle and chat is not None and not chat.busy:
            break
        if not browser_only:
            viewer.sync()
        if pace_wall_clock:
            sleep(max(0.0, 0.005 - (monotonic() - started)))
    return steps


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not math.isfinite(args.duration) or args.duration <= 0:
        raise SystemExit("--duration must be finite and positive")
    if not math.isfinite(args.mission_timeout) or args.mission_timeout <= 0:
        raise SystemExit("--mission-timeout must be finite and positive")
    if not all(math.isfinite(value) for value in args.start):
        raise SystemExit("--start values must be finite")
    if args.dual_view and not args.gui:
        raise SystemExit("--dual-view requires --gui")
    if args.voice and args.no_chat:
        raise SystemExit("--voice requires chat")
    if args.command and args.no_chat:
        raise SystemExit("--command requires chat")
    if args.voice and not 1 <= args.voice_duration <= 30:
        raise SystemExit("--voice-duration must be between 1 and 30 seconds")
    if (
        not args.no_chat
        and args.provider == "openai"
        and not os.getenv("OPENAI_API_KEY")
    ):
        raise SystemExit(
            "OPENAI_API_KEY is not set. Export it before enabling chat, "
            "or use --no-chat for a free offline smoke test."
        )
    task2_module = _import_task2(args.task2_root)
    assets_dir = args.assets_dir or _task2_assets_dir(task2_module)
    objects_path = assets_dir / "objects.json"
    weights_path = assets_dir / "yolo11n.pt"
    for required in (objects_path, weights_path):
        if not required.is_file():
            raise SystemExit(f"missing Task 2 asset: {required}")

    from task2.platform import Platform

    log_lock = threading.Lock()
    log_file = args.log_file.open("x", encoding="utf-8", buffering=1) if args.log_file else None
    terminal_stdout = sys.stdout
    if log_file is not None:
        sys.stdout = _TeeOutput(terminal_stdout, log_file)

    def log(message: str) -> None:
        # Chat and simulator events originate on different threads. Keep each
        # evidence line atomic so two valid records cannot be joined together.
        with log_lock:
            print(message, flush=True)

    platform = Platform(gui=args.gui, camera=True, logger=log, port=args.port)
    task4: Task4Integration | None = None
    chat: TerminalChatLoop | None = None
    terminal_thread: threading.Thread | None = None
    dual_view = None
    try:
        with platform.runtime.model_lock:
            platform.model.camera("dog_front_camera").fovy[0] = CAMERA_FOVY_DEG
        if tuple(args.start) != (0, 0, 0):
            x, y, yaw = args.start
            half_angle = math.radians(yaw) / 2
            platform.config["simulation"]["initial_position"] = [x, y, 0.42]
            platform.config["simulation"]["initial_quaternion"] = [
                math.cos(half_angle), 0, 0, math.sin(half_angle)
            ]
            platform.reset()
        motion = Task2MotionAdapter(platform)
        task4 = Task4Integration(
            platform,
            motion,
            load_object_positions(objects_path),
            weights=str(weights_path),
            mission_timeout_s=args.mission_timeout,
        )
        executor = PlanExecutor(
            motion, goto_object=task4.goto_object,
            goto_object_multigoal=task4.goto_object_multigoal, logger=log,
        )
        if not args.no_chat:
            if args.provider == "ollama":
                chat = build_ollama_chat_loop(
                    executor,
                    model=args.model,
                    host=args.ollama_host,
                    logger=log,
                )
            elif args.provider == "dashscope":
                chat = build_qwen_cloud_chat_loop(executor, model=args.model, logger=log)
            elif args.provider == "deepseek":
                chat = build_deepseek_chat_loop(executor, model=args.model, logger=log)
            else:
                chat = build_openai_chat_loop(executor, model=args.model, logger=log)
            if args.voice:
                chat.speech_input = LocalSpeechInput(
                    model=args.voice_model, duration_s=args.voice_duration
                )
        else:
            log("[CHAT] status=DISABLED reason=no_chat")

        browser_only = bool(args.gui or args.headless)
        with platform.scene.viewer(browser_only) as viewer:
            if not browser_only:
                _configure_native_camera(viewer, platform)
            if args.dual_view:
                from .dual_view import DualViewServer

                dual_view = DualViewServer(platform.camera, task4.detector, args.port, args.port + 1)
                dual_view.start()
                webbrowser.open(dual_view.url, new=2)
                log(f"[UI] dual_view={dual_view.url}")
            log(
                f"[RUNTIME] event=START mode={_mode_name(args)} "
                f"duration_s={args.duration:.1f} "
                f"start=({args.start[0]:.2f},{args.start[1]:.2f},{args.start[2]:.1f})"
            )
            if chat is not None:
                if args.command:
                    chat.submit(args.command)
                else:
                    terminal_thread = threading.Thread(
                        target=chat.run,
                        name="task3-terminal",
                        daemon=True,
                    )
                    terminal_thread.start()
            def reset_scene() -> None:
                platform.reset()
                task4.reset_observations()

            steps = run_simulation_loop(
                platform,
                task4,
                viewer,
                duration_s=args.duration,
                browser_only=browser_only,
                # A one-shot headless command must not exhaust simulated time
                # while its model is still producing the plan.
                pace_wall_clock=not args.headless or bool(args.command),
                chat=chat,
                reset_scene=reset_scene,
                exit_when_idle=bool(args.command),
            )
        log(
            f"[RUNTIME] event=STOP steps={steps} "
            f"sim_time={platform.data.time:.2f}"
        )
        if chat is not None and terminal_thread is not None and terminal_thread.is_alive():
            chat.cancel()
            log("[CHAT] event=SIM_STOPPED hint=/quit")
            terminal_thread.join()
        if args.command:
            result = chat.last_execution_result if chat is not None else None
            return 0 if result is not None and result.succeeded else 1
        return 0
    finally:
        if chat is not None:
            chat.cancel()
        if dual_view is not None:
            dual_view.close()
        if task4 is not None:
            task4.close()
        if chat is not None:
            chat.wait(5.0)
        platform.close()
        if log_file is not None:
            sys.stdout = terminal_stdout
            log_file.close()


def _import_task2(task2_root: Path | None):
    if task2_root is not None:
        root = task2_root.expanduser().resolve()
        if not (root / "task2" / "platform.py").is_file():
            raise SystemExit(
                "--task2-root must contain task2/platform.py; "
                f"received: {root}"
            )
        sys.path.insert(0, str(root))
        importlib.invalidate_caches()
    try:
        module = importlib.import_module("task2")
    except ImportError as exc:
        raise SystemExit(
            "Task 2 package is unavailable. Pass --task2-root /path/to/task2-project"
        ) from exc
    if not getattr(module, "__file__", None):
        raise SystemExit(
            "found only the repository task2 folder, not the Python package; "
            "pass --task2-root /path/to/task2-project"
        )
    return module


def _task2_assets_dir(task2_module: object) -> Path:
    package_file = getattr(task2_module, "__file__", None)
    if not package_file:
        raise SystemExit("cannot locate Task 2 package assets")
    return Path(package_file).resolve().parent / "assets"


def _configure_native_camera(viewer: object, platform: object) -> None:
    try:
        from runtime_control import setup_tracking_camera
    except ImportError:
        return
    setup_tracking_camera(viewer, platform.model, "trunk", distance=4.0)


def _mode_name(args: argparse.Namespace) -> str:
    if args.gui:
        return "browser"
    if args.headless:
        return "headless"
    return "native"


if __name__ == "__main__":
    raise SystemExit(main())
