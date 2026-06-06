#!/usr/bin/env python3
"""
SterileBot - 쓰러짐 감지 모듈
MediaPipe Pose 기반, CCTV 대각선 설치 환경

실행:
  python3 fall_detection.py
  python3 fall_detection.py --camera 1
  python3 fall_detection.py --stream http://192.168.0.27:5001/camera/stream
"""

import cv2
import mediapipe as mp
import time
import argparse
import socket
import threading
import struct
import json

# ── 설정값 ──────────────────────────────────────────────────
CAMERA_INDEX       = 1
FALL_DIFF_Y        = 0.25
FALL_BOX_RATIO     = 0.15
FALL_DELTA_Y       = 0.03
CONFIRM_SEC        = 2.0
VISIBILITY_MIN     = 0.3
CONDITION_REQUIRE  = 2

# ── TCP 설정 ─────────────────────────────────────────────────
TCP_PORT           = 9999    # 보안실 PC와 통신할 포트
TCP_HOST           = "0.0.0.0"

IDX = {
    "nose":        0,
    "l_shoulder": 11,
    "r_shoulder": 12,
    "l_hip":      23,
    "r_hip":      24,
    "l_knee":     25,
    "r_knee":     26,
    "l_ankle":    27,
    "r_ankle":    28,
}


# ── TCP 스트리밍 서버 ─────────────────────────────────────────
class TcpStreamServer:
    """
    쓰러짐 확정 시에만 활성화되는 TCP 서버.
    클라이언트(보안실 WPF)가 연결되면 JPEG 프레임을 전송한다.
    프로토콜: [4바이트 BE 길이][JPEG 데이터]
    첫 연결 시 JSON 상태 메시지를 먼저 전송.
    """
    def __init__(self):
        self._clients: list[socket.socket] = []
        self._lock = threading.Lock()
        self._server: socket.socket | None = None
        self._running = False
        self._thread: threading.Thread | None = None
        self.active = False  # 외부에서 확인용

    def start(self, timestamp: str):
        if self._running:
            return
        self._running = True
        self.active = True
        self._thread = threading.Thread(target=self._serve, args=(timestamp,), daemon=True)
        self._thread.start()
        print(f"\n[TCP] 보안실 서버 시작 (포트 {TCP_PORT})")

    def stop(self):
        self._running = False
        self.active = False
        with self._lock:
            for c in self._clients:
                try: c.close()
                except: pass
            self._clients.clear()
        if self._server:
            try: self._server.close()
            except: pass
        print("[TCP] 서버 종료")

    def send_frame(self, frame_bgr):
        """현재 연결된 모든 클라이언트에 JPEG 프레임 전송"""
        if not self._clients:
            return
        ret, buf = cv2.imencode('.jpg', frame_bgr, [cv2.IMWRITE_JPEG_QUALITY, 70])
        if not ret:
            return
        data = buf.tobytes()
        header = struct.pack('>I', len(data))  # 4바이트 big-endian 길이
        packet = header + data

        dead = []
        with self._lock:
            for c in self._clients:
                try:
                    c.sendall(packet)
                except:
                    dead.append(c)
            for c in dead:
                self._clients.remove(c)
                try: c.close()
                except: pass

    def _serve(self, timestamp: str):
        self._server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self._server.bind((TCP_HOST, TCP_PORT))
            self._server.listen(5)
            self._server.settimeout(1.0)
            while self._running:
                try:
                    conn, addr = self._server.accept()
                    print(f"[TCP] 보안실 연결: {addr}")
                    # 첫 메시지: 비상 상태 JSON
                    msg = json.dumps({
                        "type": "emergency",
                        "ts": timestamp
                    }).encode() + b'\n'
                    header = struct.pack('>I', len(msg))
                    conn.sendall(header + msg)
                    with self._lock:
                        self._clients.append(conn)
                except socket.timeout:
                    continue
                except Exception as e:
                    if self._running:
                        print(f"[TCP] 오류: {e}")
        finally:
            try: self._server.close()
            except: pass


# ── 비상 대응 ────────────────────────────────────────────────
_tcp_server = TcpStreamServer()

def trigger_emergency(timestamp: str):
    print("\n" + "="*50)
    print("  ⚠  쓰러짐 확정 → 보안실 TCP 알림")
    print("="*50)
    _tcp_server.start(timestamp)


# ── 메인 감지 클래스 ─────────────────────────────────────────
class FallDetector:
    def __init__(self):
        self.mp_pose = mp.solutions.pose
        self.mp_draw = mp.solutions.drawing_utils
        self.pose    = self.mp_pose.Pose(
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
            model_complexity=0
        )
        self.fall_start      = None
        self.is_fallen       = False
        self.alerted         = False
        self.prev_shoulder_y = None

    def get_landmark(self, lm, key):
        l = lm[IDX[key]]
        return l.x, l.y, l.visibility

    def check_conditions(self, lm):
        debug = {}

        _, l_sh_y, l_sh_v = self.get_landmark(lm, "l_shoulder")
        _, r_sh_y, r_sh_v = self.get_landmark(lm, "r_shoulder")
        _, l_hp_y, l_hp_v = self.get_landmark(lm, "l_hip")
        _, r_hp_y, r_hp_v = self.get_landmark(lm, "r_hip")
        l_sh_x, _, _      = self.get_landmark(lm, "l_shoulder")
        r_sh_x, _, _      = self.get_landmark(lm, "r_shoulder")

        vis_shoulder = (l_sh_v + r_sh_v) / 2
        vis_hip      = (l_hp_v + r_hp_v) / 2

        if vis_shoulder < VISIBILITY_MIN or vis_hip < VISIBILITY_MIN:
            return 0, [False, False, False], {"error": "가시성 부족"}

        shoulder_y = (l_sh_y + r_sh_y) / 2
        hip_y      = (l_hp_y + r_hp_y) / 2

        # ① 어깨-골반 Y 차이 (수평 여부)
        diff_y = abs(shoulder_y - hip_y)
        cond1  = diff_y < FALL_DIFF_Y
        debug["diff_y"] = diff_y

        # ② 코 Y좌표 (누우면 코가 화면 아래로)
        nose_x, nose_y_val, nose_v = self.get_landmark(lm, "nose")
        cond2 = nose_y_val > 0.28
        debug["nose_y"]    = nose_y_val
        debug["box_ratio"] = nose_y_val  # 터미널 출력 호환용

        # ③ 어깨 Y 급격한 하강
        if self.prev_shoulder_y is not None:
            delta_y = shoulder_y - self.prev_shoulder_y
            cond3   = delta_y > FALL_DELTA_Y
        else:
            delta_y = 0
            cond3   = False
        debug["delta_y"] = delta_y

        self.prev_shoulder_y = shoulder_y

        count = sum([cond1, cond2, cond3])
        return count, [cond1, cond2, cond3], debug

    def update(self, lm):
        count, conds, debug = self.check_conditions(lm)

        dy  = debug.get("diff_y", 0)
        ny  = debug.get("nose_y", 0)
        dlt = debug.get("delta_y", 0)
        print(f"dy={dy:.3f}(기준<{FALL_DIFF_Y}) nose_y={ny:.3f}(기준>0.28) Δ={dlt:.4f}  조건충족={count}/{CONDITION_REQUIRE}", end="\r")

        if count >= CONDITION_REQUIRE:
            if self.fall_start is None:
                self.fall_start = time.time()

            elapsed = time.time() - self.fall_start
            pct     = min(1.0, elapsed / CONFIRM_SEC)

            if elapsed >= CONFIRM_SEC and not self.alerted:
                self.is_fallen = True
                self.alerted   = True
                ts = time.strftime("%Y-%m-%d %H:%M:%S")
                trigger_emergency(ts)

            if self.is_fallen:
                return "FALL CONFIRMED", (0, 0, 220), 1.0, True
            else:
                remaining = CONFIRM_SEC - elapsed
                return f"FALL SUSPECTED ({remaining:.1f}s)", (0, 140, 255), pct, False
        else:
            self.fall_start = None
            self.is_fallen  = False
            self.alerted    = False
            dy  = debug.get("diff_y",  0)
            br  = debug.get("nose_y",  0)
            dlt = debug.get("delta_y", 0)
            txt = f"NORMAL  dy={dy:.2f} nose={br:.2f} Δ={dlt:.3f}  ({count}/{CONDITION_REQUIRE})"
            return txt, (0, 200, 80), 0.0, False


# ── 실행 ─────────────────────────────────────────────────────
def main(camera_src):
    cap = cv2.VideoCapture(camera_src, cv2.CAP_DSHOW)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    detector = FallDetector()
    mp_draw  = mp.solutions.drawing_utils
    mp_pose  = mp.solutions.pose

    flash_state  = False
    last_flash_t = time.time()

    print("[Fall Detection Start]")
    print(f"  Camera: {camera_src}")
    print(f"  TCP Port: {TCP_PORT}")
    print(f"  Quit: q\n")

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            print("[ERROR] No frame")
            break

        h, w = frame.shape[:2]
        rgb  = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        res  = detector.pose.process(rgb)

        status, color, pct, fallen = "NO PERSON", (150, 150, 150), 0.0, False

        if res.pose_landmarks:
            lm = res.pose_landmarks.landmark

            try:
                mp_draw.draw_landmarks(
                    frame, res.pose_landmarks,
                    mp_pose.POSE_CONNECTIONS,
                    mp_draw.DrawingSpec(color=(0,255,150), thickness=2, circle_radius=3),
                    mp_draw.DrawingSpec(color=(0,180,100), thickness=2)
                )
            except Exception:
                pass

            l_sh = lm[IDX["l_shoulder"]]
            r_sh = lm[IDX["r_shoulder"]]
            l_hp = lm[IDX["l_hip"]]
            r_hp = lm[IDX["r_hip"]]
            sh_y = int((l_sh.y + r_sh.y) / 2 * h)
            hp_y = int((l_hp.y + r_hp.y) / 2 * h)
            cv2.line(frame, (0, sh_y), (w, sh_y), (255, 200, 0), 1)
            cv2.line(frame, (0, hp_y), (w, hp_y), (0, 200, 255), 1)
            cv2.putText(frame, "Shoulder", (5, sh_y - 5),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 200, 0), 1)
            cv2.putText(frame, "Hip", (5, hp_y - 5),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 200, 255), 1)

            status, color, pct, fallen = detector.update(lm)

        # TCP 서버가 활성화된 경우 프레임 전송
        if _tcp_server.active:
            _tcp_server.send_frame(frame)

        # 쓰러짐 확정 시 빨간 화면 토글
        if fallen:
            now = time.time()
            if now - last_flash_t >= 0.5:
                flash_state  = not flash_state
                last_flash_t = now
            if flash_state:
                red_overlay = frame.copy()
                red_overlay[:] = (0, 0, 200)
                cv2.addWeighted(red_overlay, 0.5, frame, 0.5, 0, frame)
        else:
            flash_state  = False
            last_flash_t = time.time()

        # 상태 배경
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (w, 45), (20, 20, 20), -1)
        cv2.addWeighted(overlay, 0.6, frame, 0.4, 0, frame)

        cv2.putText(frame, status, (12, 30),
            cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)

        if pct > 0:
            bar_w = int(w * pct)
            cv2.rectangle(frame, (0, 44), (bar_w, 50), color, -1)

        if fallen:
            cv2.rectangle(frame, (0, 0), (w-1, h-1), (0, 0, 220), 6)

        cv2.putText(frame, "- Shoulder (yellow)   - Hip (cyan)",
            (12, h - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (180, 180, 180), 1)

        cv2.imshow("SterileBot - Fall Detection", frame)

        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
        elif key == ord('r'):
            detector.fall_start = None
            detector.is_fallen  = False
            detector.alerted    = False
            flash_state         = False
            _tcp_server.stop()
            print("\n[RESET] Fall detection reset")

    _tcp_server.stop()
    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--camera", default=CAMERA_INDEX,
                        help="카메라 인덱스 또는 스트리밍 URL")
    args = parser.parse_args()

    try:
        src = int(args.camera)
    except ValueError:
        src = args.camera

    main(src)