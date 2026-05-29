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

import cv2
import json
import os
import sys
import time
import socket
import threading
import ctypes

# ────────────────────────────────────────────────
#  설정값
# ────────────────────────────────────────────────
CAMERA_INDEX    = 2
ZONE_FILE       = "zone_data.json"
CURSOR_PORT     = 9002
GESTURE_PORT    = 9003
DWELL_TIME      = 0.8
DWELL_COOLDOWN  = 1.5

# ────────────────────────────────────────────────
#  구역 파일 로드
# ────────────────────────────────────────────────
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

    # 로봇 연결
    robot = None
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
        print("[INFO] 시뮬레이션 모드")

    # 소켓 스레드 시작
    threading.Thread(target=cursor_receiver,  daemon=True).start()
    threading.Thread(target=gesture_receiver, daemon=True).start()

    # 웹캠
    cap = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_DSHOW)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    fw = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    fh = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print(f"[INFO] 웹캠: {fw}x{fh}")

    cv2.namedWindow("Zone Tracker", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("Zone Tracker", fw, fh)

    screen_w = ctypes.windll.user32.GetSystemMetrics(0)
    screen_h = ctypes.windll.user32.GetSystemMetrics(1)

    # 상태
    state          = "STAGE1"   # STAGE1: 큰구역선택 / STAGE2: 세부선택
    selected_zone  = None       # 선택된 1단계 구역
    selected_child = None       # 선택된 세부 구역
    tube_slots     = set()      # 시험관이 꽂혀있는 슬롯 추적 (수평 집기용)
    pickup_pending = False      # pickup_move 후 GRAB 대기 중 여부
    drop_pending   = False      # drop_move 후 RELEASE 대기 중 여부
    holding_tube   = False      # 시험관 잡고 있는 상태
    pickup_mode    = None       # "vertical" or "horizontal"
    beaker_ready   = False      # 비커 위치 도달 후 POUR 대기
    dwell_zone     = None
    dwell_start_t  = None
    dwell_last_t   = 0.0
    last_gesture   = None

    print("\n[INFO] 트래킹 시작! (q: 종료)")

    while True:
        ret, frame = cap.read()
        if not ret:
            continue

        display = frame.copy()
        now     = time.time()

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
                if dwell_zone != hover_zone["name"]:
                    dwell_zone    = hover_zone["name"]
                    dwell_start_t = now
                else:
                    elapsed = now - dwell_start_t
                    pct     = min(elapsed / DWELL_TIME, 1.0)

                    if pct >= 1.0 and now - dwell_last_t > DWELL_COOLDOWN:
                        dwell_last_t  = now
                        dwell_zone    = None

                        # CANCEL 구역 선택 시
                        if hover_zone["name"].upper() == "CANCEL":
                            if state == "STAGE2":
                                if selected_child:
                                    selected_child = None
                                    print("[CANCEL] 세부 선택 취소")
                                else:
                                    state         = "STAGE1"
                                    selected_zone = None
                                    print("[CANCEL] 1단계로 복귀")
                        elif hover_zone["name"].upper() == "BEAKER" and holding_tube:
                            # 비커 선택 → 비커 위치로 이동
                            print("[BEAKER] 비커 위치로 이동 → POUR 제스처로 붓기")
                            beaker_ready = True
                            if robot:
                                robot.beaker_move()
                        else:
                            # 1단계 구역 선택 완료
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
                is_cancel = z["name"].upper() == "CANCEL"
                is_beaker = z["name"].upper() == "BEAKER"
                is_hover  = hover_zone and hover_zone["name"] == z["name"]

                # beaker_ready 상태면 비커만 표시, 나머지 숨김
                if beaker_ready and not is_beaker:
                    continue

                if is_cancel:
                    color = (0, 0, 255) if is_hover else (0, 0, 180)
                else:
                    color = (0, 220, 255) if is_hover else (0, 255, 157)
                thick = 3 if is_hover else 2
                cv2.rectangle(display, (x1,y1), (x2,y2), color, thick)
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
            cv2.putText(display,
                        "1단계: 시선으로 구역 선택 (Dwell)",
                        (10, 30), cv2.FONT_HERSHEY_SIMPLEX,
                        0.8, (0,255,255), 2)

        # ── STAGE1에서 POUR 처리 (비커 이동 후) ──
        if state == "STAGE1" and holding_tube and beaker_ready:
            if gesture and gesture.get("action") == "POUR":
                if robot and robot.playing:
                    pass  # 아직 이동 중
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
                        # 시약통 → pickup_move(tube_num) [수직]
                        tube_num = finger
                        if robot:
                            ok = robot.pickup_move(tube_num)
                            print(f"  [ROBOT] pickup_move({tube_num}) → {ok}")
                            if ok:
                                pickup_pending = True
                                pickup_mode    = "vertical"
                        else:
                            print(f"  [SIM] pickup_move({tube_num})")
                            pickup_pending = True
                            pickup_mode    = "vertical"
                    else:
                        # A_tubes, B_tubes
                        # 이미 꽂혀있는 슬롯이면 수평 집기, 아니면 수직 꽂기
                        # (꽂은 후 바로 POUR/GRAB 등 추가 동작 가능)
                        if slot in tube_slots:
                            # 꽂혀있는 슬롯 → 수평 이동 후 GRAB 대기
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
                            # 빈 슬롯
                            if holding_tube and pickup_mode == "horizontal":
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

            # 제스처로 동작 제어 (로봇 동작 중이면 대기)
            if gesture and "action" in gesture and (selected_child or holding_tube):
                if robot and robot.playing:
                    pass  # 로봇 동작 중 — 제스처 무시
                else:
                    action = gesture["action"]
                    if action == "GRAB" and robot:
                        if pickup_pending:
                            robot.pickup_grip()
                            pickup_pending = False
                            holding_tube   = True
                            # pickup_mode는 pickup_move/pickup_lift_move에서 이미 설정됨
                            selected_zone  = None
                            selected_child = None
                            state = "STAGE1"
                            print(f"[ROBOT] 잡기 + 홈 복귀 ({pickup_mode}) → 1단계로 복귀")
                        else:
                            robot.grip_close()
                            print("[ROBOT] 집기")
                    elif action == "RELEASE" and robot:
                        if drop_pending:
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
                        else:
                            robot.grip_open()
                            holding_tube = False
                            pickup_mode  = None
                            print("[ROBOT] 그리퍼 열기")
                        pickup_pending = False
                        selected_zone  = None
                        selected_child = None
                        state = "STAGE1"
                        print("[INFO] 1단계로 복귀")
                    elif action == "POUR" and robot:
                        if holding_tube:
                            robot.beaker_pour()
                            beaker_ready = False
                            print("[ROBOT] 붓기 동작")
                        else:
                            pour_slot = selected_child.get("slot", "A1") if selected_child else "A1"
                            robot.pour(pour_slot)
                            print(f"[ROBOT] 붓기 전체 → {pour_slot}")
                        selected_zone  = None
                        selected_child = None
                        state = "STAGE1"
                    elif action == "SHAKE" and robot:
                        robot.stir()
                        print("[ROBOT] 섞기")
                        selected_zone  = None
                        selected_child = None
                        state = "STAGE1"
                    elif action == "MOVE":
                        state          = "STAGE1"
                        selected_zone  = None
                        selected_child = None
                        print("[INFO] 1단계로 복귀")

            # 1단계 구역 박스 → 숨김 (표시 안 함)
            # CANCEL 구역만 항상 표시
            for z in zones:
                if z["name"].upper() == "CANCEL":
                    x1,y1,x2,y2 = z["x1"],z["y1"],z["x2"],z["y2"]
                    is_hover = (z["x1"] <= cam_cx <= z["x2"] and
                                z["y1"] <= cam_cy <= z["y2"])
                    color = (0, 0, 255) if is_hover else (0, 0, 180)
                    cv2.rectangle(display, (x1,y1), (x2,y2), color, 2)
                    cv2.putText(display, "CANCEL",
                                (x1+5, y1+30),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.9, color, 2)

                    # CANCEL 구역 Dwell 처리
                    if is_hover:
                        if dwell_zone != "CANCEL":
                            dwell_zone    = "CANCEL"
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
                                if selected_child:
                                    selected_child = None
                                    print("[CANCEL] 세부 선택 취소")
                                else:
                                    state         = "STAGE1"
                                    selected_zone = None
                                    print("[CANCEL] 1단계로 복귀")
                    else:
                        if dwell_zone == "CANCEL":
                            dwell_zone    = None
                            dwell_start_t = None

            # 세부 박스 표시
            # 세부 구역 선택 전: 전체 표시 (연두색)
            # 세부 구역 선택 후: 선택된 것만 표시 (노란색)
            for i, ch in enumerate(children):
                cx1,cy1,cx2,cy2 = ch["x1"],ch["y1"],ch["x2"],ch["y2"]
                is_selected = (selected_child and
                               selected_child["name"] == ch["name"])

                # 세부 선택 후엔 선택된 것만 표시
                if selected_child and not is_selected:
                    continue

                color = (0, 220, 255) if is_selected else (100, 255, 100)
                thick = 3 if is_selected else 2
                cv2.rectangle(display, (cx1,cy1), (cx2,cy2), color, thick)
                cv2.putText(display,
                            f"{i+1}. {ch['name']}",
                            (cx1+5, cy1+28),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)

            # 상태 표시
            if beaker_ready and holding_tube:
                cv2.putText(display,
                            "비커 선택됨  |  POUR 제스처로 붓기",
                            (10, 30), cv2.FONT_HERSHEY_SIMPLEX,
                            0.85, (0, 140, 255), 2)
                cv2.putText(display,
                            "MOVE=취소",
                            (10, 60), cv2.FONT_HERSHEY_SIMPLEX,
                            0.6, (150, 150, 150), 1)
            elif state != "STAGE2" or not selected_zone:
                pass
            elif selected_child:
                cv2.putText(display,
                            f"Selected: {selected_child['name']} | ESC=cancel",
                            (10, 30), cv2.FONT_HERSHEY_SIMPLEX,
                            0.8, (0,220,255), 2)
            else:
                cv2.putText(display,
                            f"Stage2: {selected_zone['name']} | Gesture 1~{len(children)}",
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

    cap.release()
    cv2.destroyAllWindows()
    print("[INFO] 종료")


if __name__ == "__main__":
    main()