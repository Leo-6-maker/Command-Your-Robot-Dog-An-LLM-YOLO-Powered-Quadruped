"""Student A: thread-safe, nonblocking motion queue; simulation-time execution."""
from collections import deque
from dataclasses import dataclass
import math
import threading
import numpy as np


def yaw_from_qpos(qpos):
    w, x, y, z = qpos[3:7]
    return math.atan2(2*(w*z+x*y), 1-2*(y*y+z*z))


def wrap(a):
    return math.atan2(math.sin(a), math.cos(a))


@dataclass
class Action:
    kind: str
    values: tuple


class MotionSkills:
    def __init__(self, logger=print):
        self._queue = deque()
        self._lock = threading.RLock()
        self.active = None
        self.log = logger
        self.results = []

    def move(self, vx, vy, wz, duration):
        values = tuple(float(v) for v in (vx, vy, wz, duration))
        if not all(math.isfinite(v) for v in values):
            raise ValueError('commands must be finite')
        if any(abs(v)>1 for v in values[:3]) or not 0<values[3]<=60:
            raise ValueError('velocity must be in [-1,1]; duration in (0,60]')
        with self._lock:
            self._queue.append(Action('move', values))

    def turn(self, angle_deg):
        angle = float(angle_deg)
        if not math.isfinite(angle) or abs(angle)>720:
            raise ValueError('angle must be finite and within +/-720 degrees')
        with self._lock:
            self._queue.append(Action('turn', (angle,)))

    def stop(self):
        with self._lock:
            self._queue.clear()
            self.active = None

    @property
    def busy(self):
        with self._lock:
            return self.active is not None or bool(self._queue)

    def update(self, t, qpos):
        """Call at 50 Hz, exclusively on the simulation thread. Returns normalized cmd."""
        with self._lock:
            yaw = yaw_from_qpos(qpos)
            if self.active is None:
                if not self._queue:
                    return np.zeros(3, dtype=np.float32)
                self.active = self._queue.popleft()
                self.started = t
                self.previous_yaw = yaw
                self.rotation = 0.
                self.stable_since = None
                self.log(f'[SKILL] {self.active.kind} values={self.active.values} t={t:.2f}')
            a = self.active
            if a.kind == 'move':
                if t-self.started >= a.values[3]-1e-8:
                    self.active = None
                    self.log(f'[MOVE] completed duration={a.values[3]:.2f}')
                    return np.zeros(3, dtype=np.float32)
                return np.array(a.values[:3], dtype=np.float32)
            delta = wrap(yaw-self.previous_yaw)
            self.rotation += delta
            self.previous_yaw = yaw
            error = math.radians(a.values[0])-self.rotation
            # Accumulated yaw preserves requested direction and turns exceeding 180 deg.
            if abs(error) <= math.radians(2):
                self._finish(t, error, 'SUCCESS')
                return np.zeros(3, dtype=np.float32)
            self.stable_since = None
            if t-self.started > max(15, abs(a.values[0])/8):
                self._finish(t, error, 'FAIL timeout')
                self._queue.clear()
                return np.zeros(3, dtype=np.float32)
            return np.array([0, 0, math.copysign(min(.65, max(.4, 2.5*abs(error))), error)], dtype=np.float32)

    def _finish(self, t, error, status):
        angle = self.active.values[0]
        record = dict(target_deg=angle, final_error_deg=math.degrees(error),
                      duration=t-self.started, status=status)
        self.results.append(record)
        self.log(f'[TURN] target={angle:.1f} deg final_error={math.degrees(error):.2f} deg status={status}')
        self.active = None
