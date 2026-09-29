import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dataclasses import asdict
import numpy as np
import mujoco
from PIL import Image
from task3.run import _import_task2, _task2_assets_dir
from task4 import YoloColorDetector, annotate_frame

assets = _task2_assets_dir(_import_task2(Path('../task2_runtime/task2')))
from task2.platform import Platform
p = Platform()
detector = YoloColorDetector(str(assets/'yolo11n.pt'))
out = Path('runs/camera_probe_01')
out.mkdir(exist_ok=False)
cam = p.model.camera('dog_front_camera')
original_quat = cam.quat.copy()
rows = []
try:
 for distance in (3.0, 1.0, .75):
  p.config['simulation']['initial_position'] = [3-distance, 1, .42]
  p.reset()
  for _ in range(400): p.step()
  for fovy, level in [(80,False),(100,False),(110,True),(120,True),(100,True)]:
   cam.fovy[0] = fovy
   if level:
    # Camera axes: image right=-body Y, image up=body Z, viewing direction=body X.
    mujoco.mju_mat2Quat(cam.quat, np.array([[0.,0.,-1.],[-1.,0.,0.],[0.,1.,0.]]).flatten())
   else: cam.quat[:] = original_quat
   mujoco.mj_forward(p.model, p.data)
   p.camera.next_time = 0
   p.camera.update(p.data)
   rgb = p.camera.latest().rgb
   detections = detector.detect(rgb)
   name = f'd{distance:g}_f{fovy}_level{int(level)}'
   Image.fromarray(annotate_frame(rgb,detections)).save(out/f'{name}.png')
   row = dict(distance=distance,fovy=fovy,level=level,detections=[asdict(d) for d in detections])
   rows.append(row)
   print('[PROBE]',name, [(d.class_name,d.color,round(d.confidence,2),round((d.bbox[3]-d.bbox[1])/480,2)) for d in detections],flush=True)
 (out/'results.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
finally: p.close()
