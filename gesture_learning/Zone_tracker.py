#!/usr/bin/env python3
# =============================================================
#  SterileBot - 2단계 구역 매칭 트래커
#  파일명: zone_tracker.py
#
#  ▶ 동작
#    1단계: 트래킹 커서로 큰 구역 선택 (Dwell)
#    2단계: 세부 박스 표시 → 제스처 1~4로 선택
#           선택된 박스 노란색 → 로봇 이동
#    3단계: 제스처로 집기/놓기/붓기 등 개별 제어
#
#  ▶ 포트
#    9002: 커서 좌표 수신 (Learning_TWM)
#    9003: 제스처 수신 (gesture_control_v6)
# =============================================================

import argparse
import cv2
import json
import os
import sys
import time
import socket
import threading
import ctypes
from mjpeg_streamer import MjpegStreamer

# ────────────────────────────────────────────────
#  설정값
# ────────────────────────────────────────────────
CAMERA_INDEX    = 0
MJPEG_PORT      = 8090
ZONE_FILE       = "zone_data.json"
CURSOR_PORT     = 9002
GESTURE_PORT    = 9003
DWELL_TIME      = 0.8
DWELL_COOLDOWN  = 1.5

# ────────────────────────────────────────────────
#  구역 파일 로드
# ────────────────────────────────────────────────
def can_drop_at(slot, tube_slots):
    """인접 슬롯에 시험관이 있으면 False (옆으로 집을 공간 없음)"""
    prefix = slot.rstrip("0123456789")   # "A" or "B"
    num_str = slot[len(prefix):]
    if not num_str.isdigit():
        return True
    num = int(num_str)
    for adj in [num - 1, num + 1]:
        adj_slot = f"{prefix}{adj}"
        if adj_slot in tube_slots:
            return False
    return True
def load_zones():
    if not os.path.exists(ZONE_FILE):
        print(f"[ERROR] 구역 파일 없음: {ZONE_FILE}")
        sys.exit(1)
    with open(ZONE_FILE, "r") as f:
        zones = json.load(f)
    print(f"[INFO] 구역 로드: {len(zones)}개")
    for z in zones:
        nch = len(z.get("children", []))
        print(f"  {z['name']}: 세부 {nch}개")
    return zones

# ────────────────────────────────────────────────
#  소켓 수신 (커서 좌표)
# ────────────────────────────────────────────────
cursor_x    = 0
cursor_y    = 0
cursor_lock = threading.Lock()
cursor_connected = False

def cursor_receiver():
    global cursor_x, cursor_y, cursor_connected
    while True:
        try:
            server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.bind(("0.0.0.0", CURSOR_PORT))
            server.listen(1)
            print(f"[INFO] 커서 수신 대기 (포트 {CURSOR_PORT})")
            conn, addr = server.accept()
            cursor_connected = True
            print(f"[INFO] Learning_TWM 연결됨: {addr}")
            buf = ""
            while True:
                data = conn.recv(1024).decode("utf-8")
                if not data:
                    break
                buf += data
                while "\n" in buf:
                    line, buf = buf.split("\n", 1)
                    try:
                        msg = json.loads(line.strip())
                        if msg.get("type") == "CURSOR":
                            with cursor_lock:
                                cursor_x = msg["x"]
                                cursor_y = msg["y"]
                    except:
                        pass
        except Exception as e:
            cursor_connected = False
            time.sleep(1.0)

# ────────────────────────────────────────────────
#  소켓 수신 (제스처)
# ────────────────────────────────────────────────
latest_gesture = None
gesture_lock   = threading.Lock()
gesture_connected = False

def gesture_receiver():
    global latest_gesture, gesture_connected
    while True:
        try:
            server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.bind(("0.0.0.0", GESTURE_PORT))
            server.listen(1)
            print(f"[INFO] 제스처 수신 대기 (포트 {GESTURE_PORT})")
            conn, addr = server.accept()
            gesture_connected = True
            print(f"[INFO] gesture_control 연결됨: {addr}")
            buf = ""
            while True:
                data = conn.recv(1024).decode("utf-8")
                if not data:
                    break
                buf += data
                while "\n" in buf:
                    line, buf = buf.split("\n", 1)
                    try:
                        msg = json.loads(line.strip())
                        print(f"[GESTURE RCV] {msg}")
                        with gesture_lock:
                            latest_gesture = msg
                    except:
                        pass
        except Exception as e:
            gesture_connected = False
            time.sleep(1.0)

# ────────────────────────────────────────────────
#  main
# ────────────────────────────────────────────────
def main():
    print("=" * 55)
    print("  SterileBot - 2단계 구역 트래커")
    print("=" * 55)

    zones = load_zones()

    # 명령행 인자 (WPF 자동 실행용). 인자 없으면 기존 콘솔 input 방식.
    parser = argparse.ArgumentParser()
    parser.add_argument("--robot", choices=["yes", "no"], default=None,
                        help="로봇 연결 여부 (WPF가 전달)")
    parser.add_argument("--ip",   type=str, default="192.168.0.32")
    parser.add_argument("--port", type=int, default=5001)
    args, _ = parser.parse_known_args()

    robot = None
    if args.robot is None:
        # 인자 없음 → 기존 콘솔 input 방식 (수동 실행 호환)
        use_robot = input("\n로봇 연결? (y/n, 기본 n): ").strip().lower()
        if use_robot == 'y':
            from robot_controller import RobotController
            ip   = input("로봇 IP (기본 192.168.0.27): ").strip() or "192.168.0.27"
            port = input("포트 (기본 5001): ").strip() or "5001"
            robot = RobotController(ip=ip, port=int(port))
            if not robot.connected:
                print("[WARN] 로봇 연결 실패 → 시뮬레이션 모드")
                robot = None
            else:
                print("[ROBOT] 홈 위치로 이동 중...")
                robot.go_home()
        else:
            print("[INFO] 시뮬레이션 모드")
    elif args.robot == "yes":
        from robot_controller import RobotController
        robot = RobotController(ip=args.ip, port=args.port)
        if not robot.connected:
            print("[WARN] 로봇 연결 실패 → 시뮬레이션 모드")
            robot = None
        else:
            print("[ROBOT] 홈 위치로 이동 중...")
            robot.go_home()
    else:
        print("[INFO] 시뮬레이션 모드 (--robot no)")

    # 소켓 스레드 시작
    threading.Thread(target=cursor_receiver,  daemon=True).start()
    threading.Thread(target=gesture_receiver, daemon=True).start()

    # 웹캠
    streamer = MjpegStreamer(port=MJPEG_PORT)
    streamer.start()
    cap = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_DSHOW)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    cap.set(cv2.CAP_PROP_AUTOFOCUS, 0)  # 자동초점 비활성화
    cap.set(cv2.CAP_PROP_FOCUS, 0)      # 초점 고정 (0 = 무한대)
    fw = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    fh = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print(f"[INFO] 웹캠: {fw}x{fh}")

    cv2.namedWindow("Zone Tracker", cv2.WINDOW_NORMAL)
    # WPF 자동 실행 시 cv2 창을 화면 밖으로 숨김 (MJPEG로 WPF에 송출하므로 불필요)
    if args.robot is not None:
        cv2.moveWindow("Zone Tracker", -10000, -10000)
        cv2.resizeWindow("Zone Tracker", 1, 1)
    else:
        cv2.resizeWindow("Zone Tracker", fw, fh)

    screen_w = ctypes.windll.user32.GetSystemMetrics(0)
    screen_h = ctypes.windll.user32.GetSystemMetrics(1)

    # 상태
    # ── 상태 변수 ──
    state              = "STAGE1"
    selected_zone      = None
    selected_child     = None
    tube_slots         = set()
    pickup_pending     = False
    drop_pending       = False
    holding_tube       = False
    pickup_mode        = None
    beaker_ready       = False
    stir_pending       = False
    stir_drop_pending  = False
    holding_stir       = False
    stir_step          = None
    dwell_zone         = None
    dwell_start_t      = None
    dwell_last_t       = 0.0
    last_gesture       = None
    last_robot_action  = None
    last_robot_param   = None
    stop_time          = 0.0   # STOP 발생 시각 (플리커 방지용)

    print("\n[INFO] 트래킹 시작! (q: 종료)")

    prev_playing = False  # robot.playing 이전 상태 추적

    while True:
        ret, frame = cap.read()
        if not ret:
            continue

        display = frame.copy()
        now     = time.time()

        # robot.playing 변화 감지 — 홈 복귀 완료 시 구역 표시
        cur_playing = robot.playing if robot else False
        if prev_playing and not cur_playing:
            # 동작 완료 → STIRRING 상태면 전체 구역 표시로 전환
            if stir_step == "STIRRING":
                stir_step = None
                print("[INFO] 섞기 홈 복귀 완료 → 전체 구역 표시")
        prev_playing = cur_playing

        # 커서 좌표 → 웹캠 좌표 변환
        with cursor_lock:
            cx = cursor_x
            cy = cursor_y
        cam_cx = int(cx / screen_w * fw)
        cam_cy = int(cy / screen_h * fh)

        # 제스처 읽기
        with gesture_lock:
            global latest_gesture
            gesture = latest_gesture
            latest_gesture = None  # 소비

        # ── STAGE 1: 큰 구역 선택 ──
        if state == "STAGE1":
            # 커서가 어느 구역 안에 있는지
            hover_zone = None
            for z in zones:
                if z["x1"] <= cam_cx <= z["x2"] and z["y1"] <= cam_cy <= z["y2"]:
                    hover_zone = z
                    break

            # Dwell 처리
            if hover_zone:
                hz_name = hover_zone["name"].upper()

                # stir_step MOVE 상태 → Stir_area/CANCEL만 Dwell 허용
                if stir_step == "MOVE" and hz_name not in ("STIR_AREA", "HOME"):
                    dwell_zone    = None
                    dwell_start_t = None
                # BEAKER_MOVING / STIRRING → Dwell 전체 차단 (CANCEL 제외)
                elif stir_step in ("BEAKER_MOVING", "STIRRING") and hz_name != "HOME":
                    dwell_zone    = None
                    dwell_start_t = None
                # DROP_MOVE 상태 → Stir_area/CANCEL만 Dwell 허용
                elif stir_step == "DROP_MOVE" and hz_name not in ("STIR_AREA", "HOME"):
                    dwell_zone    = None
                    dwell_start_t = None
                elif dwell_zone != hover_zone["name"]:
                    dwell_zone    = hover_zone["name"]
                    dwell_start_t = now
                else:
                    elapsed = now - dwell_start_t
                    pct     = min(elapsed / DWELL_TIME, 1.0)

                    if pct >= 1.0 and now - dwell_last_t > DWELL_COOLDOWN:
                        dwell_last_t  = now
                        dwell_zone    = None

                        # CANCEL 구역 선택 시
                        if hover_zone["name"].upper() == "HOME":
                            beaker_ready = False
                            if robot and robot.playing:
                                print("[HOME] 무시 — 이동 중")
                            elif state == "STAGE2" and selected_child:
                                # STAGE2 세부 선택 중 → 세부 선택만 취소
                                selected_child = None
                                print("[HOME] 세부 선택 취소")
                            else:
                                # 그 외 모든 경우 → 홈 복귀 + 전체 초기화
                                if robot:
                                    if holding_tube and pickup_mode == "horizontal":
                                        robot.go_home_lift()
                                    else:
                                        robot.go_home()
                                stir_step         = None
                                stir_pending      = False
                                stir_drop_pending = False
                                pickup_pending    = False
                                drop_pending      = False
                                holding_stir      = False
                                holding_tube      = False
                                selected_zone     = None
                                selected_child    = None
                                state             = "STAGE1"
                                last_gesture      = None
                                print("[HOME] 홈 복귀 + 전체 초기화")
                        elif hover_zone["name"].upper() == "BEAKER" and (holding_tube or holding_stir):
                            if robot and robot.playing:
                                print("[BEAKER] 무시 — 이동 중")
                            elif holding_stir and not stir_drop_pending and stir_step != "DROP_MOVE":
                                # 막대 잡은 상태 → 비커 위치로 이동 후 SHAKE 대기 (중복 방지)
                                print("[BEAKER] 비커 위치로 이동 → SHAKE 제스처로 섞기")
                                stir_step = "BEAKER_MOVING"  # 이동 중 플래그 → 재트리거 방지
                                dwell_last_t = now  # cooldown 강제 리셋
                                if robot:
                                    robot.stir_beaker_move()
                            elif not holding_stir:
                                # 시험관 잡은 상태 → 비커 위치로 이동 후 POUR 대기
                                print("[BEAKER] 비커 위치로 이동 → POUR 제스처로 붓기")
                                beaker_ready = True
                                dwell_last_t = now  # cooldown 강제 리셋
                                if robot:
                                    robot.beaker_move()
                        elif hover_zone["name"].upper() == "STIR_AREA":
                            if holding_stir and not stir_drop_pending:
                                # 막대 들고 있으면 → 원위치로 이동 후 RELEASE 대기
                                print("[STIR] 막대 원위치로 이동 → RELEASE 제스처로 놓기")
                                stir_step = "DROP_MOVE"
                                dwell_last_t = now  # cooldown 강제 리셋
                                if robot:
                                    ok = robot.stir_drop_move()
                                    print(f"  [ROBOT] stir_drop_move → {ok}")
                                    if ok:
                                        stir_drop_pending = True
                                else:
                                    stir_drop_pending = True
                                    print("[SIM] stir_drop_move")
                            elif stir_step is None and not holding_tube and not holding_stir:
                                print("[STIR] 막대 위치로 이동 → GRAB 제스처로 잡기")
                                stir_step = "MOVE"
                                if robot:
                                    ok = robot.stir_move()
                                    print(f"  [ROBOT] stir_move → {ok}")
                                    if ok:
                                        stir_pending = True
                                        last_robot_action = "stir_move"
                                        last_robot_param  = None
                                    else:
                                        stir_step = None
                                        print("  [ERROR] stir_move 실패")
                                else:
                                    stir_pending = True
                                    print("[SIM] stir_move")
                        else:
                            # 일반 구역 (A_tubes, B_tubes, Reagent_bottles 등) → STAGE2
                            beaker_ready  = False
                            selected_zone = hover_zone
                            state         = "STAGE2"
                            print(f"\n[SELECT1] {selected_zone['name']} 선택됨")
                            print(f"  제스처 1~{len(selected_zone.get('children',[]))}로 세부 선택")
            else:
                dwell_zone    = None
                dwell_start_t = None

            # 구역 표시
            for z in zones:
                x1, y1, x2, y2 = z["x1"], z["y1"], z["x2"], z["y2"]
                is_home  = z["name"].upper() == "HOME"
                is_beaker  = z["name"].upper() == "BEAKER"
                is_stir    = z["name"].upper() == "STIR_AREA"
                is_hover   = hover_zone and hover_zone["name"] == z["name"]

                # stir_step MOVE 상태면 Stir_area + CANCEL만 표시
                if stir_step == "MOVE" and not is_stir and not is_home:
                    continue

                # BEAKER_MOVING / STIRRING 상태 → 비커+CANCEL만
                if stir_step in ("BEAKER_MOVING", "STIRRING") and not is_beaker and not is_home:
                    continue

                # DROP_MOVE 상태 → Stir_area + CANCEL만 표시
                if stir_step == "DROP_MOVE" and not is_stir and not is_home:
                    continue

                # beaker_ready 상태 → 비커 + HOME만 표시
                if beaker_ready and not is_beaker and not is_home:
                    continue

                if is_home:
                    color = (0, 0, 255) if is_hover else (0, 0, 180)
                else:
                    color = (0, 220, 255) if is_hover else (0, 255, 157)
                thick = 3 if is_hover else 2
                cv2.rectangle(display, (x1,y1), (x2,y2), color, thick)
                if not is_home:  # HOME은 별도 루프에서 텍스트 표시
                    cv2.putText(display, z["name"],
                                (x1+5, y1+30),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.9, color, 2)

                # Dwell 진행 바
                if is_hover and dwell_start_t:
                    elapsed = now - dwell_start_t
                    pct     = min(elapsed / DWELL_TIME, 1.0)
                    bw      = int((x2-x1) * pct)
                    cv2.rectangle(display, (x1,y2+4), (x1+bw,y2+12),
                                  (0,255,157), -1)

            # 상태 표시
            if stir_step == "MOVE":
                label = "Stir: Moving" if (robot and robot.playing) else "Stir: GRAB"
                cv2.putText(display, label,
                            (10, 30), cv2.FONT_HERSHEY_SIMPLEX,
                            0.8, (0,255,255), 2)
            elif stir_step == "BEAKER_MOVING":
                cv2.putText(display, "Stir: Moving",
                            (10, 30), cv2.FONT_HERSHEY_SIMPLEX,
                            0.8, (0,255,255), 2)
            elif stir_step == "STIRRING":
                cv2.putText(display, "Stir: Stirring",
                            (10, 30), cv2.FONT_HERSHEY_SIMPLEX,
                            0.8, (0,255,255), 2)
            elif stir_step == "DROP_MOVE":
                label = "Stir: Moving" if (robot and robot.playing) else "Stir: RELEASE"
                cv2.putText(display, label,
                            (10, 30), cv2.FONT_HERSHEY_SIMPLEX,
                            0.8, (0,255,255), 2)
            elif holding_stir:
                cv2.putText(display, "Stir: Holding",
                            (10, 30), cv2.FONT_HERSHEY_SIMPLEX,
                            0.8, (0,255,255), 2)
            elif pickup_pending:
                label = "Moving" if (robot and robot.playing) else "GRAB"
                cv2.putText(display, label,
                            (10, 30), cv2.FONT_HERSHEY_SIMPLEX,
                            0.8, (0,255,255), 2)
            elif drop_pending:
                label = "Moving" if (robot and robot.playing) else "RELEASE"
                cv2.putText(display, label,
                            (10, 30), cv2.FONT_HERSHEY_SIMPLEX,
                            0.8, (0,255,255), 2)
            elif beaker_ready:
                if robot and robot.playing:
                    cv2.putText(display, "Moving to Beaker",
                                (10, 30), cv2.FONT_HERSHEY_SIMPLEX,
                                0.8, (0,255,255), 2)
                else:
                    cv2.putText(display, "POUR",
                                (10, 30), cv2.FONT_HERSHEY_SIMPLEX,
                                0.8, (0,140,255), 2)
            elif robot and robot.playing:
                cv2.putText(display, "Moving",
                            (10, 30), cv2.FONT_HERSHEY_SIMPLEX,
                            0.8, (0,255,255), 2)

        # ── STAGE1에서 POUR 처리 (비커 이동 후) ──
        if state == "STAGE1" and holding_tube and beaker_ready:
            if gesture and gesture.get("action") == "POUR":
                if robot and robot.playing:
                    pass  # 아직 비커 이동 중 — 대기
                else:
                    print("[ROBOT] 붓기 동작 실행")
                    robot.beaker_pour()
                    beaker_ready   = False
                    holding_tube   = False  # 붓고나면 시험관 없음
                    print("[INFO] 붓기 완료 → 시험관 꽂기 선택 가능")

        # ── STAGE 2: 세부 선택 ──
        elif state == "STAGE2" and selected_zone:
            children = selected_zone.get("children", [])

            # 제스처로 1~4 선택
            if gesture and gesture.get("finger") is not None:
                if robot and robot.playing:
                    pass  # 로봇 동작 중 — 대기
                else:
                    finger = gesture["finger"]
                    if 1 <= finger <= len(children):
                        selected_child = children[finger - 1]
                        slot = selected_child["slot"]
                        print(f"[SELECT2] {selected_child['name']} (slot={slot})")

                        zone_name = selected_zone["name"].upper()
                        if "REAGENT" in zone_name:
                            if stir_step == "DROP_MOVE":
                                # 섞기 후 막대 원위치로 이동 단계
                                print(f"  [ROBOT] stir_drop_move → 막대 원위치 이동")
                                if robot:
                                    ok = robot.stir_drop_move()
                                    print(f"  [ROBOT] stir_drop_move → {ok}")
                                    if ok:
                                        drop_pending = True
                                else:
                                    print(f"  [SIM] stir_drop_move")
                                    drop_pending = True
                                selected_zone  = None
                                selected_child = None
                                state = "STAGE1"
                                if drop_pending:
                                    print("  → 막대 원위치 도달 후 RELEASE 제스처로 놓기")
                            else:
                                # 시약통 → pickup_move(tube_num) [수직]
                                tube_num = finger
                                if robot:
                                    ok = robot.pickup_move(tube_num)
                                    print(f"  [ROBOT] pickup_move({tube_num}) → {ok}")
                                    if ok:
                                        pickup_pending    = True
                                        pickup_mode       = "vertical"
                                        last_robot_action = "pickup_move"
                                        last_robot_param  = tube_num
                                else:
                                    print(f"  [SIM] pickup_move({tube_num})")
                                    pickup_pending = True
                                    pickup_mode    = "vertical"
                        else:
                            # A_tubes, B_tubes
                            if not holding_tube:
                                # 시험관 안 들고 있으면 → 무조건 수평 집기
                                print(f"  → {slot} 수평 집기 이동")
                                ok = False
                                if robot:
                                    for _ in range(5):
                                        if not robot.playing:
                                            ok = robot.pickup_lift_move(slot)
                                            if ok: break
                                        time.sleep(0.5)
                                    print(f"  [ROBOT] pickup_lift_move({slot}) → {ok}")
                                    if ok:
                                        tube_slots.discard(slot)
                                        pickup_pending = True
                                        pickup_mode    = "horizontal"
                                else:
                                    tube_slots.discard(slot)
                                    pickup_pending = True
                                    pickup_mode    = "horizontal"
                            else:
                                # 시험관 들고 있으면 → 놓기
                                if not can_drop_at(slot, tube_slots):
                                    print(f"  [WARN] {slot} 인접 슬롯에 시험관 있음 → 꽂기 불가 (옆으로 집을 공간 없음)")
                                elif pickup_mode == "horizontal":
                                    # 수평으로 잡았으면 수평으로 이동 후 RELEASE 대기
                                    ok = False
                                    if robot:
                                        for _ in range(5):
                                            if not robot.playing:
                                                ok = robot.side_drop_move(slot)
                                                if ok: break
                                            time.sleep(0.5)
                                        print(f"  [ROBOT] side_drop_move({slot}) → {ok}")
                                        if ok:
                                            drop_pending = True
                                    else:
                                        drop_pending = True
                                else:
                                    # 수직으로 잡았으면 수직으로 꽂기 (drop_move + RELEASE)
                                    ok = False
                                    if robot:
                                        for retry in range(5):
                                            if not robot.playing:
                                                ok = robot.drop_move(slot)
                                                if ok: break
                                            time.sleep(0.5)
                                        print(f"  [ROBOT] drop_move({slot}) → {ok}")
                                        if ok:
                                            drop_pending = True
                                    else:
                                        print(f"  [SIM] drop_move({slot})")
                                        drop_pending = True
                            if drop_pending:
                                print(f"  → {slot} 위치 도달. RELEASE 제스처로 놓기")
                            elif not pickup_pending:
                                print(f"  → {slot} 완료")

        # 제스처로 동작 제어
        if gesture and "action" in gesture:
            print(f"[DEBUG] action={gesture.get('action')} stir_step={stir_step} stir_pending={stir_pending} pickup_pending={pickup_pending} robot.playing={robot.playing if robot else 'N/A'}")
        # STOP은 항상 최우선 처리 — 로봇만 정지, 상태 유지
        if gesture and gesture.get("action") == "STOP" and robot:
            robot.stop()
            if last_gesture != "STOP":
                stop_time = now
                print("[ROBOT] 긴급 정지 — CANCEL로 취소, 손 내리면 재개")
            last_gesture = "STOP"

        # STOP_RELEASE — 1.5초 이상 지난 STOP이어야 재개 (플리커 방지)
        elif gesture and gesture.get("action") == "STOP_RELEASE":
            if now - stop_time >= 1.5:
                last_gesture = None
                print("[INFO] 정지 해제 → 동작 재개")
                if robot and last_robot_action:
                    if last_robot_action == "stir_move" and stir_pending:
                        ok = robot.stir_move()
                        print(f"  [ROBOT] stir_move 재개 → {ok}")
                        if not ok:
                            stir_step    = None
                            stir_pending = False
                    elif last_robot_action == "pickup_move" and pickup_pending:
                        ok = robot.pickup_move(last_robot_param)
                        print(f"  [ROBOT] pickup_move({last_robot_param}) 재개 → {ok}")
                        if not ok:
                            pickup_pending = False
            else:
                # 너무 빨리 온 STOP_RELEASE → 플리커, 무시
                last_gesture = "STOP"

        elif gesture and gesture.get("action") not in ("STOP", "STOP_RELEASE"):
            last_gesture = gesture.get("action")

        if gesture and "action" in gesture and (selected_child or holding_tube or pickup_pending or drop_pending or stir_step or holding_stir or stir_pending or stir_drop_pending):
            action = gesture["action"]

            # STOP은 위에서 이미 처리
            if action == "STOP":
                pass

            # robot.playing 체크 (stir/pickup 대기 제스처는 예외)
            elif robot and robot.playing:
                stir_waiting = (stir_pending and action == "GRAB") or \
                               (stir_drop_pending and action == "RELEASE")
                # SHAKE는 반드시 이동 완료(robot.playing=False) 후에만 처리
                if stir_waiting:
                    pass
                else:
                    pass
                    action = None

            # ── GRAB ──
            if action == "GRAB" and robot:
                if stir_pending:
                    ok = robot.stir_grip()
                    print(f"  [ROBOT] stir_grip → {ok}")
                    if ok:
                        stir_pending      = False
                        holding_stir      = True
                        stir_step         = None
                        last_robot_action = None  # 완료
                        state             = "STAGE1"
                        print("[ROBOT] 막대 잡기 완료 → Beaker 구역 선택하세요")
                elif pickup_pending:
                    if pickup_mode == "horizontal":
                        ok = robot.pickup_grip_lift()
                        print(f"  [ROBOT] pickup_grip_lift → {ok}")
                    else:
                        ok = robot.pickup_grip()
                        print(f"  [ROBOT] pickup_grip → {ok}")
                    if ok:
                        pickup_pending    = False
                        holding_tube      = True
                        last_robot_action = None  # 완료
                        selected_zone     = None
                        selected_child    = None
                        state = "STAGE1"
                        print(f"[ROBOT] 잡기 완료 ({pickup_mode}) → 1단계로 복귀")
                elif not holding_stir and not holding_tube:
                    robot.grip_close()
                    print("[ROBOT] 집기")

            elif action == "RELEASE" and robot:
                if stir_drop_pending:
                    ok = robot.stir_drop_release()
                    print(f"  [ROBOT] stir_drop_release → {ok}")
                    if ok:
                        stir_drop_pending = False
                        holding_stir      = False
                        stir_step         = None
                        state             = "STAGE1"
                        print("[ROBOT] 막대 반납 완료 → 섞기 끝")
                elif drop_pending:
                    if pickup_mode == "horizontal":
                        robot.side_drop_release()
                        print("[ROBOT] 수평 놓기 + 복귀")
                    else:
                        robot.drop_release()
                        print("[ROBOT] 수직 놓기 + 복귀")
                    drop_pending = False
                    holding_tube = False
                    pickup_mode  = None
                    if selected_child:
                        tube_slots.add(selected_child.get("slot",""))
                    pickup_pending = False
                    selected_zone  = None
                    selected_child = None
                    state = "STAGE1"
                    print("[INFO] 1단계로 복귀")
                elif not holding_stir:
                    robot.grip_open()
                    holding_tube = False
                    pickup_mode  = None
                    print("[ROBOT] 그리퍼 열기")

            elif action == "POUR" and robot:
                if holding_tube and beaker_ready:
                    robot.beaker_pour()
                    beaker_ready = False
                    holding_tube = False
                    print("[ROBOT] 붓기 동작")
                    selected_zone  = None
                    selected_child = None
                    state = "STAGE1"

            elif action == "SHAKE" and robot:
                if holding_stir and stir_step == "BEAKER_MOVING":
                    ok = robot.stir_do()
                    print(f"  [ROBOT] stir_do → {ok}")
                    if ok:
                        stir_step    = "STIRRING"
                        holding_stir = True
                        state        = "STAGE1"
                        print("[ROBOT] 섞기 실행 → 홈 복귀 후 전체 구역 표시")

            elif action == "MOVE":
                state          = "STAGE1"
                selected_zone  = None
                selected_child = None
                print("[INFO] 1단계로 복귀")

        # 1단계 구역 박스 → 숨김 (표시 안 함)
        # CANCEL 구역만 항상 표시
        for z in zones:
            if z["name"].upper() == "HOME":
                x1,y1,x2,y2 = z["x1"],z["y1"],z["x2"],z["y2"]
                is_hover = (z["x1"] <= cam_cx <= z["x2"] and
                            z["y1"] <= cam_cy <= z["y2"])
                color = (0, 0, 255) if is_hover else (0, 0, 180)
                cv2.rectangle(display, (x1,y1), (x2,y2), color, 2)
                cv2.putText(display, "HOME",
                            (x1+5, y1+30),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.9, color, 2)

                # CANCEL 구역 Dwell 처리
                if is_hover:
                    if dwell_zone != "HOME":
                        dwell_zone    = "HOME"
                        dwell_start_t = now
                    else:
                        elapsed = now - dwell_start_t
                        pct     = min(elapsed / DWELL_TIME, 1.0)
                        bw      = int((x2-x1) * pct)
                        cv2.rectangle(display,
                                      (x1, y2+4), (x1+bw, y2+12),
                                      (0,0,255), -1)
                        if pct >= 1.0 and now - dwell_last_t > DWELL_COOLDOWN:
                            dwell_last_t = now
                            dwell_zone   = None
                            beaker_ready = False
                            if robot and robot.playing:
                                print("[HOME] 무시 — 이동 중")
                            elif state == "STAGE2" and selected_child:
                                selected_child = None
                                print("[HOME] 세부 선택 취소")
                            else:
                                if robot:
                                    robot.go_home()
                                stir_step         = None
                                stir_pending      = False
                                stir_drop_pending = False
                                pickup_pending    = False
                                drop_pending      = False
                                holding_stir      = False
                                holding_tube      = False
                                selected_zone     = None
                                selected_child    = None
                                state             = "STAGE1"
                                last_gesture      = None
                                print("[HOME] 홈 복귀 + 전체 초기화")
                else:
                    if dwell_zone == "HOME":
                        dwell_zone    = None
                        dwell_start_t = None

        # 세부 박스 표시 (STAGE2일 때만)
        if state == "STAGE2" and selected_zone:
          children = selected_zone.get("children", [])
          zone_name = selected_zone["name"].upper()
          is_tube_zone = "TUBES" in zone_name  # A_tubes, B_tubes
          for i, ch in enumerate(children):
            cx1,cy1,cx2,cy2 = ch["x1"],ch["y1"],ch["x2"],ch["y2"]
            is_selected = (selected_child and
                           selected_child["name"] == ch["name"])

            # 세부 선택 후엔 선택된 것만 표시
            if selected_child and not is_selected:
                continue

            # 인접 슬롯 차단 — 시험관 들고 있을 때 A/B_tubes에서 숨김
            slot = ch.get("slot", "")
            blocked = (holding_tube and is_tube_zone and
                       slot not in tube_slots and
                       not can_drop_at(slot, tube_slots))
            if blocked:
                continue

            if is_selected:
                color = (0, 220, 255)
            else:
                color = (100, 255, 100)
            thick = 3 if is_selected else 2
            cv2.rectangle(display, (cx1,cy1), (cx2,cy2), color, thick)
            cv2.putText(display,
                        f"{i+1}. {ch['name']}",
                        (cx1+5, cy1+28),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)

        # 상태 표시
        if beaker_ready and holding_tube:
            cv2.putText(display,
                        "POUR",
                        (10, 30), cv2.FONT_HERSHEY_SIMPLEX,
                        0.85, (0, 140, 255), 2)
            cv2.putText(display,
                        "MOVE=cancel",
                        (10, 60), cv2.FONT_HERSHEY_SIMPLEX,
                        0.6, (150, 150, 150), 1)
        elif state != "STAGE2" or not selected_zone:
            pass
        elif selected_child:
            cv2.putText(display,
                        f"{selected_child['name']}",
                        (10, 30), cv2.FONT_HERSHEY_SIMPLEX,
                        0.8, (0,220,255), 2)
        else:
            cv2.putText(display,
                        f"{selected_zone['name']} | 1~{len(selected_zone.get('children',[]))}",
                        (10, 30), cv2.FONT_HERSHEY_SIMPLEX,
                        0.8, (0,220,255), 2)
        if state == "STAGE2":
            cv2.putText(display,
                        "MOVE=back to Stage1  ESC=cancel selection",
                        (10, 60), cv2.FONT_HERSHEY_SIMPLEX,
                        0.6, (180,180,180), 1)

        # 커서 표시
        cv2.circle(display, (cam_cx, cam_cy), 12, (255,255,255), 2)
        cv2.circle(display, (cam_cx, cam_cy),  4, (0,255,157), -1)

        # 연결 상태
        conn_text = []
        if cursor_connected:  conn_text.append("Face:OK")
        if gesture_connected: conn_text.append("Gesture:OK")
        cv2.putText(display, "  ".join(conn_text),
                    (10, fh-15), cv2.FONT_HERSHEY_SIMPLEX,
                    0.6, (0,255,157), 1)

        streamer.update(display)
        cv2.imshow("Zone Tracker", display)

        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            break
        elif key == 27:  # ESC
            if selected_child:
                # 세부 선택 취소 → 세부 선택 화면으로
                selected_child = None
                print("[INFO] 세부 선택 취소")
            elif state == "STAGE2":
                # 2단계 취소 → 1단계로 복귀
                state          = "STAGE1"
                selected_zone  = None
                selected_child = None
                print("[INFO] 1단계로 복귀")


    streamer.stop()
    cap.release()
    cv2.destroyAllWindows()
    print("[INFO] 종료")


if __name__ == "__main__":
    main()