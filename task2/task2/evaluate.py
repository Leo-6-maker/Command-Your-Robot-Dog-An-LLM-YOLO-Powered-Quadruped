"""Student A: measured open/closed-loop turning, using the same ONNX and physics."""
import csv
import math
from .platform import Platform, ROOT
from .skills import yaw_from_qpos, wrap


def main():
    p=Platform(camera=False)
    rows=[]
    try:
        for _ in range(400): p.step()
        previous=yaw_from_qpos(p.data.qpos); rotation=0.
        p.skills.move(0,0,1,4)
        while p.skills.busy:
            p.step(); y=yaw_from_qpos(p.data.qpos)
            rotation+=wrap(y-previous); previous=y
        nominal_rate=abs(rotation)/4
        print(f'[CALIBRATION] wz=1 duration=4 yaw_rate={nominal_rate:.6f} rad/s',flush=True)
        for angle in (90,180,-90):
            for method in ('open','closed'):
                p.reset()
                for _ in range(400): p.step()
                start=p.data.time; previous=yaw_from_qpos(p.data.qpos); rotation=0
                # Empirical nominal rate measured by the calibration below; not cmd_scale.
                duration=abs(math.radians(angle))/nominal_rate
                if method=='open': p.skills.move(0,0,math.copysign(1,angle),duration)
                else: p.skills.turn(angle)
                while p.skills.busy and p.data.time-start<50:
                    p.step(); y=yaw_from_qpos(p.data.qpos)
                    rotation+=wrap(y-previous); previous=y
                action_end=p.data.time
                for _ in range(200):
                    p.step(); y=yaw_from_qpos(p.data.qpos)
                    rotation+=wrap(y-previous); previous=y
                result=dict(method=method,target_deg=angle,actual_deg=math.degrees(rotation),
                            error_deg=angle-math.degrees(rotation),duration_s=action_end-start,
                            settled_height_m=float(p.data.qpos[2]))
                rows.append(result); print('[EVAL]',result,flush=True)
        path=ROOT/'evidence/turn_comparison.csv'
        with path.open('w',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    finally: p.close()

if __name__=='__main__': main()
