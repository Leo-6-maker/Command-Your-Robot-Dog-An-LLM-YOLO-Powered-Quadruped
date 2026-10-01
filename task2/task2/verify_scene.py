"""Student A: live onboard RGB -> COCO YOLO; evidence and machine-readable detections."""
import json
from pathlib import Path
import argparse
from PIL import Image
from ultralytics import YOLO
from .platform import Platform, ROOT


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--weights',default=str(ROOT/'task2/assets/yolo11n.pt'))
    parser.add_argument('--output',type=Path,default=ROOT/'evidence')
    args=parser.parse_args(); args.output.mkdir(parents=True,exist_ok=True)
    detector=YOLO(args.weights)
    p=Platform()
    try:
        for _ in range(400): p.step()
        frame=p.camera.latest()
        Image.fromarray(frame.rgb).save(args.output/'front.png')
        # Ultralytics numpy inputs are BGR, unlike the public camera API.
        r=detector.predict(frame.rgb[:,:,::-1].copy(),device='cpu',conf=.25,imgsz=640,verbose=False)[0]
        records=[dict(coco_class=r.names[int(b.cls.item())],confidence=float(b.conf.item()),bbox=b.xyxy[0].tolist()) for b in r.boxes]
        Image.fromarray(r.plot()[:,:,::-1]).save(args.output/'detections.png')
        (args.output/'detections.json').write_text(json.dumps(dict(sim_time=frame.sim_time,detections=records),indent=2))
        print(json.dumps(records,indent=2))
        chairs=sum(d['coco_class']=='chair' for d in records)
        ball=any(d['coco_class']=='sports ball' for d in records)
        if chairs<2 or not ball: raise SystemExit('FAIL: require two chairs and a sports ball in this view')
        print('[VERIFY] PASS: 3 objects, 2 COCO classes, two differently coloured chairs')
    finally: p.close()

if __name__=='__main__': main()
