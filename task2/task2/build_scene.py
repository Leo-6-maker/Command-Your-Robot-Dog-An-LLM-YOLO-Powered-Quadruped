"""Student A: regenerate the original object MJCF and evaluation metadata."""
from pathlib import Path
import json
p=Path(__file__).resolve().parent/'assets'
# Original, explicitly modeled chairs: seats, backrests and four legs.
parts=['<mujoco model="task2_object_lab"><asset><texture name="floor_tex" type="2d" builtin="checker" rgb1=".65 .65 .62" rgb2=".8 .8 .77" width="512" height="512"/><material name="floor_mat" texture="floor_tex" texrepeat="8 8" reflectance=".05"/></asset><worldbody><geom name="floor" type="plane" size="12 12 .1" material="floor_mat"/>']
objects=[]
for name,color,pos,rgba in [('green_chair','green',(3,1,0),'.06 .55 .10 1'),('red_chair','red',(3,-1,0),'.75 .04 .04 1')]:
    parts.append(f'<body name="{name}" pos="{pos[0]} {pos[1]} 0" euler="0 0 -90">')
    def box(n,loc,size):
        parts.append(f'<geom name="{name}_{n}" type="box" pos="{loc}" size="{size}" rgba="{rgba}"/>')
    box('seat','0 0 .46','.25 .24 .035')
    box('back','0 .215 .75','.25 .025 .27')
    for i,(x,y) in enumerate([(-.21,-.2),(.21,-.2),(-.21,.2),(.21,.2)]):
        box(f'leg{i}',f'{x} {y} .22','.022 .022 .22')
    parts.append('</body>')
    objects.append(dict(id=name,coco_class='chair',color=color,position=[pos[0],pos[1],.5]))
# Basketball with dark great-circle seams, a recognisable sports ball silhouette.
parts.append('<body name="orange_ball" pos="2.5 0 .16"><geom name="ball" type="sphere" size=".16" rgba=".9 .28 .025 1"/>')
import math
for axis in range(3):
    for i in range(64):
        a,b=2*math.pi*i/64,2*math.pi*(i+1)/64
        def point(t):
            v=[.1605*math.cos(t),.1605*math.sin(t),0]
            return [v[(j+axis)%3] for j in range(3)]
        xyz=point(a)+point(b)
        parts.append('<geom type="capsule" fromto="'+' '.join(map(str,xyz))+'" size=".002" rgba=".08 .05 .03 1" contype="0" conaffinity="0"/>')
parts.append('</body></worldbody></mujoco>')
objects.append(dict(id='orange_ball',coco_class='sports ball',color='orange',position=[2.5,0,.16]))
(p/'scene.xml').write_text('\n'.join(parts))
(p/'objects.json').write_text(json.dumps({'usage':'Logging/evaluation only; never use positions for steering','objects':objects},indent=2))
