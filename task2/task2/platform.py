"""Student A: reusable platform. Policy/observation/PD math follows eg/play.py."""
from pathlib import Path
from types import SimpleNamespace
import sys
import numpy as np
import mujoco
import onnxruntime as ort
import yaml
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'eg'))
import play as base
from runtime_control import RuntimeScene, MapSpec, MotorCommandDelay, compute_pd_torques, scale_torque_limits
from .skills import MotionSkills
from .camera import FrontCamera

class Platform:
    def __init__(self, gui=False, camera=True, map_name='object_lab', logger=print, port=8765):
        self.cfg = yaml.safe_load(base.DEFAULT_CONFIG.read_text())
        c = self.cfg
        self.config = base.build_runtime_config(SimpleNamespace(gui=gui, gui_port=port), c['kps'], c['kds'])
        maps = dict(base.MAP_SPECS)
        maps['object_lab'] = MapSpec(ROOT/'task2/assets/scene.xml')
        self.config['map_spawns']['object_lab'] = dict(position=[0,0,.42], quaternion=[1,0,0,0])
        self.config['runtime_ui']['maps']['object_lab'] = 'Task 2 Object Lab'
        self.config['runtime_ui']['default_map'] = map_name
        self.config['runtime_actions'] = {
            'skill_move': {'label':'Timed move 3s', 'shortcut':'m'},
            'skill_left': {'label':'Turn +90 deg', 'shortcut':'j'},
            'skill_back': {'label':'Turn +180 deg', 'shortcut':'k'},
            'skill_stop': {'label':'Cancel skills', 'shortcut':'x'}}
        self.scene = RuntimeScene(base.DEFAULT_ROBOT_XML, maps, self.config, robot_body_name='trunk', robot_cameras=base.ROBOT_CAMERAS).open()
        self.model, self.data, self.runtime = self.scene.model, self.scene.data, self.scene.runtime
        self.model.opt.timestep = c['simulation_dt']
        options=ort.SessionOptions(); options.intra_op_num_threads=1; options.inter_op_num_threads=1
        self.policy = ort.InferenceSession(str(base.DEFAULT_ONNX), sess_options=options, providers=['CPUExecutionProvider'])
        self.input_name = self.policy.get_inputs()[0].name
        self.skills = MotionSkills(logger)
        self.history = base.ObsHistoryBuffer(6,46)
        self.motor_delay = MotorCommandDelay(c['simulation_dt'])
        self.camera = FrontCamera(self.model) if camera else None
        self.runtime.runtime_control(self.model,self.data)
        self.runtime.consume_reset()
        self.reset()

    def reset(self):
        base.reset_robot(self.model,self.data,base.DEFAULT_ANGLES_MUJOCO,
                         self.config['simulation']['initial_position'], self.config['simulation']['initial_quaternion'])
        self.skills.stop(); self.history.reset(); self.motor_delay.reset()
        self.last_action = np.zeros(12,dtype=np.float32)
        self.target = base.DEFAULT_ANGLES_MUJOCO.copy()
        self.count = 0; self.command=np.zeros(3,dtype=np.float32)
        if self.camera: self.camera.reset()
        for _ in range(6): self.history.push(self._obs(self.command))

    def _obs(self,cmd):
        d,c=self.data,self.cfg
        q=d.qpos[3:7]
        return base.build_single_obs(q[[1,2,3,0]],d.qvel[3:6],
            d.qpos[7:19][base.MUJOCO_TO_ISAAC], d.qvel[6:18][base.MUJOCO_TO_ISAAC],
            self.last_action,base.DEFAULT_ANGLES_ISAAC,cmd,np.array(c['cmd_scale']),
            c['ang_vel_scale'],c['dof_pos_scale'],c['dof_vel_scale'],c['clip_obs'],
            height_cmd=self.config['command']['height'])

    def step(self, manual=None):
        state=self.runtime.runtime_control(self.model,self.data)
        if self.runtime.consume_reset(): self.reset()
        if self.count%4==0:
            self.command=self.skills.update(self.data.time,self.data.qpos)
            if manual is not None and not self.skills.busy:
                self.command=np.clip(np.asarray(manual,dtype=np.float32),-1,1)
            self.history.push(self._obs(self.command))
            action=self.policy.run(None,{self.input_name:self.history.get()})[0][0]
            self.last_action=np.clip(action,-10,10).astype(np.float32)
            self.target=(self.last_action*self.cfg['action_scale']+base.DEFAULT_ANGLES_ISAAC)[base.ISAAC_TO_MUJOCO]
        target=self.motor_delay.apply(self.target,state['motor_delay_ms'])
        limits=scale_torque_limits(np.tile([23.7,23.7,35.55],4),state['torque_limit'],reference_limit=35.55)
        self.data.ctrl[:12]=compute_pd_torques(target,self.data.qpos[7:19],self.data.qvel[6:18],state['kp'],state['kd'],motor_strength=state['motor_strength'],torque_limit=limits)
        self.runtime.apply_external_forces(self.model,self.data)
        mujoco.mj_step(self.model,self.data)
        self.count+=1
        return self.camera.update(self.data) if self.camera else False

    def close(self):
        if self.camera: self.camera.close()
        self.scene.close()
