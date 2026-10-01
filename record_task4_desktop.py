"""Capture the real Windows desktop while Task 3 terminal and MuJoCo are visible."""

import argparse
from pathlib import Path
import subprocess
import time

import cv2
import imageio_ffmpeg
import numpy as np
from PIL import ImageGrab


parser = argparse.ArgumentParser()
parser.add_argument('output', type=Path)
parser.add_argument('--stop-file', type=Path, required=True)
parser.add_argument('--max-seconds', type=int, default=180)
args = parser.parse_args()
args.output.parent.mkdir(parents=True, exist_ok=True)
if args.output.exists():
    parser.error('output already exists')
if args.stop_file.exists():
    parser.error('stop file already exists')

size = ImageGrab.grab().size
fps = 8
command = [imageio_ffmpeg.get_ffmpeg_exe(), '-hide_banner', '-loglevel', 'error',
           '-y', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s', f'{size[0]}x{size[1]}',
           '-r', str(fps), '-i', '-', '-an', '-c:v', 'libx264', '-preset', 'ultrafast',
           '-crf', '24', '-pix_fmt', 'yuv420p', str(args.output)]
encoder = subprocess.Popen(command, stdin=subprocess.PIPE)
started = time.monotonic()
frames = 0
try:
    while not args.stop_file.exists() and time.monotonic() - started < args.max_seconds:
        image = cv2.cvtColor(np.asarray(ImageGrab.grab()), cv2.COLOR_RGB2BGR)
        encoder.stdin.write(cv2.resize(image, size, interpolation=cv2.INTER_AREA).tobytes())
        frames += 1
        time.sleep(max(0, started + frames / fps - time.monotonic()))
finally:
    encoder.stdin.close()
    encoder.wait(timeout=30)
print(f'frames={frames} exit={encoder.returncode} output={args.output}', flush=True)
