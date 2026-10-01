"""Student A: rebuild the report from measured evidence (optional reportlab dependency)."""
from pathlib import Path
import csv,json
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle,Image,PageBreak
from reportlab.lib.styles import getSampleStyleSheet,ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
fontdir=Path("/usr/share/fonts/truetype/liberation")
if fontdir.exists():
    for name,suffix in [("Times-Roman","Regular"),("Times-Bold","Bold"),("Times-Italic","Italic"),("Times-BoldItalic","BoldItalic")]:
        pdfmetrics.registerFont(TTFont(name,str(fontdir/f"LiberationSerif-{suffix}.ttf")))
    pdfmetrics.registerFontFamily("Times-Roman",normal="Times-Roman",bold="Times-Bold",italic="Times-Italic",boldItalic="Times-BoldItalic")
from reportlab.graphics.shapes import Drawing,Rect,String,Line,Polygon

ROOT=Path(__file__).resolve().parents[1]
S=getSampleStyleSheet()
S.add(ParagraphStyle(name='BodyLab',fontName='Times-Roman',fontSize=12,leading=18,spaceAfter=8))
S.add(ParagraphStyle(name='TitleLab',fontName='Times-Bold',fontSize=17,leading=22,spaceAfter=14))
S.add(ParagraphStyle(name='HeadingLab',fontName='Times-Bold',fontSize=13,leading=18,spaceAfter=10))
S.add(ParagraphStyle(name='SmallLab',fontName='Times-Roman',fontSize=10,leading=13,spaceAfter=6))
story=[]; md=[]
def para(text,style='BodyLab'):
    story.append(Paragraph(text,S[style])); md.append(text.replace('<b>','').replace('</b>','')+'\n')
def table(rows,widths):
    md.append('| '+' | '.join(str(v) for v in rows[0])+' |\n| '+' | '.join('---' for _ in rows[0])+' |')
    md.extend('| '+' | '.join(str(v) for v in row)+' |' for row in rows[1:])
    md.append('\n')
    rows=[[Paragraph(str(v),S['SmallLab']) for v in row] for row in rows]
    t=Table(rows,colWidths=widths,repeatRows=1)
    t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e6edf4')),('VALIGN',(0,0),(-1,-1),'TOP'),('LINEBELOW',(0,0),(-1,0),.7,colors.HexColor('#66819b')),('LINEBELOW',(0,1),(-1,-1),.3,colors.HexColor('#cbd5df')),('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6)]))
    story.append(t);story.append(Spacer(1,10))
def page(): story.append(PageBreak());md.append('\n---\n')

para('Task 2: Platform, Scene and Motion Skills','TitleLab')
para('EE5112 MiniLab 1.3 | Semester 1, AY 2026/27','HeadingLab')
para('Contributor: Student A - [insert actual name and matriculation number]. This chapter documents Task 2 only; merge it into the group report.','SmallLab')
para('2.1 Platform and control pipeline','HeadingLab')
para('The implementation extends the course quadruped_mujoco platform [1] at commit dd40180f1121a66373d261e64a9a09eb69b1b2a7. MuJoCo supplies dynamics; the bundled ONNX locomotion policy runs with CPUExecutionProvider. The original observation construction, rear-leg mapping, action scaling and PD torque equations are retained. A motion queue replaces the keyboard command source during autonomous skills.')
d=Drawing(450,155)
boxes=[(0,103,138,43,'Motion queue / keyboard','vx, vy, wz; height'),(157,103,138,43,'46-D observation','6 frames -> 276-D'),(314,103,136,43,'ONNX policy, 50 Hz','12 joint actions'),(314,22,136,43,'Targets + rear-leg map','default + 0.25 x action'),(157,22,138,43,'PD + torque limits','200 Hz; decimation 4'),(0,22,138,43,'MuJoCo physics','qpos / qvel feedback')]
for x,y,w,h,a,b in boxes:
 d.add(Rect(x,y,w,h,fillColor=colors.HexColor('#eff4f8'),strokeColor=colors.HexColor('#58718a')))
 d.add(String(x+w/2,y+26,a,fontName='Times-Bold',fontSize=10,textAnchor='middle'))
 d.add(String(x+w/2,y+11,b,fontName='Times-Roman',fontSize=9,textAnchor='middle'))
for x1,y1,x2,y2 in [(138,124,157,124),(295,124,314,124),(382,103,382,65),(314,43,295,43),(157,43,138,43)]:
 d.add(Line(x1,y1,x2,y2,strokeColor=colors.HexColor('#58718a')))
 if x2>x1: pts=[x2,y2,x2-5,y2+3,x2-5,y2-3]
 elif x2<x1: pts=[x2,y2,x2+5,y2+3,x2+5,y2-3]
 else: pts=[x2,y2,x2-3,y2+5,x2+3,y2+5]
 d.add(Polygon(pts,fillColor=colors.HexColor('#58718a')))
d.add(String(0,4,'State feedback forms the next observation and closes the yaw controller.',fontName='Times-Italic',fontSize=10))
story.append(d)
md.append('```mermaid\nflowchart LR\n A[Motion queue / keyboard] --> B[46-D observation x 6 frames] --> C[ONNX 50 Hz] --> D[Rear-leg remap] --> E[PD 200 Hz] --> F[MuJoCo] --> B\n```')
para('Figure 2.1. The local control pipeline. Policy decisions are held for four 5 ms physics steps.','SmallLab')
table([['Observation slice','Content / scale'],['0:3; 3:6; 6:9','Velocity command x [2,2,0.25]; body angular velocity x 0.25; projected gravity'],['9:21; 21:33; 33:45','Joint position deviation; joint velocity x 0.05; previous action'],['45','(height command - 0.25) / 0.1']], [130,321])
para('Policy joint order is FL, FR, RL, RR, whereas MuJoCo uses FL, FR, RR, RL. Indices [0,1,2,3,4,5,9,10,11,6,7,8] reorder observations and output targets. Without this swap, rear-leg actions are applied to the opposite legs. PD uses Kp=40, Kd=1 and limits of 23.7 Nm (hip/thigh) and 35.55 Nm (calf).','SmallLab')
page()
para('2.2 Onboard camera and detectable scene','TitleLab')
para('FrontCamera renders dog_front_camera, rigidly attached to trunk, at 640 x 480 RGB. It samples every 0.1 s of simulation time (20 physics steps). Ten Hz reduces rendering work relative to 200 Hz while providing frequent updates for object search. No wall-clock 10 Hz performance claim is made: slow rendering slows the simulation. latest() returns a locked copy with a simulation timestamp and sequence number.')
para('The custom MJCF contains two chairs and an orange basketball. Chairs are original combinations of a seat, backrest and four legs; the ball has dark seams. External mesh downloads are unnecessary because the complete rendered shapes passed the actual COCO detector test. This does not imply that an arbitrary coloured primitive will be recognised.')
story.append(Image(str(ROOT/'evidence/detections.png'),width=320,height=240))
md.append('![YOLO detections](evidence/detections.png)')
para('Figure 2.2. YOLO11n detections from the live front camera after 2 s of simulation. CPU inference, imgsz=640, confidence threshold=0.25. The RGB array is converted to BGR before NumPy-based YOLO inference.','SmallLab')
dets=json.loads((ROOT/'evidence/detections.json').read_text())['detections']
chairs=sorted([d for d in dets if d['coco_class']=='chair'],key=lambda x:x['bbox'][0]);ball=[d for d in dets if d['coco_class']=='sports ball'][0]
table([['Object','COCO class','Centre (x,y,z), m','Confidence'],['Green chair','chair','(3, 1, 0.5)',f"{chairs[0]['confidence']:.3f}"],['Red chair','chair','(3, -1, 0.5)',f"{chairs[1]['confidence']:.3f}"],['Orange basketball','sports ball','(2.5, 0, 0.16)',f"{ball['confidence']:.3f}"]],[100,88,170,93])
para('Object centres are recorded in assets/objects.json for distance logging and evaluation only. Task 4 must consume latest() as its sole image source and infer colour from pixels; the class detector alone does not provide colour. Scene labels in this table describe authored objects, not an evaluated colour-grounding algorithm.','SmallLab')
page()
para('2.3 Motion API and measured turning error','TitleLab')
para('move(vx, vy, wz, duration) adds a timed command to a thread-safe FIFO queue. Commands are normalised to [-1,1]; they are not guaranteed physical velocities. The control loop checks simulation time, advances the queue in order and returns zero velocity when idle. turn(angle_deg) reads the root quaternion and accumulates wrapped yaw differences, preserving turn direction through the +/-180 degree boundary and supporting turns up to +/-720 degrees.')
para('The turn controller saturates at |wz|=0.65 and uses a minimum nonzero magnitude of 0.40 to overcome the learned gait response dead zone. It stops at an instantaneous yaw error of at most 2 degrees and logs [TURN]. A timeout clears remaining actions and reports FAIL. This is a heading skill; it does not freeze the robot pose or actively hold heading after completion.')
para('For a fair open-loop baseline, a four-second left turn at wz=1 measured a mean rate of 0.651790 rad/s. Each open-loop duration was then |target angle| / calibrated rate. Both methods start after two seconds of settling; the table measures yaw again one second after the command ends. Each condition is one deterministic trial, not a statistical robustness study.')
rows=list(csv.DictReader((ROOT/'evidence/turn_comparison.csv').open()))
table([['Method','Target','Measured yaw','Signed error','Time, s']]+[[r['method'],f"{float(r['target_deg']):.0f} deg",f"{float(r['actual_deg']):.2f} deg",f"{float(r['error_deg']):.2f} deg",f"{float(r['duration_s']):.2f}"] for r in rows],[70,74,110,110,87])
para('The calibrated open-loop left turns were accurate (0.95 and -1.24 degrees), but reusing that timing for a right turn produced 21.30 degrees error. Direction-dependent gait dynamics invalidate a single universal timing constant. Closed-loop completion errors were 1.92, 1.89 and -1.99 degrees. After one second, errors increased to 4.26, 5.12 and -6.56 degrees because of gait relaxation. Feedback reduced the large right-turn error, but was slower and did not outperform calibrated open loop in every test.')
para('Demo: move(0.5,0,0,3), then turn(180); recorded completion error 1.93 degrees, SUCCESS.','SmallLab')
page()
para('2.4 Reproduction, integration and evidence','TitleLab')
para('The tested environment is Linux with Python 3.12, MuJoCo 3.14.0, ONNX Runtime 1.30.0 and Ultralytics 8.4.160. Dependency pins are in requirements-task2.txt; environment-tested.txt records the resolved environment. Install CPU Torch/Torchvision first, then install the repository editable and the Task 2 requirements. The ONNX policy and YOLO11n weights are included.')
table([['Purpose','Command from repository root'],['Native / browser','python -m task2.run<br/>MUJOCO_GL=egl python -m task2.run --gui'],['Scene verification','MUJOCO_GL=egl python -m task2.verify_scene'],['Turn comparison','MUJOCO_GL=egl python -m task2.evaluate'],['Unit checks','python -m pytest -q task2/test_skills.py'],['Automated video','MUJOCO_GL=egl python -m task2.run --headless --demo --duration 22 --record evidence/Video_Task2.mp4']],[110,341])
para('The original eg/play.py launched successfully in native mode and the browser service ran with --gui. API checks exercised W/S/A/D/Q/E, Race Track, Stairs and Cross Slope, and selected all three onboard cameras. Separate named-camera renders are included. The six unit tests passed, covering queue timing, cancellation, yaw wrapping/full turns, invalid inputs and timeout. Browser skill actions also completed a move and a 180-degree turn (1.87 degrees error).','SmallLab')
para('Task 3 should enqueue actions from its own input/LLM thread while the main simulation thread continuously calls Platform.step(). Task 4 reads FrontCamera.latest(), rejects stale frames and issues short motion commands. Ground-truth object centres are not read by either the motion controller or the camera pipeline. Task 3/4 logic and their evaluation are outside this implementation.','SmallLab')
para('<b>Submission limitation.</b> Video_Task2.mp4 is an offscreen simulation recording with synchronised console text, not a desktop terminal recording. To meet the literal terminal-visible requirement, record the browser/native window beside a terminal, trigger M then K, and retain the [TURN] SUCCESS line. The supplied evidence does not claim that the student has personally performed that recording.','SmallLab')
para('<b>AI Usage Declaration (review before submission).</b> OpenAI Codex assisted with implementation, scene construction, debugging, test execution and drafting this Task 2 chapter. The submitting student must review the code, fill in their identity and actual contribution, and be able to explain the submitted work.','SmallLab')
para('References','HeadingLab')
para('[1] Course platform: https://github.com/aoqianz/quadruped_mujoco (commit recorded on page 1).<br/>[2] MuJoCo documentation: https://mujoco.readthedocs.io/<br/>[3] Ultralytics documentation and YOLO11n COCO weights: https://docs.ultralytics.com/<br/>[4] EE5112 MiniLab 1.3, Semester 1 AY2026/27, Task 2 specification.','SmallLab')

def footer(c,doc):
 c.setFont('Times-Roman',9); c.setFillColor(colors.HexColor('#5a6874'))
 c.drawString(72,38,'EE5112 MiniLab 1.3 | Task 2 | Student A')
 c.drawRightString(523,38,str(doc.page))
SimpleDocTemplate(str(ROOT/'Task2_Report.pdf'),pagesize=(595.28,841.89),leftMargin=72,rightMargin=72,topMargin=72,bottomMargin=72).build(story,onFirstPage=footer,onLaterPages=footer)
(ROOT/'Task2_Report.md').write_text('\n'.join(md)+'\n\nSee evidence/turn_comparison.csv and evidence/detections.json for numerical tables.\n')
