"""
Dog Sim2Sim — IsaacGym → MuJoCo

Joint order:
  MuJoCo XML order (i.e. URDF order): FL(0-2), FR(3-5), RR(6-8), RL(9-11)
  IsaacGym dof order (internally reordered): FL(0-2), FR(3-5), RL(6-8), RR(9-11)
  → The rear legs are swapped! RL/RR remapping is required!


   sudo chmod 666 /dev/input/event*
"""
import time
from pathlib import Path
import sys
import mujoco
import numpy as np
import onnxruntime as ort
import yaml


# All in-repo resources are located relative to this file, so running does not
# depend on the current working directory or machine-specific absolute paths.
DEMO_DIR = Path(__file__).resolve().parent
RUNTIME_CONTROL_DIR = DEMO_DIR.parent
PACKAGE_SRC = RUNTIME_CONTROL_DIR / "src"
try:
    from runtime_control import (
        MotorCommandDelay,
        RuntimeScene,
        bundled_map_specs,
        compute_pd_torques,
        make_runtime_config,
        make_standard_robot_cameras,
        scale_torque_limits,
        setup_tracking_camera,
        standard_camera_options,
    )
except ModuleNotFoundError as exc:
    if exc.name != "runtime_control":
        raise
    sys.path.insert(0, str(PACKAGE_SRC))
    from runtime_control import (
        MotorCommandDelay,
        RuntimeScene,
        bundled_map_specs,
        compute_pd_torques,
        make_runtime_config,
        make_standard_robot_cameras,
        scale_torque_limits,
        setup_tracking_camera,
        standard_camera_options,
    )


DEFAULT_CONFIG = DEMO_DIR / "dog.yaml"
DEFAULT_ONNX = DEMO_DIR / "model_3400.onnx"
DEFAULT_ROBOT_XML = DEMO_DIR / "dog" / "xml" / "dog_terrain.xml"
MAP_SPECS = bundled_map_specs()

# compose_scene injects these under "trunk"; they move and rotate with the robot.
ROBOT_CAMERAS = make_standard_robot_cameras(prefix="dog")
CAMERA_OPTIONS = standard_camera_options(prefix="dog")


# ============================================================
#  RL/RR remapping — IsaacGym internally reorders the joints
# ============================================================
# MuJoCo qpos[7:19] order: FL(0-2), FR(3-5), RR(6-8), RL(9-11)
# IsaacGym dof order:      FL(0-2), FR(3-5), RL(6-8), RR(9-11)
#
# MuJoCo[i] -> Isaac[j]:
#   MuJoCo 0-5  (FL,FR) -> Isaac 0-5  (FL,FR)  unchanged
#   MuJoCo 6-8  (RR)    -> Isaac 9-11 (RR)
#   MuJoCo 9-11 (RL)    -> Isaac 6-8  (RL)

MUJOCO_TO_ISAAC = [0, 1, 2, 3, 4, 5, 9, 10, 11, 6, 7, 8]
ISAAC_TO_MUJOCO = [0, 1, 2, 3, 4, 5, 9, 10, 11, 6, 7, 8]

# Default joint angles — IsaacGym dof order: FL, FR, RL, RR
# From dog_config.py default_joint_angles
# FL: hip=-0.1, thigh=-0.8, calf=-1.5
# FR: hip=0.1,  thigh=0.8,  calf=1.5
# RL: hip=0.1,  thigh=-1.0, calf=-1.5
# RR: hip=-0.1, thigh=1.0,  calf=1.5
DEFAULT_ANGLES_ISAAC = np.array([
    -0.1, -0.8, -1.5,    # FL (Isaac dof 0-2)
     0.1,  0.8,  1.5,    # FR (Isaac dof 3-5)
     0.1, -1.0, -1.5,    # RL (Isaac dof 6-8)
    -0.1,  1.0,  1.5,    # RR (Isaac dof 9-11)
], dtype=np.float64)

# MuJoCo order: FL, FR, RR, RL — derived from the Isaac order via the mapping
DEFAULT_ANGLES_MUJOCO = DEFAULT_ANGLES_ISAAC[ISAAC_TO_MUJOCO]

# Torque limits (from URDF actuatorfrcrange / dog.xml)
TAU_LIMIT_HIP_THIGH = 23.7   # hip, thigh joint torque limit [Nm]
TAU_LIMIT_CALF = 35.55        # calf joint torque limit [Nm]
OUTPUT_PRINT_SCALE = 0.25


def quat_rotate_inverse(q, v):
    q_w = q[3]
    q_vec = q[:3]
    a = v * (2.0 * q_w ** 2 - 1.0)
    b = np.cross(q_vec, v) * q_w * 2.0
    c = q_vec * np.dot(q_vec, v) * 2.0
    return a - b + c


class ObsHistoryBuffer:
    def __init__(self, history_len, single_obs_dim):
        self.history_len = history_len
        self.single_obs_dim = single_obs_dim
        self.total_dim = history_len * single_obs_dim
        self.buffer = np.zeros(self.total_dim, dtype=np.float32)

    def push(self, new_obs):
        self.buffer[self.single_obs_dim:] = self.buffer[:-self.single_obs_dim].copy()
        self.buffer[:self.single_obs_dim] = new_obs

    def get(self):
        return self.buffer.reshape(1, -1).copy()

    def reset(self):
        self.buffer[:] = 0.0


# ============================================================
#  Keyboard control
#  Movement keys (W/A/S/D/Q/E): evdev press/release listener — move while held,
#  stop on release
#  Function keys (R/F/Z/T/Y/X): single-shot via the MuJoCo key_callback
# ============================================================

# --- evdev: optional global keyboard input on Linux; browser control does not
# depend on it. ---
try:
    import evdev
except ImportError:
    evdev = None
import threading

def _find_keyboards():
    """Auto-detect keyboard devices (supporting EV_KEY with letter keys)"""
    keyboards = []
    if evdev is None:
        return keyboards
    for path in evdev.list_devices():
        try:
            dev = evdev.InputDevice(path)
            caps = dev.capabilities()
            if evdev.ecodes.EV_KEY in caps:
                keys = caps[evdev.ecodes.EV_KEY]
                if evdev.ecodes.KEY_W in keys:
                    keyboards.append(dev)
                    continue
        except Exception:
            pass
    return keyboards

_pressed_keys = set()   # keys currently held down (lowercase letters)

# Direction key mapping: evdev scancode → direction letter
_DIR_SCANCODES = {} if evdev is None else {
    evdev.ecodes.KEY_W: 'w', evdev.ecodes.KEY_S: 's',
    evdev.ecodes.KEY_A: 'a', evdev.ecodes.KEY_D: 'd',
    evdev.ecodes.KEY_Q: 'q', evdev.ecodes.KEY_E: 'e',
    evdev.ecodes.KEY_UP: 'w', evdev.ecodes.KEY_DOWN: 's',
    evdev.ecodes.KEY_LEFT: 'a', evdev.ecodes.KEY_RIGHT: 'd',
}

def _evdev_keyboard_thread(dev):
    """Background thread: read evdev keyboard events"""
    try:
        for event in dev.read_loop():
            if event.type == evdev.ecodes.EV_KEY:
                scancode = event.code
                value = event.value  # 1=press, 0=release, 2=hold repeat
                if scancode in _DIR_SCANCODES:
                    d = _DIR_SCANCODES[scancode]
                    if value == 1:      # press
                        _pressed_keys.add(d)
                    elif value == 0:    # release
                        _pressed_keys.discard(d)
    except Exception as e:
        print(f"[KEYBOARD] evdev device read error: {e}")

# Start the evdev keyboard listeners
_kb_devs = _find_keyboards()

if not _kb_devs and evdev is not None:
    # If permissions are missing, try opening a known keyboard device directly
    import glob, os
    _keyboard_event = "/dev/input/event3"  # AT Translated Set 2 keyboard
    if os.path.exists(_keyboard_event):
        try:
            _dev = evdev.InputDevice(_keyboard_event)
            _kb_devs = [_dev]
        except PermissionError:
            print(f"\n{'='*60}")
            print("[KEYBOARD] ⚠ Cannot access keyboard device (Permission denied)")
            print(f"{'='*60}")
            print("  Cause: pynput/evdev needs /dev/input access under Wayland")
            print("  Fixes (pick one):")
            print("")
            print("  Option 1: add the current user to the input group"
                  " (recommended, permanent after reboot)")
            print("    sudo usermod -aG input $USER")
            print("    then log out and log back in")
            print("")
            print("  Option 2: temporarily change device permissions"
                  " (must be repeated after every reboot)")
            print("    sudo chmod 666 /dev/input/event*")
            print("")
            print("  Option 3: run this script with sudo")
            print(f"    sudo python3 {os.path.abspath(__file__)} ...")
            print(f"{'='*60}\n")
        except Exception:
            pass

for _dev in _kb_devs:
    _t = threading.Thread(target=_evdev_keyboard_thread, args=(_dev,), daemon=True)
    _t.start()

if _kb_devs:
    print(f"[KEYBOARD] evdev: listening on {len(_kb_devs)} keyboard device(s)")
    for _dev in _kb_devs:
        print(f"  - {_dev.path}: {_dev.name}")
elif evdev is None:
    print("[KEYBOARD] evdev not installed; browser keyboard control is available")

# --- MuJoCo key_callback: function keys ---
GLFW_KEY_R = 82;  GLFW_KEY_F = 70
GLFW_KEY_Z = 90;  GLFW_KEY_T = 84
GLFW_KEY_Y = 89;  GLFW_KEY_X = 88
GLFW_KEY_SPACE = 32

# Global state
height_cmd = 0.25
reset_flag = False
print_action_flag = False


def key_callback(keycode):
    """MuJoCo keyboard callback — function keys only"""
    global height_cmd, reset_flag, print_action_flag
    if keycode == GLFW_KEY_R:
        height_cmd = max(0.20, height_cmd - 0.02)
    elif keycode == GLFW_KEY_F:
        height_cmd = min(0.35, height_cmd + 0.02)
    elif keycode == GLFW_KEY_Z:
        height_cmd = 0.25
    elif keycode == GLFW_KEY_T:
        reset_flag = True
    elif keycode == GLFW_KEY_Y:
        print_action_flag = not print_action_flag
    elif keycode == GLFW_KEY_X:
        _pressed_keys.clear()
    elif keycode == GLFW_KEY_SPACE and "runtime" in globals():
        runtime.request_push()

    # Keep the native viewer shortcuts in sync with the browser panel;
    # otherwise the panel value overwrites them on the next simulation step.
    if "runtime" in globals():
        if keycode in (GLFW_KEY_R, GLFW_KEY_F, GLFW_KEY_Z):
            runtime_config["command"]["height"] = height_cmd
            runtime.sync_height_to_panel()
        elif keycode == GLFW_KEY_X:
            runtime.sync_stop_to_panel()


def get_commands():
    """Return commands from the current key state — move while held, stop on release"""
    vx = ( 1.0 if 'w' in _pressed_keys else
          -1.0 if 's' in _pressed_keys else 0.0)
    vy = ( 1.0 if 'a' in _pressed_keys else
          -1.0 if 'd' in _pressed_keys else 0.0)
    wz = ( 1.0 if 'q' in _pressed_keys else
          -1.0 if 'e' in _pressed_keys else 0.0)
    return np.array([vx, vy, wz], dtype=np.float32)


def build_single_obs(quat_xyzw, omega, joint_q_isaac, joint_dq_isaac,
                     last_action_isaac, default_angles_isaac,
                     cmd, cmd_scale, ang_vel_scale, dof_pos_scale, dof_vel_scale,
                     clip_obs, height_cmd=0.25):
    """
    Build the 46-dim single-step observation — all joint quantities use the
    IsaacGym dof order: FL, FR, RL, RR
    Dim 46: height command (height_cmd - 0.25) / 0.1
    """
    obs = np.zeros(46, dtype=np.float32)
    obs[0:3] = cmd * cmd_scale[:3]

    omega_body = omega  # MuJoCo free-joint angular qvel is already in the local body frame
    obs[3:6] = omega_body.astype(np.float32) * ang_vel_scale

    gravity_world = np.array([0., 0., -1.], dtype=np.float64)
    proj_gravity = quat_rotate_inverse(quat_xyzw, gravity_world)
    obs[6:9] = proj_gravity.astype(np.float32)

    obs[9:21] = ((joint_q_isaac - default_angles_isaac) * dof_pos_scale).astype(np.float32)
    obs[21:33] = (joint_dq_isaac * dof_vel_scale).astype(np.float32)
    obs[33:45] = last_action_isaac
    obs[45] = np.float32((height_cmd - 0.25) / 0.1)
    obs = np.clip(obs, -clip_obs, clip_obs)
    return obs


def reset_robot(model, data, default_angles_mujoco, position=None, quaternion=None):
    mujoco.mj_resetData(model, data)
    data.qpos[:3] = position if position is not None else [0.0, 0.0, 0.42]
    data.qpos[3:7] = quaternion if quaternion is not None else [1, 0, 0, 0]
    data.qpos[7:19] = default_angles_mujoco
    data.qvel[:] = 0
    mujoco.mj_forward(model, data)


def build_runtime_config(args, kps, kds):
    """Adapt Dog's flat policy config into the structure used by runtime_control."""
    map_spawns = {
        name: {
            "position": [0.0, 0.0, 0.42],
            "quaternion": [1.0, 0.0, 0.0, 0.0],
        }
        for name in MAP_SPECS
    }
    map_spawns["rc26_track"] = {
        "position": [3.7, -9.0, 0.45],
        "quaternion": [-0.7071068, 0.0, 0.0, 0.7071068],
    }
    map_spawns["google_barkour"] = {
        "position": [1.0, -1.5, 0.42],
        "quaternion": [1.0, 0.0, 0.0, 0.0],
    }
    map_labels = {
        "rc26_track": "26RC Track",
        "race_track": "Race Track",
        "stairs": "Stairs",
        "cross_stairs": "Cross Stairs",
        "cross_slope": "Cross Slope",
        "google_barkour": "Google Barkour",
        "gap_jump": "Gap Jump",
        "hurdles": "Hurdles",
        "suspended_steps": "Suspended Steps",
        "perlin_rough": "Perlin Rough Terrain",
        "dynamic_obstacles": "Dynamic Obstacles",
    }
    return make_runtime_config(
        gui=args.gui,
        title="Dog MuJoCo Live Tuning",
        maps=map_labels,
        map_spawns=map_spawns,
        kp=kps[0],
        kd=kds[0],
        torque_limit=TAU_LIMIT_CALF,
        initial_position=map_spawns["rc26_track"]["position"],
        initial_quaternion=map_spawns["rc26_track"]["quaternion"],
        command=(1.0, 1.0, 1.0, 0.25),
        height_range=(0.2, 0.35),
        cameras=CAMERA_OPTIONS,
        port=args.gui_port,
        tracking_camera={
            "camera_distance": 2.0,
            "camera_azimuth": 135.0,
            "camera_elevation": -25.0,
        },
        randomization={
            "kp": [32.0, 48.0],
            "kd": [0.8, 1.2],
            "torque_limit": [28.0, 42.0],
            "motor_strength": [0.9, 1.1],
            "motor_delay_ms": [0.0, 15.0],
            "mass_scale": [0.9, 1.1],
            "payload_mass": [0.0, 2.0],
            "friction_scale": [0.5, 1.5],
            "gravity_z": [-10.3, -9.3],
        },
        push={
            "force_range": [40.0, 100.0],
            "duration_range": [0.10, 0.25],
        },
    )


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--onnx",
        type=Path,
        default=DEFAULT_ONNX,
        help="ONNX path (defaults to eg/model_3400.onnx)",
    )
    parser.add_argument("--no-policy", action="store_true")
    parser.add_argument(
        "--headless",
        action="store_true",
        help="open neither the browser nor the native viewer; for automated checks",
    )
    parser.add_argument(
        "--duration",
        type=float,
        help="override the simulation duration (seconds) from the YAML",
    )
    parser.add_argument(
        "--verbose-inference",
        action="store_true",
        help="print the first 10 full observations; off by default",
    )
    parser.add_argument(
        "--gui",
        action="store_true",
        help="enable only the browser live-tuning panel (no native MuJoCo viewer)",
    )
    parser.add_argument("--gui-port", type=int, default=8765, help="browser panel port")
    args = parser.parse_args()
    if args.gui and args.headless:
        parser.error("--gui and --headless cannot be used together")
    if args.duration is not None and args.duration <= 0:
        parser.error("--duration must be greater than 0")

    config_path = DEFAULT_CONFIG
    policy_path = (
        None if args.no_policy else str(args.onnx.expanduser().resolve())
    )
    if policy_path is not None and not Path(policy_path).is_file():
        raise FileNotFoundError(f"ONNX model not found: {policy_path}")
    with config_path.open("r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    simulation_duration = (
        args.duration
        if args.duration is not None else config["simulation_duration"]
    )
    simulation_dt       = config["simulation_dt"]
    control_decimation  = config["control_decimation"]
    kps            = np.array(config["kps"], dtype=np.float64)
    kds            = np.array(config["kds"], dtype=np.float64)
    action_scale   = config["action_scale"]
    ang_vel_scale  = config["ang_vel_scale"]
    dof_pos_scale  = config["dof_pos_scale"]
    dof_vel_scale  = config["dof_vel_scale"]
    cmd_scale      = np.array(config["cmd_scale"], dtype=np.float32)
    clip_obs       = config.get("clip_obs", 100.0)
    runtime_config = build_runtime_config(args, kps, kds)

    # Torque limits: hip/thigh=23.7, calf=35.55 (MuJoCo order)
    tau_limits_mujoco = np.array([
        TAU_LIMIT_HIP_THIGH, TAU_LIMIT_HIP_THIGH, TAU_LIMIT_CALF,
        TAU_LIMIT_HIP_THIGH, TAU_LIMIT_HIP_THIGH, TAU_LIMIT_CALF,
        TAU_LIMIT_HIP_THIGH, TAU_LIMIT_HIP_THIGH, TAU_LIMIT_CALF,
        TAU_LIMIT_HIP_THIGH, TAU_LIMIT_HIP_THIGH, TAU_LIMIT_CALF,
    ])

    NUM_ONE_STEP_OBS = 46
    HISTORY_LEN      = 6
    NUM_ACTIONS      = 12

    print(f"\n{'='*60}")
    print(f"[CONFIG] Dog — with RL/RR remapping")
    print(f"{'='*60}")
    print(f"  IsaacGym dof: FL, FR, RL, RR")
    print(f"  MuJoCo dof:   FL, FR, RR, RL")
    print(f"  mapping: MUJOCO_TO_ISAAC = {MUJOCO_TO_ISAAC}")
    print(f"  default_isaac:  {DEFAULT_ANGLES_ISAAC}")
    print(f"  default_mujoco: {DEFAULT_ANGLES_MUJOCO}")
    print(f"  kps={kps[0]}, kds={kds[0]}, action_scale={action_scale}")
    print(f"  tau_limits: hip/thigh={TAU_LIMIT_HIP_THIGH}, calf={TAU_LIMIT_CALF}")
    print(f"{'='*60}")

    # RuntimeScene owns the temporary MJCF, model, data and browser runtime.
    scene = RuntimeScene(
        robot_xml=DEFAULT_ROBOT_XML,
        map_specs=MAP_SPECS,
        runtime_config=runtime_config,
        robot_body_name="trunk",
        robot_cameras=ROBOT_CAMERAS,
        dynamic_obstacle_map="dynamic_obstacles",
        output_name="dog_all_maps.xml",
    )
    scene.open()
    mj_model = scene.model
    mj_model.opt.timestep = simulation_dt
    mj_data = scene.data
    runtime = scene.runtime
    motor_delay = MotorCommandDelay(simulation_dt)

    print(f"\n[VERIFY] MuJoCo joint order:")
    for i in range(mj_model.njnt):
        jn = mujoco.mj_id2name(mj_model, mujoco.mjtObj.mjOBJ_JOINT, i)
        if jn: print(f"  [{i}] {jn}")

    reset_robot(
        mj_model,
        mj_data,
        DEFAULT_ANGLES_MUJOCO,
        runtime_config["simulation"]["initial_position"],
        runtime_config["simulation"]["initial_quaternion"],
    )

    # Verify: MuJoCo qpos converted to Isaac order should equal DEFAULT_ANGLES_ISAAC
    q_isaac = mj_data.qpos[7:19][MUJOCO_TO_ISAAC]
    print(f"\n[VERIFY] qpos(MuJoCo→Isaac): {q_isaac}")
    print(f"[VERIFY] expected (Isaac):   {DEFAULT_ANGLES_ISAAC}")
    print(f"[VERIFY] {'✓ match' if np.allclose(q_isaac, DEFAULT_ANGLES_ISAAC) else '✗ MISMATCH!'}")

    if not args.no_policy:
        policy = ort.InferenceSession(policy_path, providers=['CPUExecutionProvider'])
        input_name  = policy.get_inputs()[0].name
        output_name = policy.get_outputs()[0].name
        print(f"[ONNX] {policy.get_inputs()[0].shape} → {policy.get_outputs()[0].shape}")

    obs_history      = ObsHistoryBuffer(HISTORY_LEN, NUM_ONE_STEP_OBS)
    target_q_mujoco  = DEFAULT_ANGLES_MUJOCO.copy()
    action_isaac     = np.zeros(NUM_ACTIONS, dtype=np.float64)
    last_action_isaac = np.zeros(NUM_ACTIONS, dtype=np.float32)
    labels = ["FL_hip","FL_thigh","FL_calf","FR_hip","FR_thigh","FR_calf",
              "RL_hip","RL_thigh","RL_calf","RR_hip","RR_thigh","RR_calf"]
    count = 0
    inference_count = 0

    # Warm-up
    for _ in range(HISTORY_LEN):
        quat_wxyz = mj_data.qpos[3:7]
        quat_xyzw = np.array([quat_wxyz[1], quat_wxyz[2], quat_wxyz[3], quat_wxyz[0]])
        omega = mj_data.qvel[3:6].astype(np.float64)
        joint_q_isaac = mj_data.qpos[7:19].astype(np.float64)[MUJOCO_TO_ISAAC]
        joint_dq_isaac = mj_data.qvel[6:18].astype(np.float64)[MUJOCO_TO_ISAAC]
        obs = build_single_obs(
            quat_xyzw, omega, joint_q_isaac, joint_dq_isaac,
            last_action_isaac, DEFAULT_ANGLES_ISAAC,
            np.zeros(3, dtype=np.float32), cmd_scale,
            ang_vel_scale, dof_pos_scale, dof_vel_scale, clip_obs,
            height_cmd=0.25
        )
        obs_history.push(obs)

    print(f"[INFO] warm-up done, norm={np.linalg.norm(obs_history.buffer):.4f}")
    print(f"\n  W/S:forward/back A/D:strafe Q/E:turn X:emergency stop"
          f" T:reset Y:print model output")
    print(f"  R:crouch↓ F:stand↑ Z:reset height (default 0.25m)")
    print(f"  [hold to move, release to stop] global evdev listener,"
          f" works on Wayland/X11\n")

    display = scene.viewer(
        args.gui or args.headless,
        key_callback=key_callback,
    )
    with display as viewer:
        # The browser and the native viewer are mutually exclusive display
        # modes, to avoid rendering twice and slowing the simulation down.
        if not args.gui and not args.headless:
            setup_tracking_camera(
                viewer,
                mj_model,
                "trunk",
                distance=2.0,
                azimuth=135.0,
                elevation=-25.0,
            )

        start = time.time()

        while viewer.is_running() and time.time() - start < simulation_duration:
            step_start = time.time()

            # The browser and the physical keyboard both update the motion
            # command. Without --gui the original keyboard logic is kept.
            if runtime.update_command(_pressed_keys):
                cmd = np.array([
                    runtime_config["command"]["linear_x"],
                    runtime_config["command"]["linear_y"],
                    runtime_config["command"]["yaw"],
                ], dtype=np.float32)
                height_cmd = runtime_config["command"]["height"]
            else:
                cmd = get_commands()

            runtime_state = runtime.runtime_control(mj_model, mj_data)
            if runtime.consume_reset():
                reset_flag = True

            if reset_flag:
                reset_robot(
                    mj_model,
                    mj_data,
                    DEFAULT_ANGLES_MUJOCO,
                    runtime_config["simulation"]["initial_position"],
                    runtime_config["simulation"]["initial_quaternion"],
                )
                obs_history.reset()
                last_action_isaac[:] = 0; action_isaac[:] = 0; count = 0; inference_count = 0
                print_action_flag = False
                height_cmd = runtime_config["command"]["height"]
                motor_delay.reset()
                runtime.reset_simulation_state()
                reset_flag = False

            # Read the MuJoCo state
            joint_q_mujoco  = mj_data.qpos[7:19].astype(np.float64)
            joint_dq_mujoco = mj_data.qvel[6:18].astype(np.float64)

            # ★ Remap to IsaacGym order (fed to the policy)
            joint_q_isaac  = joint_q_mujoco[MUJOCO_TO_ISAAC]
            joint_dq_isaac = joint_dq_mujoco[MUJOCO_TO_ISAAC]

            quat_wxyz = mj_data.qpos[3:7]
            quat_xyzw = np.array([quat_wxyz[1], quat_wxyz[2], quat_wxyz[3], quat_wxyz[0]])
            omega = mj_data.qvel[3:6].astype(np.float64)

            if count % control_decimation == 0:
                if not args.no_policy:
                    single_obs = build_single_obs(
                        quat_xyzw, omega, joint_q_isaac, joint_dq_isaac,
                        last_action_isaac, DEFAULT_ANGLES_ISAAC,
                        cmd, cmd_scale,
                        ang_vel_scale, dof_pos_scale, dof_vel_scale, clip_obs,
                        height_cmd=height_cmd
                    )
                    obs_history.push(single_obs)
                    obs_input = obs_history.get()

                    if args.verbose_inference and inference_count < 10:
                        print(f"\n{'='*60}")
                        print(f"[inference #{inference_count}] full 276-dim history obs"
                              f" (6 frames × 46 dims):")
                        buf = obs_history.buffer
                        for slot in range(HISTORY_LEN):
                            base = slot * 46
                            frame = buf[base:base+46]
                            print(f"\n  --- frame {slot} (offset {base}) ---")
                            print(f"    cmd:          {frame[0:3]}")
                            print(f"    gyro_body:    {frame[3:6]}")
                            print(f"    proj_gravity: {frame[6:9]}")
                            print(f"    dof_pos_dev:  {np.array2string(frame[9:21], precision=4, separator=', ')}")
                            print(f"    dof_vel:      {np.array2string(frame[21:33], precision=4, separator=', ')}")
                            print(f"    last_action:  {np.array2string(frame[33:45], precision=4, separator=', ')}")
                            print(f"    height_cmd:   {frame[45]:.4f}")
                            print(f"    frame norm:   {np.linalg.norm(frame):.4f}")
                        if inference_count == 9:
                            print(f"\n[INFO] first 10 obs frames printed;"
                                  f" press Y to start printing model output.")
                        print(f"{'='*60}")

                    action_raw = policy.run([output_name], {input_name: obs_input})[0][0]
                    action_isaac[:] = np.clip(action_raw, -10.0, 10.0)
                    last_action_isaac = action_isaac.astype(np.float32)

                    if inference_count >= 10 and print_action_flag:
                        print(f"\n[inference #{inference_count}] model output action x"
                              f" {OUTPUT_PRINT_SCALE} (Isaac order FL,FR,RL,RR):")
                        for j in range(12):
                            print(f"    {labels[j]:12s}: action={action_isaac[j] * OUTPUT_PRINT_SCALE:+.4f}")

                    inference_count += 1

                    # ★ Target angles: IsaacGym order → MuJoCo order
                    target_q_isaac = action_isaac * action_scale + DEFAULT_ANGLES_ISAAC
                    target_q_mujoco = target_q_isaac[ISAAC_TO_MUJOCO]
                else:
                    target_q_mujoco = DEFAULT_ANGLES_MUJOCO.copy()

            # PD control (MuJoCo order). Live Kp/Kd, motor strength, delay and
            # torque limits all take effect right before writing data.ctrl.
            applied_target_q = motor_delay.apply(
                target_q_mujoco, runtime_state["motor_delay_ms"]
            )
            effective_tau_limits = scale_torque_limits(
                tau_limits_mujoco,
                runtime_state["torque_limit"],
                reference_limit=TAU_LIMIT_CALF,
            )
            tau = compute_pd_torques(
                applied_target_q,
                joint_q_mujoco,
                joint_dq_mujoco,
                runtime_state["kp"],
                runtime_state["kd"],
                motor_strength=runtime_state["motor_strength"],
                torque_limit=effective_tau_limits,
            )
            mj_data.ctrl[:NUM_ACTIONS] = tau

            runtime.apply_external_forces(mj_model, mj_data)
            mujoco.mj_step(mj_model, mj_data)
            count += 1

            if count % (control_decimation * 50) == 0:
                grav = quat_rotate_inverse(quat_xyzw, np.array([0., 0., -1.]))
                h = mj_data.qpos[2]
                print(f"[{time.time()-start:.1f}s] Step {count} H={h:.3f}(cmd={height_cmd:.2f}) "
                      f"vx={mj_data.qvel[0]:.2f} vy={mj_data.qvel[1]:.2f} wz={mj_data.qvel[5]:.2f} "
                      f"grav_z={grav[2]:.3f} "
                      f"act=[{action_isaac.min():.2f},{action_isaac.max():.2f}]")

            if not args.gui and not args.headless:
                viewer.sync()
            elapsed = time.time() - step_start
            if simulation_dt - elapsed > 0:
                time.sleep(simulation_dt - elapsed)

    scene.close()
    print("\n[INFO] simulation finished")
