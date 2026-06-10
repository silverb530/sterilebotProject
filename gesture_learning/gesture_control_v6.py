"""
ChemiBot — MediaPipe 손동작 제어 v6
특징 추출(거리 기반) + ML 학습 + 실시간 추론
"""

import argparse
import cv2
import mediapipe as mp
import numpy as np
import math
import time
import pickle
import os
import socket
import json
import threading
from collections import Counter
from mjpeg_streamer import MjpegStreamer
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report

CAMERA_ID    = 2
CAM_W, CAM_H = 640, 480
ROBOT_Z_DEFAULT = 200
GESTURE_HOLD_TIME = 0.5
POUR_ANGLE_THRESHOLD = 25
SAMPLES_PER_GESTURE = 200
MODEL_PATH = "models/gesture_model_v6.pkl"

# ── zone_tracker 소켓 송신 ──
ZONE_TRACKER_HOST = "127.0.0.1"
ZONE_TRACKER_PORT = 9003
zone_sock = None

def connect_zone_tracker():
    global zone_sock
    try:
        zone_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        zone_sock.connect((ZONE_TRACKER_HOST, ZONE_TRACKER_PORT))
        print(f"[INFO] zone_tracker 연결됨 (포트 {ZONE_TRACKER_PORT})")
    except Exception:
        zone_sock = None
        print(f"[WARN] zone_tracker 연결 실패")

def send_gesture(gesture):
    global zone_sock
    if zone_sock is None:
        connect_zone_tracker()  # 재연결 시도
    if zone_sock is None:
        print(f"[WARN] zone_tracker 미연결 — {gesture} 전송 실패")
        return
    try:
        msg = {"gesture": gesture}
        if gesture in ("1","2","3","4"):
            msg["finger"] = int(gesture)
            msg["action"] = None
        else:
            msg["finger"] = None
            msg["action"] = gesture
        data = json.dumps(msg) + "\n"
        zone_sock.sendall(data.encode())
        print(f"[GESTURE] → {gesture}")
    except Exception as e:
        print(f"[WARN] zone_tracker 전송 실패: {e}")
        zone_sock = None

mp_hands = mp.solutions.hands
mp_draw  = mp.solutions.drawing_utils
hands    = mp_hands.Hands(static_image_mode=False, max_num_hands=1,
                          min_detection_confidence=0.7, min_tracking_confidence=0.6)

USE_PIL = False
font_large = font_mid = font_small = None
try:
    from PIL import ImageFont, ImageDraw, Image
    for fp in ["C:/Windows/Fonts/malgun.ttf","C:/Windows/Fonts/MALGUN.TTF","C:/Windows/Fonts/gulim.ttc"]:
        try:
            font_large = ImageFont.truetype(fp, 28)
            font_mid   = ImageFont.truetype(fp, 20)
            font_small = ImageFont.truetype(fp, 14)
            USE_PIL = True; break
        except: continue
except ImportError: pass

def put_text(frame, text, pos, font=None, color=(255,255,255)):
    if USE_PIL and font:
        img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        ImageDraw.Draw(img).text(pos, text, font=font, fill=color)
        return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
    cv2.putText(frame, text, (pos[0], pos[1]+20), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
    return frame


# ══════════════════════════════════════════════════════════════════
#  특징 추출
# ══════════════════════════════════════════════════════════════════
def dist(a, b):
    return math.sqrt((a.x-b.x)**2 + (a.y-b.y)**2)

def extract_features(lm):
    hand_size = dist(lm[0], lm[9])
    if hand_size < 0.01:
        return [0.0] * 16
    features = []
    thumb_tip = dist(lm[4], lm[5]) / (hand_size + 1e-6)
    thumb_ref = dist(lm[3], lm[5]) / (hand_size + 1e-6)
    thumb_ratio = thumb_tip / (thumb_ref + 1e-6)
    thumb_open = min(1.0, max(0.0, (thumb_ratio - 0.8) / 0.8))
    features.extend([thumb_ratio, thumb_open])
    thumb_to_mid    = dist(lm[4], lm[9])  / (hand_size + 1e-6)
    thumb_to_wrist  = dist(lm[4], lm[0])  / (hand_size + 1e-6)
    thumb_to_midtip = dist(lm[4], lm[12]) / (hand_size + 1e-6)
    features.extend([thumb_to_mid, thumb_to_wrist, thumb_to_midtip])
    for tip, pip, mcp in [(8,6,5), (12,10,9), (16,14,13), (20,18,17)]:
        tip_d = dist(lm[tip], lm[mcp])
        pip_d = dist(lm[pip], lm[mcp])
        ratio = tip_d / (pip_d + 1e-6)
        openness = min(1.0, max(0.0, (ratio - 0.8) / 1.2))
        features.extend([ratio, openness])
    features.extend([dist(lm[4], lm[8]) / (hand_size + 1e-6),
                     dist(lm[4], lm[20]) / (hand_size + 1e-6)])
    tilt = abs(math.atan2(abs(lm[9].x-lm[0].x), abs(lm[0].y-lm[9].y)+0.001))
    features.append(tilt)
    return features

def get_finger_states_from_features(features):
    if len(features) < 16:
        return [False]*5, [0.0]*5
    states, openness = [False]*5, [0.0]*5
    states[0]   = features[0] > 1.2 and features[2] > 0.8
    openness[0] = features[1]
    for i, idx in enumerate([5, 7, 9, 11]):
        states[i+1]   = features[idx] > 1.3
        openness[i+1] = features[idx+1]
    return states, openness


# ══════════════════════════════════════════════════════════════════
#  제스처 정의
# ══════════════════════════════════════════════════════════════════
GESTURES = ["GRAB", "POUR", "RELEASE", "SHAKE", "1", "2", "3", "4", "STOP"]
GESTURE_INSTRUCTIONS = {
    "GRAB":"주먹을 쥐세요", "POUR":"엄지만 펴세요",
    "RELEASE":"엄지+검지를 펴세요", "SHAKE":"엄지+새끼를 펴세요",
    "1":"검지 1개만", "2":"검지+중지 2개", "3":"검지+중지+약지 3개", "4":"엄지 빼고 4개",
    "STOP":"손바닥 전체 펴세요 (5개 모두)",
}
LABELS_KR = {
    "GRAB":"잡기","RELEASE":"놓기","POUR":"붓기","SHAKE":"흔들기",
    "STOP":"정지","UNKNOWN":"...","1":"1","2":"2","3":"3","4":"4",
}
COLORS = {
    "GRAB":(33,150,243),"RELEASE":(255,193,7),"POUR":(156,39,176),"SHAKE":(255,87,34),
    "1":(0,150,60),"2":(0,150,60),"3":(0,150,60),"4":(0,150,60),
    "STOP":(100,100,100),"UNKNOWN":(60,60,60),
}


# ══════════════════════════════════════════════════════════════════
#  데이터 수집
# ══════════════════════════════════════════════════════════════════
def collect_data():
    cap = cv2.VideoCapture(CAMERA_ID, cv2.CAP_DSHOW)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAM_W)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAM_H)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    all_features, all_labels = [], []
    print("="*50)
    print(f"  데이터 수집: {len(GESTURES)}개 x {SAMPLES_PER_GESTURE}개")
    print("  ★ 손 위치/각도를 계속 바꿔가며 수집하세요!")
    print("="*50)
    for gesture in GESTURES:
        instruction = GESTURE_INSTRUCTIONS[gesture]
        label_kr = LABELS_KR.get(gesture, gesture)
        collected = 0; ready_start = None; waiting = True
        print(f"\n[{gesture}] {instruction}")
        while collected < SAMPLES_PER_GESTURE:
            ret, frame = cap.read()
            if not ret: break
            frame = cv2.flip(frame, 1)
            result = hands.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            h, w = frame.shape[:2]
            cv2.rectangle(frame, (0,0), (w,60), (50,50,50), -1)
            frame = put_text(frame, f"{label_kr} ({gesture})  [{collected}/{SAMPLES_PER_GESTURE}]", (12,5), font_large, (255,255,255))
            frame = put_text(frame, instruction, (12,70), font_mid, (100,255,100))
            pw = int(collected / SAMPLES_PER_GESTURE * (w-40))
            cv2.rectangle(frame, (20,h-30), (20+pw,h-18), (76,175,80), -1)
            cv2.rectangle(frame, (20,h-30), (w-20,h-18), (100,100,100), 1)
            if result and hasattr(result, 'multi_hand_landmarks') and result.multi_hand_landmarks:
                for hlm in result.multi_hand_landmarks:
                    mp_draw.draw_landmarks(frame, hlm, mp_hands.HAND_CONNECTIONS)
                    if waiting:
                        if ready_start is None: ready_start = time.time()
                        rem = 3 - (time.time() - ready_start)
                        if rem > 0:
                            frame = put_text(frame, f"{int(rem)+1}초 후 수집...", (w//2-80,h//2-20), font_mid, (255,255,0))
                        else:
                            waiting = False; print("  수집 시작!")
                    else:
                        feat = extract_features(hlm.landmark)
                        all_features.append(feat); all_labels.append(gesture)
                        collected += 1
                        cv2.circle(frame, (w-40,40), 15, (0,255,0), -1)
                        time.sleep(0.03)
            else:
                ready_start = None
            cv2.imshow("ChemiBot v6 - Data Collection", frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                cap.release(); cv2.destroyAllWindows(); return None, None
        print(f"  {gesture} 완료! ({collected}개)")
        waiting = True; ready_start = None
        for _ in range(40):
            ret, frame = cap.read()
            if not ret: break
            frame = cv2.flip(frame, 1); h, w = frame.shape[:2]
            cv2.rectangle(frame, (0,0), (w,h), (30,30,30), -1)
            frame = put_text(frame, f"{label_kr} 완료!", (w//2-60,h//2-40), font_large, (0,255,0))
            frame = put_text(frame, "다음 제스처 준비...", (w//2-80,h//2+10), font_mid, (200,200,200))
            cv2.imshow("ChemiBot v6 - Data Collection", frame); cv2.waitKey(50)
    cap.release(); cv2.destroyAllWindows()
    return all_features, all_labels


# ══════════════════════════════════════════════════════════════════
#  학습
# ══════════════════════════════════════════════════════════════════
def train_model(features, labels):
    X, y = np.array(features), np.array(labels)
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    print(f"\n학습: {len(X_train)}개 / 테스트: {len(X_test)}개")
    model = RandomForestClassifier(n_estimators=300, max_depth=15, class_weight="balanced", random_state=42)
    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)
    print(f"정확도: {accuracy_score(y_test,y_pred)*100:.1f}%")
    print(classification_report(y_test, y_pred))
    os.makedirs("models", exist_ok=True)
    with open(MODEL_PATH, "wb") as f: pickle.dump(model, f)
    print(f"모델 저장: {MODEL_PATH}")
    return model


# ══════════════════════════════════════════════════════════════════
#  로봇 제어
# ══════════════════════════════════════════════════════════════════
robot = None
_wpf_mode = False  # WPF 자동 실행 시 True → cv2 창 숨김

def robot_grip():
    if robot: robot.grip_close()
    else: print("  [ROBOT] 잡기")

def robot_release():
    if robot: robot.grip_open()
    else: print("  [ROBOT] 놓기")

def robot_pour(slot):
    """붓기: 슬롯 옆면 집기 → 비커 붓기 → 원래 위치 꽂기"""
    if robot: robot.pour(slot)
    else: print(f"  [ROBOT] 붓기 {slot}")

def robot_shake():
    """섞기: 막대기 집기 → 섞기 동작 → 막대기 내려놓기"""
    if robot: robot.stir()
    else: print("  [ROBOT] 섞기")

def robot_stop():
    if robot: robot.stop()
    else: print("  [ROBOT] 정지")

def get_tilt(lm):
    return abs(math.degrees(math.atan2(abs(lm[9].x-lm[0].x), abs(lm[0].y-lm[9].y)+0.001)))


# ══════════════════════════════════════════════════════════════════
#  실시간 인식
# ══════════════════════════════════════════════════════════════════
def run_realtime(model):
    cap = cv2.VideoCapture(CAMERA_ID, cv2.CAP_DSHOW)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAM_W)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAM_H)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    # WPF 자동 실행 시 창을 화면 밖으로 숨기고 MJPEG 스트리밍 시작
    cv2.namedWindow("ChemiBot - Gesture Control v6", cv2.WINDOW_NORMAL)
    if _wpf_mode:
        cv2.moveWindow("ChemiBot - Gesture Control v6", -10000, -10000)
        cv2.resizeWindow("ChemiBot - Gesture Control v6", 1, 1)
        streamer = MjpegStreamer(port=8091)
        streamer.start()
    else:
        streamer = None

    grabbed = False
    no_hand_frames = 0

    # 상태: IDLE → MEASURING → EXECUTE → IDLE / POSITIONED
    state = "IDLE"
    measure_start = 0
    measure_preds = []
    MEASURE_SEC = 2.0
    MIN_CONFIDENCE = 60
    execute_start = 0
    execute_gesture = ""
    execute_conf = 0
    execute_blocked = False
    selected_tube = None  # POSITIONED 상태에서 선택된 튜브 번호
    last_gesture = "UNKNOWN"

    print("\n" + "="*50)
    print("  ChemiBot v6 실시간 인식")
    print("  1~4: 튜브 위치 이동  |  주먹: 잡기")
    print("  엄지: 붓기  |  엄지+검지: 놓기")
    print("  손 치우면 정지  |  Q: 종료")
    print("="*50)

    while True:
        ret, frame = cap.read()
        if not ret: break
        frame = cv2.flip(frame, 1)
        result = hands.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        h, w = frame.shape[:2]
        gesture = "UNKNOWN"; confidence = 0; tilt = None
        finger_states = [False]*5; openness = [0.0]*5
        now = time.time()

        # ── 손 감지 ──
        if result and hasattr(result, 'multi_hand_landmarks') and result.multi_hand_landmarks:
            no_hand_frames = 0
            for hlm in result.multi_hand_landmarks:
                mp_draw.draw_landmarks(frame, hlm, mp_hands.HAND_CONNECTIONS)
                lm = hlm.landmark
                tilt = get_tilt(lm)
                feat = extract_features(lm)
                finger_states, openness = get_finger_states_from_features(feat)
                proba = model.predict_proba([feat])[0]
                pred_idx = np.argmax(proba)
                gesture = model.classes_[pred_idx]
                confidence = proba[pred_idx] * 100
        else:
            no_hand_frames += 1
            if no_hand_frames > 10:
                if last_gesture == "STOP":
                    # 손 치움 → STOP 해제, Zone_tracker에 재개 신호
                    last_gesture = "UNKNOWN"
                    print("[INFO] 정지 해제")
                    send_gesture("STOP_RELEASE")
                gesture = "UNKNOWN"  # 손 없으면 항상 UNKNOWN (STOP 루프 방지)

        # ── 상태 머신 ──
        if state == "IDLE":
            if robot and robot.playing:
                pass  # 로봇 동작 중 차단
            elif gesture not in ("UNKNOWN","STOP") and confidence >= 50:
                last_gesture = gesture
                state = "MEASURING"
                measure_start = now
                measure_preds = [(gesture, confidence)]
            elif gesture == "STOP" and last_gesture != "STOP":
                robot_stop()
                send_gesture("STOP")  # Zone_tracker에도 정지 전송
                last_gesture = "STOP"

        elif state == "POSITIONED":
            # 튜브 위치 도달 — GRAB만 받음
            if robot and robot.playing:
                pass  # 아직 이동 중
            elif gesture == "GRAB" and confidence >= 50:
                state = "MEASURING"
                measure_start = now
                measure_preds = [(gesture, confidence)]
            elif no_hand_frames > 15:
                state = "IDLE"

        elif state == "MEASURING":
            elapsed = now - measure_start
            remaining = MEASURE_SEC - elapsed
            if gesture == "STOP" or no_hand_frames > 5:
                state = "POSITIONED" if (selected_tube and not (robot and robot.playing)) else "IDLE"
                measure_preds = []
            elif remaining <= 0:
                all_g = [g for g,c in measure_preds]
                counts = Counter(all_g)
                best_gesture, best_count = counts.most_common(1)[0]
                best_confs = [c for g,c in measure_preds if g == best_gesture]
                avg_conf = sum(best_confs) / len(best_confs)
                vote_ratio = best_count / len(measure_preds) * 100
                execute_gesture = best_gesture
                execute_conf = avg_conf
                execute_start = now
                label_kr = LABELS_KR.get(best_gesture, best_gesture)

                if avg_conf < MIN_CONFIDENCE or vote_ratio < 50:
                    execute_blocked = True
                    state = "EXECUTE"
                    print(f"  [경고] {label_kr} — 신뢰도 {avg_conf:.0f}% → 차단")
                else:
                    execute_blocked = False
                    print(f"  [실행] {label_kr} — {avg_conf:.0f}%")
                    send_gesture(best_gesture)  # zone_tracker로 전송

                    # ★ zone_tracker 연결됐으면 로봇 직접 제어 안 함
                    # zone_tracker가 모든 로봇 명령 처리
                    if zone_sock is not None:
                        state = "EXECUTE"
                    else:
                        # zone_tracker 없을 때만 직접 제어
                        if best_gesture in ("1","2","3","4"):
                            selected_tube = int(best_gesture)
                            if robot and not robot.playing:
                                robot.pickup_move(selected_tube)
                            state = "POSITIONED"

                        elif best_gesture == "GRAB":
                            if selected_tube:
                                if robot: robot.pickup_grip()
                                robot_grip(); grabbed = True
                                selected_tube = None
                            elif not grabbed:
                                robot_grip(); grabbed = True
                            state = "EXECUTE"

                        elif best_gesture == "RELEASE":
                            robot_release(); grabbed = False
                            state = "EXECUTE"

                        elif best_gesture == "POUR":
                            pour_slot = f"A{selected_tube}" if selected_tube else "A1"
                            robot_pour(pour_slot)
                            selected_tube = None
                            state = "EXECUTE"

                        elif best_gesture == "SHAKE":
                            robot_shake()
                            state = "EXECUTE"

            else:
                if gesture not in ("UNKNOWN","STOP"):
                    measure_preds.append((gesture, confidence))

        elif state == "EXECUTE":
            robot_done = not (robot and robot.playing)
            if now - execute_start > 2.0 and robot_done:
                state = "IDLE"
                measure_preds = []

        # ── UI ──
        if state == "IDLE":
            if robot and robot.playing:
                display_label = f"로봇: {robot.current_action}"
                bar_color = (50,120,50); conf_text = ""
            elif gesture not in ("UNKNOWN","STOP"):
                display_label = LABELS_KR.get(gesture, gesture)
                bar_color = COLORS.get(gesture,(60,60,60))
                conf_text = f"  ({confidence:.0f}%)"
            elif gesture == "STOP":
                display_label = "정지"; bar_color = COLORS["STOP"]; conf_text = ""
            else:
                display_label = "대기 중..."; bar_color = (60,60,60); conf_text = ""
            cv2.rectangle(frame, (0,0), (w,54), bar_color, -1)
            if USE_PIL:
                frame = put_text(frame, f"{display_label}{conf_text}", (12,8), font_large, (255,255,255))
            else:
                cv2.putText(frame, f"{display_label}{conf_text}", (15,38), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255,255,255), 2)

        elif state == "POSITIONED":
            cv2.rectangle(frame, (0,0), (w,54), (0,120,200), -1)
            msg = f"tube_{selected_tube} 도달 — 주먹 쥐어 잡기"
            if USE_PIL:
                frame = put_text(frame, msg, (12,8), font_large, (255,255,255))
            else:
                cv2.putText(frame, msg, (15,38), cv2.FONT_HERSHEY_SIMPLEX, 0.85, (255,255,255), 2)

        elif state == "MEASURING":
            elapsed2 = now - measure_start
            remaining2 = max(0, MEASURE_SEC - elapsed2)
            progress = min(1.0, elapsed2 / MEASURE_SEC)
            if measure_preds:
                all_g2 = [g for g,c in measure_preds]
                top_g = Counter(all_g2).most_common(1)[0][0]
                top_label = LABELS_KR.get(top_g, top_g)
                top_confs = [c for g,c in measure_preds if g==top_g]
                avg_c = sum(top_confs)/len(top_confs)
            else:
                top_label = "..."; avg_c = 0
            cv2.rectangle(frame, (0,0), (w,84), (40,40,40), -1)
            bw = int(progress*(w-40))
            cv2.rectangle(frame, (20,62), (20+bw,76), (76,175,80), -1)
            cv2.rectangle(frame, (20,62), (w-20,76), (100,100,100), 1)
            if USE_PIL:
                frame = put_text(frame, f"인식 중... {remaining2:.1f}초", (12,4), font_mid, (255,255,0))
                frame = put_text(frame, f"{top_label} ({avg_c:.0f}%)", (12,32), font_large, (255,255,255))
            else:
                cv2.putText(frame, f"Measuring... {remaining2:.1f}s", (15,22), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,255,0), 2)
                cv2.putText(frame, f"{top_label} ({avg_c:.0f}%)", (15,55), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255,255,255), 2)
            cv2.putText(frame, f"samples: {len(measure_preds)}", (w-150,76), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (150,200,150), 1)

        elif state == "EXECUTE":
            label_kr2 = LABELS_KR.get(execute_gesture, execute_gesture)
            if execute_blocked:
                cv2.rectangle(frame, (0,0), (w,84), (40,40,180), -1)
                if USE_PIL:
                    frame = put_text(frame, f"✗ {label_kr2} — 인식 불확실", (12,4), font_large, (255,255,255))
                    frame = put_text(frame, f"신뢰도 {execute_conf:.0f}% → 다시 시도", (12,42), font_mid, (255,200,200))
                else:
                    cv2.putText(frame, f"X {label_kr2} - LOW CONFIDENCE", (15,35), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255,255,255), 2)
                    cv2.putText(frame, f"{execute_conf:.0f}% - Try again", (15,65), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,200,200), 2)
            else:
                exec_color = COLORS.get(execute_gesture,(60,60,60))
                cv2.rectangle(frame, (0,0), (w,84), exec_color, -1)
                if USE_PIL:
                    frame = put_text(frame, f"✓ {label_kr2} 실행!", (12,4), font_large, (255,255,255))
                    frame = put_text(frame, f"신뢰도: {execute_conf:.0f}%", (12,42), font_mid, (220,255,220))
                else:
                    cv2.putText(frame, f">> {label_kr2} EXECUTE!", (15,35), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255,255,255), 2)
                    cv2.putText(frame, f"Confidence: {execute_conf:.0f}%", (15,65), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (220,255,220), 2)

        if tilt is not None:
            bc = (156,39,176) if tilt > POUR_ANGLE_THRESHOLD else (200,200,200)
            cv2.putText(frame, f"Tilt: {int(tilt)} deg", (10,h-22), cv2.FONT_HERSHEY_SIMPLEX, 0.5, bc, 1)
        if result and hasattr(result, 'multi_hand_landmarks') and result.multi_hand_landmarks:
            names = ["Th","In","Mi","Ri","Pi"]
            dbg = " ".join([f"{names[i]}:{'O' if finger_states[i] else 'x'}({openness[i]:.1f})" for i in range(5)])
            cv2.putText(frame, dbg, (10,h-48), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (180,220,255), 1)
        cv2.putText(frame, "Q: Quit", (w-80,h-10), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (150,150,150), 1)
        if robot:
            status = robot.get_status()
            cv2.circle(frame, (w-20,20), 6, (0,255,0) if status["connected"] else (0,0,255), -1)
            if status["playing"]:
                cv2.putText(frame, f"ROBOT: {status['action']}", (w-250,20), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (100,255,100), 1)
            cv2.putText(frame, f"Grip: {status['gripper']}", (w-120,h-28), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (180,180,180), 1)

        if streamer:
            streamer.update(frame)
        cv2.imshow("ChemiBot - Gesture Control v6", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'): break

    if streamer:
        streamer.stop()
    cap.release(); cv2.destroyAllWindows()


# ══════════════════════════════════════════════════════════════════
#  메인
# ══════════════════════════════════════════════════════════════════
def main():
    global robot
    print("="*50)
    print("  ChemiBot v6 — 손동작 제어")
    print("="*50)

    # 명령행 인자 (WPF 자동 실행용). 인자 없으면 기존 콘솔 input 방식.
    parser = argparse.ArgumentParser()
    parser.add_argument("--robot", choices=["yes", "no"], default=None)
    parser.add_argument("--ip",   type=str, default="192.168.0.32")
    parser.add_argument("--port", type=int, default=5001)
    parser.add_argument("--home", choices=["yes", "no"], default="no")
    args, _ = parser.parse_known_args()

    global _wpf_mode
    _wpf_mode = (args.robot is not None)  # WPF에서 실행 시 True

    if args.robot is None:
        # 수동 실행 → 기존 콘솔 input
        use_robot = input("\n로봇 연결? (y/n, 기본 n): ").strip().lower()
        if use_robot == 'y':
            from robot_controller import RobotController
            ip   = input("로봇 IP (기본 192.168.0.27): ").strip() or "192.168.0.27"
            port = input("포트 (기본 5001): ").strip() or "5001"
            robot = RobotController(ip=ip, port=int(port))
            if robot.connected:
                if input("홈 위치로 이동? (y/n): ").strip().lower() == 'y':
                    robot.go_home()
        else:
            robot = None
            print("[INFO] 시뮬레이션 모드")
    elif args.robot == "yes":
        from robot_controller import RobotController
        robot = RobotController(ip=args.ip, port=args.port)
        if robot.connected and args.home == "yes":
            robot.go_home()
        if not robot.connected:
            robot = None
            print("[WARN] 로봇 연결 실패 → 시뮬레이션 모드")
    else:
        robot = None
        print("[INFO] 시뮬레이션 모드 (--robot no)")

    # zone_tracker 연결
    connect_zone_tracker()

    # 모델 로드: WPF 자동 실행 시 기존 모델 무조건 로드 (input 없이)
    model = None
    if os.path.exists(MODEL_PATH):
        if args.robot is None:
            # 수동: 물어봄
            print(f"\n[모델] 기존 파일: {MODEL_PATH}")
            if input("기존 모델 사용? (y/n): ").strip().lower() == 'y':
                with open(MODEL_PATH, "rb") as f: model = pickle.load(f)
                print(f"[INFO] 로드 완료: {list(model.classes_)}")
        else:
            # 자동: 무조건 로드
            with open(MODEL_PATH, "rb") as f: model = pickle.load(f)
            print(f"[INFO] 모델 자동 로드: {list(model.classes_)}")

    if model is None:
        print(f"\n[학습] {len(GESTURES)}개 x {SAMPLES_PER_GESTURE}개 수집")
        features, labels = collect_data()
        if features is None: return
        model = train_model(features, labels)

    print("\n[실시간 인식 시작]")
    run_realtime(model)

if __name__ == '__main__':
    main()