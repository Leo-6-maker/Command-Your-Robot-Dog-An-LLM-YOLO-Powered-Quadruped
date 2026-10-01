# Runtime Control Demo

This directory is a self-contained Dog ONNX example. All in-repo resources are located relative to `play.py`, so running it does not depend on the current working directory and contains no machine-specific absolute paths.

Contents:

- `model_3400.onnx`: example policy;
- `dog.yaml`: policy and simulation parameters;
- `dog/`: MuJoCo XML, meshes and URDF;
- `play.py`: complete Runtime Control integration example.

## Install dependencies

```bash
pip install mujoco numpy onnxruntime pyyaml pillow
```

Optional native global keyboard capture on Linux:

```bash
pip install evdev
```

Without `evdev`, `W/S/A/D/Q/E` still work in the browser panel.

## Run from the repository root

Browser control panel:

```bash
python eg/play.py --gui
```

Native MuJoCo viewer:

```bash
python eg/play.py
```

Headless quick check:

```bash
python eg/play.py --headless --duration 1
```

Use another policy:

```bash
python eg/play.py --gui --onnx path/to/model.onnx
```

See all options with:

```bash
python eg/play.py --help
```
