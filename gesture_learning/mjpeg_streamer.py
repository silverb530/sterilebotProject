#!/usr/bin/env python3
# =============================================================
#  SterileBot - MJPEG 스트리밍 모듈
#  파일명: mjpeg_streamer.py
#
#  ▶ 역할
#    Zone_tracker 가 그리는 화면(display Mat)을 MJPEG over HTTP 로 송출.
#    WPF 모니터(또는 웹 브라우저)가 받아서 표시.
#
#  ▶ 사용법 (Zone_tracker.py 에서)
#    from mjpeg_streamer import MjpegStreamer
#    streamer = MjpegStreamer(port=8090)   # main() 시작 부분
#    streamer.start()
#    ...
#    # 매 프레임 display 그린 직후:
#    streamer.update(display)
#    ...
#    # 종료 시:
#    streamer.stop()
#
#  ▶ 수신 URL
#    브라우저:  http://<PC_IP>:8090/         (테스트용 페이지)
#    스트림:    http://<PC_IP>:8090/stream   (MJPEG, WPF/브라우저가 직접 사용)
#    단일 프레임: http://<PC_IP>:8090/frame.jpg
#
#  ▶ 의존성
#    pip install opencv-python   (이미 Zone_tracker 가 사용 중)
#    표준 라이브러리 http.server 사용 — 추가 설치 없음
# =============================================================

import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import cv2


class MjpegStreamer:
    def __init__(self, port=8090, quality=70, fps_limit=25):
        """
        port      : 스트리밍 포트
        quality   : JPEG 품질 (0~100, 낮을수록 데이터 작음)
        fps_limit : 송출 최대 FPS (네트워크 부하 조절)
        """
        self.port      = port
        self.quality   = quality
        self.fps_limit = fps_limit

        self._latest_jpeg = None          # 최신 인코딩된 JPEG 바이트
        self._lock        = threading.Lock()
        self._server      = None
        self._thread      = None
        self._running     = False
        self._last_encode = 0.0

    # ─────────────────────────────────────
    #  프레임 갱신 (Zone_tracker 가 매 프레임 호출)
    # ─────────────────────────────────────
    def update(self, frame):
        """display(BGR Mat)를 받아 JPEG로 인코딩해 보관. fps_limit 으로 스로틀."""
        now = time.time()
        min_interval = 1.0 / self.fps_limit
        if now - self._last_encode < min_interval:
            return
        self._last_encode = now

        try:
            ok, buf = cv2.imencode(
                ".jpg", frame,
                [int(cv2.IMWRITE_JPEG_QUALITY), self.quality]
            )
            if ok:
                with self._lock:
                    self._latest_jpeg = buf.tobytes()
        except Exception as e:
            print(f"[MJPEG] 인코딩 실패: {e}")

    def get_latest(self):
        with self._lock:
            return self._latest_jpeg

    # ─────────────────────────────────────
    #  서버 시작 / 종료
    # ─────────────────────────────────────
    def start(self):
        if self._running:
            return
        self._running = True
        streamer = self

        class Handler(BaseHTTPRequestHandler):
            # 로그 끄기 (콘솔 깔끔하게)
            def log_message(self, *args):
                pass

            def do_GET(self):
                if self.path in ("/stream", "/stream.mjpg"):
                    self._serve_stream()
                elif self.path in ("/frame.jpg", "/frame"):
                    self._serve_single()
                elif self.path in ("/", "/index.html"):
                    self._serve_index()
                else:
                    self.send_error(404)

            def _serve_stream(self):
                self.send_response(200)
                self.send_header(
                    "Content-Type",
                    "multipart/x-mixed-replace; boundary=frame"
                )
                self.send_header("Cache-Control", "no-cache, private")
                self.send_header("Pragma", "no-cache")
                self.end_headers()
                try:
                    while streamer._running:
                        jpg = streamer.get_latest()
                        if jpg is None:
                            time.sleep(0.05)
                            continue
                        self.wfile.write(b"--frame\r\n")
                        self.wfile.write(b"Content-Type: image/jpeg\r\n")
                        self.wfile.write(
                            f"Content-Length: {len(jpg)}\r\n\r\n".encode()
                        )
                        self.wfile.write(jpg)
                        self.wfile.write(b"\r\n")
                        time.sleep(1.0 / streamer.fps_limit)
                except (BrokenPipeError, ConnectionResetError):
                    pass  # 클라이언트 끊김 — 정상
                except Exception:
                    pass

            def _serve_single(self):
                jpg = streamer.get_latest()
                if jpg is None:
                    self.send_error(503, "No frame yet")
                    return
                self.send_response(200)
                self.send_header("Content-Type", "image/jpeg")
                self.send_header("Content-Length", str(len(jpg)))
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()
                self.wfile.write(jpg)

            def _serve_index(self):
                html = (
                    "<!doctype html><html><head><meta charset='utf-8'>"
                    "<title>Zone Tracker Stream</title>"
                    "<style>body{margin:0;background:#111;}"
                    "img{width:100vw;height:100vh;object-fit:contain;}</style>"
                    "</head><body>"
                    "<img src='/stream'>"
                    "</body></html>"
                ).encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(html)))
                self.end_headers()
                self.wfile.write(html)

        def serve():
            try:
                self._server = ThreadingHTTPServer(("0.0.0.0", self.port), Handler)
                print(f"[MJPEG] 스트리밍 시작 — 포트 {self.port}")
                print(f"[MJPEG]   브라우저: http://localhost:{self.port}/")
                print(f"[MJPEG]   스트림:   http://<PC_IP>:{self.port}/stream")
                self._server.serve_forever()
            except Exception as e:
                print(f"[MJPEG] 서버 오류: {e}")

        self._thread = threading.Thread(target=serve, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._server:
            try:
                self._server.shutdown()
            except Exception:
                pass
        print("[MJPEG] 스트리밍 종료")


# ─────────────────────────────────────
#  단독 테스트 (웹캠 직접 송출)
# ─────────────────────────────────────
if __name__ == "__main__":
    import sys
    cam = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    print(f"[TEST] 웹캠 {cam} 을 MJPEG 송출 — http://localhost:8090/")
    cap = cv2.VideoCapture(cam)
    s = MjpegStreamer(port=8090)
    s.start()
    try:
        while True:
            ret, frame = cap.read()
            if ret:
                # 테스트용 텍스트 오버레이
                cv2.putText(frame, "MJPEG TEST", (20, 40),
                            cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 157), 2)
                s.update(frame)
            time.sleep(0.02)
    except KeyboardInterrupt:
        pass
    finally:
        s.stop()
        cap.release()