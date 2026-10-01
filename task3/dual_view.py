"""Show Task 2's rear view beside live onboard RGB without changing navigation."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
import threading
from urllib.request import Request, urlopen

from PIL import Image


class DualViewServer:
    def __init__(self, front_camera, detector, task2_port: int, port: int):
        self.task2_port = task2_port
        page = f"""<!doctype html><html lang="en"><meta charset="utf-8">
<title>Task4 Dual View</title><style>
body{{margin:0;background:#0b1422;color:#f0f6ff;font:16px Arial,sans-serif}}
main{{height:100vh;display:grid;grid-template-rows:1fr 1fr;gap:6px;padding:6px;box-sizing:border-box}}
section{{min-height:0;display:flex;flex-direction:column;background:#15243a;border:1px solid #38516b;border-radius:8px;overflow:hidden}}
header{{padding:7px 12px;font-weight:bold;background:#1e3451}}
img{{min-height:0;width:100%;flex:1;object-fit:contain;background:#02060c}}
</style><main>
<section><header>Rear overhead · robot and scene</header>
<img src="http://127.0.0.1:{task2_port}/api/stream.mjpg"></section>
<section><header>dog_front_camera · latest YOLO detections</header>
<img id="front"></section></main>
<script>const front=document.getElementById('front');
function refresh(){{front.src='/front.jpg?t='+Date.now()}}
front.onload=()=>setTimeout(refresh,200);
front.onerror=()=>setTimeout(refresh,500);
refresh();</script></html>""".encode()

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path == "/":
                    content, kind = page, "text/html; charset=utf-8"
                elif self.path.startswith("/front.jpg"):
                    annotated = detector.latest_annotated_frame
                    if annotated is None:
                        frame = front_camera.latest()
                        if frame is None:
                            self.send_response(204)
                            self.end_headers()
                            return
                        annotated = frame.rgb
                    output = BytesIO()
                    Image.fromarray(annotated).save(output, format="JPEG", quality=75)
                    content, kind = output.getvalue(), "image/jpeg"
                else:
                    self.send_error(404)
                    return
                self.send_response(200)
                self.send_header("Content-Type", kind)
                self.send_header("Content-Length", str(len(content)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                try:
                    self.wfile.write(content)
                except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
                    pass  # Browser closed or replaced a frame during refresh.

            def log_message(self, *_):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
        self.url = f"http://127.0.0.1:{port}/"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def start(self):
        self.thread.start()
        request = Request(
            f"http://127.0.0.1:{self.task2_port}/api/camera",
            data=b'{"camera":"dog_rear_overhead_camera"}',
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=5):
            pass

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
