"""Student A: Task 4's sole RGB source. Rendering stays on simulation thread."""
from dataclasses import dataclass
from threading import Lock
import mujoco

@dataclass(frozen=True)
class CameraFrame:
    rgb: object
    sim_time: float
    sequence: int

class FrontCamera:
    def __init__(self, model, hz=10, width=640, height=480):
        if not 10 <= hz <= 20:
            raise ValueError('perception rate must be 10-20 Hz')
        self.renderer = mujoco.Renderer(model, height=height, width=width)
        self.period = 1/hz
        self.next_time = 0.
        self.frame = None
        self.sequence = 0
        self.lock = Lock()

    def update(self, data):
        if data.time+1e-8 < self.next_time:
            return False
        self.renderer.update_scene(data, camera='dog_front_camera')
        rgb = self.renderer.render().copy()
        with self.lock:
            self.sequence += 1
            self.frame = CameraFrame(rgb, float(data.time), self.sequence)
        self.next_time = data.time+self.period
        return True

    def latest(self):
        """Thread-safe RGB uint8 HxWx3 copy; None before first frame. No ground truth."""
        with self.lock:
            f = self.frame
            return None if f is None else CameraFrame(f.rgb.copy(), f.sim_time, f.sequence)

    def reset(self):
        self.next_time = 0.
        with self.lock:
            self.frame = None

    def close(self):
        self.renderer.close()
