"""Student A: native/browser/headless demonstration and keyboard skill shortcuts."""
import argparse
from collections import deque
from pathlib import Path
import threading
import time
import numpy as np
import mujoco
from PIL import Image, ImageDraw, ImageFont
from .platform import Platform, ROOT
from runtime_control import setup_tracking_camera


def main():
    parser=argparse.ArgumentParser()
    modes=parser.add_mutually_exclusive_group()
    modes.add_argument('--gui',action='store_true')
    modes.add_argument('--headless',action='store_true')
    parser.add_argument('--demo',action='store_true')
    parser.add_argument('--duration',type=float,default=60)
    parser.add_argument('--record',type=Path)
    parser.add_argument('--map',default='object_lab')
    args=parser.parse_args()
    lines=deque(maxlen=7)
    def log(s):
        print(s,flush=True); lines.append(s)
    p=Platform(gui=args.gui,map_name=args.map,logger=log)
    # The input thread only queues commands; MuJoCo is owned by the main thread.
    def shortcut(key):
        if key=='m': p.skills.move(.5,0,0,3)
        elif key=='j': p.skills.turn(90)
        elif key=='k': p.skills.turn(180)
        elif key=='x': p.skills.stop()
        elif key in 'wsadqe':
            # Native viewer fallback: a short pulse per key event, no privileged evdev.
            commands={'w':(.5,0,0),'s':(-.5,0,0),'a':(0,.5,0),
                      'd':(0,-.5,0),'q':(0,0,.5),'e':(0,0,-.5)}
            if not p.skills.busy: p.skills.move(*commands[key],.25)
    def terminal():
        while True:
            try: shortcut(input().strip().lower())
            except (EOFError, OSError): break
    if not args.demo: threading.Thread(target=terminal,daemon=True).start()
    log('[KEYS] M: move 3s | J: +90 deg | K: +180 deg | X: cancel')
    log('[CAMERA] dog_front_camera RGB 640x480 at 10 Hz simulation time')
    writer=None; overview=None
    if args.record:
        import imageio.v2 as imageio
        args.record.parent.mkdir(parents=True,exist_ok=True)
        writer=imageio.get_writer(str(args.record),fps=10,codec='libx264',quality=8)
        overview=mujoco.Renderer(p.model,height=480,width=640)
    cam=mujoco.MjvCamera(); cam.lookat[:]=[1.6,0,.3]; cam.distance=6; cam.azimuth=135; cam.elevation=-30
    scheduled=False
    try:
        with p.scene.viewer(args.headless or args.gui,key_callback=lambda k:shortcut(chr(k).lower())) as viewer:
            if not (args.headless or args.gui): setup_tracking_camera(viewer,p.model,'trunk',distance=4)
            while viewer.is_running() and p.data.time<args.duration:
                started=time.monotonic()
                if args.demo and p.data.time>=2 and not scheduled:
                    p.skills.move(.5,0,0,3); p.skills.turn(180); scheduled=True
                manual=None
                if not args.demo:
                    from .platform import base
                    if p.runtime.update_command(base._pressed_keys):
                        manual=[p.config['command'][k] for k in ('linear_x','linear_y','yaw')]
                    else: manual=base.get_commands()
                for action in p.runtime.consume_actions():
                    key={'skill_move':'m','skill_left':'j','skill_back':'k','skill_stop':'x'}.get(action)
                    if key: shortcut(key)
                fresh=p.step(manual)
                if fresh and writer:
                    overview.update_scene(p.data,camera=cam)
                    canvas=Image.new('RGB',(1280,672),'#131b27')
                    canvas.paste(Image.fromarray(overview.render()),(0,32))
                    canvas.paste(Image.fromarray(p.camera.latest().rgb),(640,32))
                    draw=ImageDraw.Draw(canvas)
                    font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf',16) if Path('/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf').exists() else ImageFont.load_default()
                    draw.text((12,7),f'TASK 2 | Scene overview | t={p.data.time:5.1f}s',font=font,fill='white')
                    draw.text((650,7),'Onboard front camera | RGB | 10 Hz',font=font,fill='white')
                    for i,line in enumerate(lines): draw.text((12,520+21*i),line,font=font,fill='#b5efb4')
                    writer.append_data(np.asarray(canvas))
                if not(args.headless or args.gui): viewer.sync()
                if not args.headless:
                    time.sleep(max(0,.005-(time.monotonic()-started)))
    finally:
        if writer: writer.close()
        if overview: overview.close()
        p.close()

if __name__=='__main__': main()
