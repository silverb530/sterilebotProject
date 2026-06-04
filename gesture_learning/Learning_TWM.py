#!/usr/bin/env python3
# =============================================================
#  SterileBot - 얼굴 방향 마우스 커서 (트래킹 전용)
#  파일명: head_mouse.py
#
#  ▶ 실행 (캘리브레이션 먼저 해야 함)
#    python head_mouse.py                  (default 사용)
#    python head_mouse.py --name minju     (사용자 지정)
#
#  ▶ 캘리브레이션
#    python calib.py --name minju
#
#  ▶ 동작
#    얼굴 방향 → 커서 이동
#    3초 응시  → 왼쪽 클릭 (Dwell)
#
#  ▶ 종료
#    터미널에서 Ctrl+C
# =============================================================

import cv2
import numpy as np
import mediapipe as mp
import sys
import os
import argparse
import time
import threading
import ctypes
import keyboard
from collections import deque
from Utils import (get_head_pose, apply_transform, get_screen_size,
                   mouse_move, mouse_click,
                   create_and_set_cursor, restore_cursor)

# ────────────────────────────────────────────────
#  설정값
# ────────────────────────────────────────────────
CAMERA_INDEX  = 1
SMOOTHING     = 0.4
BUFFER_SIZE   = 8
DEAD_ZONE     = 14
PROCESS_EVERY = 2
SAVE_DIR      = "calib_data"

# Dwell 클릭
DWELL_TIME     = 1.2
DWELL_ZONE     = 40
DWELL_COOLDOWN = 2.0

# 포그라운드 유지 (커서 멈춤 방지)
FOREGROUND_INTERVAL = 1.0  # 1초마다 터미널 창을 포그라운드로

# zone_tracker 소켓 송신
import socket
import json
ZONE_TRACKER_PORT = 9002
zone_sock = None
_last_connect_try = 0.0
_RECONNECT_INTERVAL = 2.0  # 연결 실패 시 2초마다 재시도

def connect_zone_tracker(verbose=True):
    global zone_sock
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.5)
        s.connect(("127.0.0.1", ZONE_TRACKER_PORT))
        s.settimeout(None)
        zone_sock = s
        if verbose:
            print(f"[INFO] zone_tracker 연결됨")
    except:
        zone_sock = None
        if verbose:
            print(f"[WARN] zone_tracker 연결 실패")

def send_cursor(x, y):
    global zone_sock, _last_connect_try
    # 연결 안 돼있으면 주기적으로 재연결 시도
    if zone_sock is None:
        now = time.time()
        if now - _last_connect_try > _RECONNECT_INTERVAL:
            _last_connect_try = now
            connect_zone_tracker(verbose=True)
        if zone_sock is None:
            return
    try:
        msg = json.dumps({"type": "CURSOR", "x": int(x), "y": int(y)}) + "\n"
        zone_sock.sendall(msg.encode())
    except:
        zone_sock = None

# ────────────────────────────────────────────────
#  카메라 캡처 스레드
#  별도 스레드에서 계속 캡처 → 메인 루프 블로킹 방지
# ────────────────────────────────────────────────
class CameraThread:
    def __init__(self, index, width, height):
        self.cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH,  width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        self.frame  = None
        self.lock   = threading.Lock()
        self.running = True
        self.thread  = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _run(self):
        while self.running:
            ret, frame = self.cap.read()
            if ret:
                with self.lock:
                    self.frame = frame

    def read(self):
        with self.lock:
            return self.frame is not None, \
                   self.frame.copy() if self.frame is not None else None

    def get_size(self):
        return (int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
                int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)))

    def stop(self):
        self.running = False
        self.cap.release()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", type=str, default="default",
                        help="사용자 이름 (캘리브레이션 파일명)")
    args = parser.parse_args()

    save_path = os.path.join(SAVE_DIR, f"{args.name}.npy")

    # 캘리브레이션 파일 확인
    if not os.path.exists(save_path):
        print(f"[ERROR] 캘리브레이션 파일 없음: {save_path}")
        print(f"[ERROR] 먼저 실행: python calib.py --name {args.name}")
        sys.exit(1)

    # 캘리브레이션 파일 로드
    data        = np.load(save_path, allow_pickle=True).item()
    transform_M = data["transform_M"]
    saved_sw    = data.get("screen_w", 0)
    saved_sh    = data.get("screen_h", 0)

    print("=" * 55)
    print("  Head Mouse Tracking")
    print("=" * 55)
    print(f"사용자: {args.name}")
    print(f"캘리브레이션 파일: {save_path}")
    print(f"캘리브레이션 해상도: {saved_sw}x{saved_sh}")
    print(f"Dwell {DWELL_TIME}s → Left Click")
    print("종료: Ctrl+C")
    print("=" * 55)

    screen_w, screen_h = get_screen_size()

    # 해상도가 다르면 경고
    if saved_sw != screen_w or saved_sh != screen_h:
        print(f"[WARN] 현재 해상도({screen_w}x{screen_h})와 "
              f"캘리브레이션 해상도({saved_sw}x{saved_sh})가 달라요!")
        print(f"[WARN] 정확도가 낮을 수 있어요. 재캘리브레이션 권장.")

    # 커서 적용
    create_and_set_cursor()
    connect_zone_tracker()

    # 카메라 스레드 시작
    cam = CameraThread(CAMERA_INDEX, 640, 480)
    frame_w, frame_h = cam.get_size()
    print(f"[INFO] 웹캠: {frame_w}x{frame_h}")
    print("[INFO] 트래킹 시작! (종료: Ctrl+C 또는 q키)")

    # 상태 변수
    cur_x     = screen_w / 2
    cur_y     = screen_h / 2
    yaw_buf   = deque(maxlen=BUFFER_SIZE)
    pitch_buf = deque(maxlen=BUFFER_SIZE)

    dwell_start_x = None
    dwell_start_y = None
    dwell_start_t = None
    dwell_last_t  = 0.0

    frame_count  = 0
    yaw, pitch   = None, None
    last_fg_time = 0.0  # 포그라운드 유지용

    # 터미널 창 핸들 미리 가져오기
    console_hwnd = ctypes.windll.kernel32.GetConsoleWindow()

    # Zone Tracker 창 핸들 찾기
    zone_tracker_hwnd = None
    def find_zone_tracker():
        nonlocal zone_tracker_hwnd
        import ctypes
        EnumWindows = ctypes.windll.user32.EnumWindows
        EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int))
        GetWindowText = ctypes.windll.user32.GetWindowTextW
        GetWindowTextLength = ctypes.windll.user32.GetWindowTextLengthW
        IsWindowVisible = ctypes.windll.user32.IsWindowVisible
        found = []
        def callback(hwnd, lparam):
            length = GetWindowTextLength(hwnd)
            if length > 0:
                buf = ctypes.create_unicode_buffer(length + 1)
                GetWindowText(hwnd, buf, length + 1)
                if "Zone Tracker" in buf.value:
                    found.append(hwnd)
            return True
        EnumWindows(EnumWindowsProc(callback), 0)
        if found:
            zone_tracker_hwnd = found[0]

    mp_face_mesh = mp.solutions.face_mesh

    try:
        with mp_face_mesh.FaceMesh(
            max_num_faces=1,
            refine_landmarks=False,
            min_detection_confidence=0.7,
            min_tracking_confidence=0.7
        ) as face_mesh:

            while True:
                ret, frame = cam.read()
                if not ret:
                    time.sleep(0.01)
                    continue

                frame_count += 1
                frame = cv2.flip(frame, 1)
                now   = time.time()

                # 주기적으로 포그라운드 유지
                # Zone Tracker 살아있으면 그 창, 없으면 WPF 창으로 포그라운드 유지
                if now - last_fg_time > FOREGROUND_INTERVAL:
                    if zone_tracker_hwnd is None:
                        find_zone_tracker()
                    if zone_tracker_hwnd:
                        # Zone Tracker 창 포그라운드 시도
                        ret = ctypes.windll.user32.SetForegroundWindow(zone_tracker_hwnd)
                        if not ret:
                            # 핸들 무효 → 초기화 후 다음 루프에서 WPF로
                            zone_tracker_hwnd = None
                    else:
                        # Zone Tracker 없음 (실험 종료 후) → WPF 창 포그라운드
                        wpf_hwnd = ctypes.windll.user32.FindWindowW(None, "SterileBot Monitor")
                        if wpf_hwnd:
                            ctypes.windll.user32.SetForegroundWindow(wpf_hwnd)
                    last_fg_time = now

                # N프레임마다 MediaPipe 처리
                if frame_count % PROCESS_EVERY == 0:
                    rgb    = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    result = face_mesh.process(rgb)
                    yaw, pitch = None, None

                    if result.multi_face_landmarks:
                        lm = result.multi_face_landmarks[0].landmark
                        yaw, pitch = get_head_pose(lm, frame_w, frame_h)

                if yaw is not None:
                    # 이동 평균 필터
                    yaw_buf.append(yaw)
                    pitch_buf.append(pitch)
                    avg_yaw   = np.mean(yaw_buf)
                    avg_pitch = np.mean(pitch_buf)

                    # 변환 행렬 적용
                    tx, ty = apply_transform(transform_M, avg_yaw, avg_pitch)
                    tx = max(0, min(screen_w-1, tx))
                    ty = max(0, min(screen_h-1, ty))

                    # 스무딩 + 데드존
                    new_x = cur_x + (tx - cur_x) * SMOOTHING
                    new_y = cur_y + (ty - cur_y) * SMOOTHING
                    if abs(new_x - cur_x) > DEAD_ZONE:
                        cur_x = new_x
                    if abs(new_y - cur_y) > DEAD_ZONE:
                        cur_y = new_y

                    mouse_move(cur_x, cur_y)
                    send_cursor(cur_x, cur_y)

                    # Dwell 클릭
                    if dwell_start_x is None:
                        dwell_start_x = cur_x
                        dwell_start_y = cur_y
                        dwell_start_t = now
                    else:
                        dist = np.sqrt((cur_x-dwell_start_x)**2 +
                                       (cur_y-dwell_start_y)**2)
                        if dist > DWELL_ZONE:
                            dwell_start_x = cur_x
                            dwell_start_y = cur_y
                            dwell_start_t = now
                        else:
                            dwell_elapsed = now - dwell_start_t
                            if dwell_elapsed >= DWELL_TIME and \
                               now - dwell_last_t > DWELL_COOLDOWN:
                                # 화면 상단 50px는 제목표시줄/작업표시줄 — 클릭 차단
                                if cur_y < 50:
                                    dwell_start_x = None
                                else:
                                    mouse_click()
                                    dwell_last_t  = now
                                    dwell_start_x = None
                                    print(f"[DWELL] Click ({int(cur_x)},{int(cur_y)})")
                else:
                    dwell_start_x = None

                # 창 포커스 없이도 동작 (keyboard 라이브러리)
                if keyboard.is_pressed("q"):
                    break
                time.sleep(0.01)

    except KeyboardInterrupt:
        print("\n[INFO] Ctrl+C 종료")
    finally:
        cam.stop()
        cv2.destroyAllWindows()
        restore_cursor()
        print("[INFO] 종료")


if __name__ == "__main__":
    main()