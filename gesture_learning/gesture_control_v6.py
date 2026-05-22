"""
ChemiBot — MediaPipe 손동작 제어 v6
특징 추출(거리 기반) + ML 학습 + 실시간 추론
제스처 8개:
  1,2,3,4 / 잡기(주먹) / 붓기(엄지) / 놓기(엄지+검지) / 흔들기(엄지+새끼)
정지: 손 안 보이면 자동
"""

import cv2
import mediapipe as mp
import numpy as np
import math
import time
import pickle
import os
from collections import Counter
# from pymycobot.mycobot import MyCobot

from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report

CAMERA_ID    = 0
CAM_W, CAM_H = 640, 480
ROBOT_Z_DEFAULT = 200
ROBOT_SPEED = 20
GESTURE_HOLD_TIME = 0.5
POUR_ANGLE_THRESHOLD = 25
SAMPLES_PER_GESTURE = 200
MODEL_PATH = "models/gesture_model_v6.pkl"

# mc = MyCobot('192.168.0.20', 9000); time.sleep(1)

mp_hands = mp.solutions.hands
mp_draw  = mp.solutions.drawing_utils
hands    = mp_hands.Hands(static_image_mode=False, max_num_hands=1,
                          min_detection_confidence=0.7, min_tracking_confidence=0.6)

# ── 한글 폰트 ──
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
#  특징 추출 — 거리 기반 (회전 불변)
# ══════════════════════════════════════════════════════════════════
def dist(a, b):
    return math.sqrt((a.x-b.x)**2 + (a.y-b.y)**2)

def extract_features(lm):
    """
    랜드마크 → 16개 특징값 추출 (회전 불변)

    [thumb_ratio, thumb_open,                          # 엄지 기본
     thumb_to_mid, thumb_to_wrist, thumb_to_midtip,    # 엄지 추가 (POUR vs GRAB 구분)
     index_ratio, index_open,
     middle_ratio, middle_open,
     ring_ratio, ring_open,
     pinky_ratio, pinky_open,
     thumb_index_spread, thumb_pinky_spread,            # 손가락 벌림
     hand_tilt]                                         # 기울기
    """
    hand_size = dist(lm[0], lm[9])
    if hand_size < 0.01:
        return [0.0] * 16

    features = []

    # ── 엄지 기본 ──
    thumb_tip = dist(lm[4], lm[5]) / (hand_size + 1e-6)
    thumb_ref = dist(lm[3], lm[5]) / (hand_size + 1e-6)
    thumb_ratio = thumb_tip / (thumb_ref + 1e-6)
    thumb_open = min(1.0, max(0.0, (thumb_ratio - 0.8) / 0.8))
    features.extend([thumb_ratio, thumb_open])

    # ── 엄지 추가 (POUR vs GRAB 핵심) ──
    # 엄지 tip → 중지 MCP(9): GRAB이면 가깝고, POUR이면 멀다
    thumb_to_mid = dist(lm[4], lm[9]) / (hand_size + 1e-6)
    # 엄지 tip → 손목(0): POUR이면 더 멀다
    thumb_to_wrist = dist(lm[4], lm[0]) / (hand_size + 1e-6)
    # 엄지 tip → 중지 tip(12): GRAB이면 엄지가 감겨서 가깝고, POUR이면 멀다
    thumb_to_midtip = dist(lm[4], lm[12]) / (hand_size + 1e-6)
    features.extend([thumb_to_mid, thumb_to_wrist, thumb_to_midtip])

    # ── 검지~새끼 ──
    for tip, pip, mcp in [(8,6,5), (12,10,9), (16,14,13), (20,18,17)]:
        tip_d = dist(lm[tip], lm[mcp])
        pip_d = dist(lm[pip], lm[mcp])
        ratio = tip_d / (pip_d + 1e-6)
        openness = min(1.0, max(0.0, (ratio - 0.8) / 1.2))
        features.extend([ratio, openness])

    # ── 손가락 간 벌림 ──
    # 엄지-검지 벌림: RELEASE(엄지+검지) 구분에 도움
    thumb_index_spread = dist(lm[4], lm[8]) / (hand_size + 1e-6)
    # 엄지-새끼 벌림: SHAKE(엄지+새끼) 구분에 도움
    thumb_pinky_spread = dist(lm[4], lm[20]) / (hand_size + 1e-6)
    features.extend([thumb_index_spread, thumb_pinky_spread])

    # ── 손 기울기 ──
    tilt = abs(math.atan2(abs(lm[9].x-lm[0].x), abs(lm[0].y-lm[9].y)+0.001))
    features.append(tilt)

    return features  # 16개


def get_finger_states_from_features(features):
    """특징값에서 손가락 상태 추출 (디버그 표시용)"""
    if len(features) < 16:
        return [False]*5, [0.0]*5
    states = [False] * 5
    openness = [0.0] * 5

    # 엄지: ratio(idx 0) + 추가 특징(idx 2,3,4) 종합 판단
    thumb_ratio = features[0]
    thumb_to_mid = features[2]
    states[0] = thumb_ratio > 1.2 and thumb_to_mid > 0.8
    openness[0] = features[1]

    # 검지~새끼: idx 5,7,9,11 = ratio
    for i, idx in enumerate([5, 7, 9, 11]):
        ratio = features[idx]
        openness[i+1] = features[idx+1]
        states[i+1] = ratio > 1.3

    return states, openness


# ══════════════════════════════════════════════════════════════════
#  제스처 정의
# ══════════════════════════════════════════════════════════════════
GESTURES = ["GRAB", "POUR", "RELEASE", "SHAKE", "1", "2", "3", "4"]
GESTURE_INSTRUCTIONS = {
    "GRAB":    "주먹을 쥐세요",
    "POUR":    "엄지만 펴세요",
    "RELEASE": "엄지 + 검지를 펴세요",
    "SHAKE":   "엄지 + 새끼를 펴세요",
    "1":       "검지 1개만 펴세요",
    "2":       "검지 + 중지 2개 펴세요",
    "3":       "검지 + 중지 + 약지 3개 펴세요",
    "4":       "엄지 빼고 4개 펴세요",
}

LABELS_KR = {
    "GRAB":"잡기", "RELEASE":"놓기", "POUR":"붓기",
    "SHAKE":"흔들기", "STOP":"정지", "UNKNOWN":"...",
    "1":"1", "2":"2", "3":"3", "4":"4",
}

COLORS = {
    "GRAB":(33,150,243), "RELEASE":(255,193,7),
    "POUR":(156,39,176), "SHAKE":(255,87,34),
    "1":(0,150,60), "2":(0,150,60), "3":(0,150,60), "4":(0,150,60),
    "STOP":(100,100,100), "UNKNOWN":(60,60,60),
}


# ══════════════════════════════════════════════════════════════════
#  데이터 수집
# ══════════════════════════════════════════════════════════════════
def collect_data():
    cap = cv2.VideoCapture(CAMERA_ID)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAM_W)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAM_H)
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
            frame = put_text(frame, f"{label_kr} ({gesture})  [{collected}/{SAMPLES_PER_GESTURE}]",
                             (12,5), font_large, (255,255,255))
            frame = put_text(frame, instruction, (12,70), font_mid, (100,255,100))
            pw = int(collected / SAMPLES_PER_GESTURE * (w-40))
            cv2.rectangle(frame, (20,h-30), (20+pw,h-18), (76,175,80), -1)
            cv2.rectangle(frame, (20,h-30), (w-20,h-18), (100,100,100), 1)

            if result.multi_hand_landmarks:
                for hlm in result.multi_hand_landmarks:
                    mp_draw.draw_landmarks(frame, hlm, mp_hands.HAND_CONNECTIONS)
                    if waiting:
                        if ready_start is None: ready_start = time.time()
                        remaining = 3 - (time.time() - ready_start)
                        if remaining > 0:
                            frame = put_text(frame, f"{int(remaining)+1}초 후 수집...",
                                             (w//2-80, h//2-20), font_mid, (255,255,0))
                        else:
                            waiting = False
                            print("  수집 시작!")
                    else:
                        feat = extract_features(hlm.landmark)
                        all_features.append(feat)
                        all_labels.append(gesture)
                        collected += 1
                        cv2.circle(frame, (w-40, 40), 15, (0,255,0), -1)

                        # 디버그: 특징값 표시
                        states, opens = get_finger_states_from_features(feat)
                        names = ["Th","In","Mi","Ri","Pi"]
                        dbg = " ".join([f"{names[i]}:{'O' if states[i] else 'x'}({opens[i]:.1f})" for i in range(5)])
                        cv2.putText(frame, dbg, (10,h-50), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (180,220,255), 1)

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
            frame = put_text(frame, f"{label_kr} 완료!",
                             (w//2-60, h//2-40), font_large, (0,255,0))
            frame = put_text(frame, "다음 제스처 준비...",
                             (w//2-80, h//2+10), font_mid, (200,200,200))
            cv2.imshow("ChemiBot v6 - Data Collection", frame)
            cv2.waitKey(50)

    cap.release(); cv2.destroyAllWindows()
    return all_features, all_labels


# ══════════════════════════════════════════════════════════════════
#  학습
# ══════════════════════════════════════════════════════════════════
def train_model(features, labels):
    X, y = np.array(features), np.array(labels)
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    print(f"\n학습 데이터: {len(X_train)}개 / 테스트: {len(X_test)}개")
    print(f"특징값: {X.shape[1]}개 (손가락 ratio+openness)")
    print("모델 학습 중...")

    model = RandomForestClassifier(
        n_estimators=300,
        max_depth=15,
        class_weight="balanced",
        random_state=42,
    )
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    acc = accuracy_score(y_test, y_pred)
    print(f"\n정확도: {acc*100:.1f}%")
    print("\n클래스별 성능:")
    print(classification_report(y_test, y_pred))

    # 특징 중요도
    feat_names = ["thumb_r","thumb_o","thumb_mid","thumb_wrist","thumb_midtip",
                  "index_r","index_o","middle_r","middle_o",
                  "ring_r","ring_o","pinky_r","pinky_o",
                  "th_in_spread","th_pi_spread","tilt"]
    importances = model.feature_importances_
    print("특징 중요도:")
    for name, imp in sorted(zip(feat_names, importances), key=lambda x: -x[1]):
        bar = "█" * int(imp * 50)
        print(f"  {name:10s} {imp:.3f} {bar}")

    os.makedirs("models", exist_ok=True)
    with open(MODEL_PATH, "wb") as f:
        pickle.dump(model, f)
    print(f"\n모델 저장: {MODEL_PATH}")
    return model


# ══════════════════════════════════════════════════════════════════
#  로봇 제어
# ══════════════════════════════════════════════════════════════════
def robot_grip():    print("  [ROBOT] 잡기")
def robot_release(): print("  [ROBOT] 놓기")
def robot_pour(a):   print(f"  [ROBOT] 붓기 {int(a)}도")
def robot_shake(x,y): print("  [ROBOT] 흔들기")
def robot_stop():    print("  [ROBOT] 정지")

def get_tilt(lm):
    return abs(math.degrees(math.atan2(
        abs(lm[9].x-lm[0].x), abs(lm[0].y-lm[9].y)+0.001)))


# ══════════════════════════════════════════════════════════════════
#  실시간 인식
# ══════════════════════════════════════════════════════════════════
def run_realtime(model):
    cap = cv2.VideoCapture(CAMERA_ID)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAM_W)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAM_H)

    last_gesture = "UNKNOWN"
    last_gesture_time = 0
    grabbed = False
    no_hand_frames = 0
    last_robot_xyz = (0, 0, ROBOT_Z_DEFAULT)

    # 상태 머신: IDLE → MEASURING → EXECUTE → IDLE
    state = "IDLE"
    measure_start = 0
    measure_preds = []       # 측정 중 누적된 (gesture, confidence) 리스트
    MEASURE_SEC = 2.0
    MIN_CONFIDENCE = 60      # 이 이하면 실행 안 하고 경고
    execute_start = 0
    execute_gesture = ""
    execute_conf = 0
    execute_blocked = False   # 신뢰도 부족 → 실행 차단

    print("\n" + "="*50)
    print("  실시간 제스처 인식 (v6)")
    print("  1,2,3,4: 손가락 개수")
    print("  주먹=잡기 | 엄지=붓기")
    print("  엄지+검지=놓기 | 엄지+새끼=흔들기")
    print("  손 치우면 정지 | Q: 종료")
    print("="*50)

    while True:
        ret, frame = cap.read()
        if not ret: break
        frame = cv2.flip(frame, 1)
        result = hands.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        h, w = frame.shape[:2]

        gesture = "UNKNOWN"
        confidence = 0
        tilt = None
        finger_states = [False]*5
        openness = [0.0]*5
        now = time.time()

        # ── 손 감지 + 제스처 추론 ──
        if result.multi_hand_landmarks:
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
                gesture = "STOP"

        # ── 상태 머신 ──
        if state == "IDLE":
            if gesture not in ("UNKNOWN", "STOP") and confidence >= 50:
                # 제스처 감지 → 측정 시작
                state = "MEASURING"
                measure_start = now
                measure_preds = [(gesture, confidence)]
            elif gesture == "STOP" and last_gesture != "STOP":
                robot_stop()
                last_gesture = "STOP"

        elif state == "MEASURING":
            elapsed = now - measure_start
            remaining = MEASURE_SEC - elapsed

            if gesture == "STOP" or no_hand_frames > 5:
                # 손 치움 → 리셋
                state = "IDLE"
                measure_preds = []
            elif remaining <= 0:
                # 3초 완료 → 결과 집계
                all_gestures = [g for g, c in measure_preds]
                counts = Counter(all_gestures)
                best_gesture, best_count = counts.most_common(1)[0]
                # 해당 제스처의 평균 confidence
                best_confs = [c for g, c in measure_preds if g == best_gesture]
                avg_conf = sum(best_confs) / len(best_confs)
                vote_ratio = best_count / len(measure_preds) * 100

                execute_gesture = best_gesture
                execute_conf = avg_conf
                execute_start = now
                state = "EXECUTE"

                label_kr = LABELS_KR.get(best_gesture, best_gesture)

                if avg_conf < MIN_CONFIDENCE or vote_ratio < 50:
                    # 신뢰도 부족 → 경고, 실행 안 함
                    execute_blocked = True
                    print(f"  [경고] {label_kr} — 신뢰도 {avg_conf:.0f}% / 투표 {vote_ratio:.0f}% → 실행 차단")
                else:
                    # 신뢰도 충분 → 실행
                    execute_blocked = False
                    print(f"  [실행] {label_kr} — 신뢰도 {avg_conf:.0f}% (투표 {vote_ratio:.0f}%)")

                    if best_gesture == "GRAB" and not grabbed:
                        robot_grip(); grabbed = True
                    elif best_gesture == "RELEASE" and grabbed:
                        robot_release(); grabbed = False
                    elif best_gesture == "POUR":
                        pour_angle = max(0, min(90, tilt)) if tilt else 45
                        robot_pour(pour_angle)
                    elif best_gesture == "SHAKE":
                        robot_shake(last_robot_xyz[0], last_robot_xyz[1])

                    last_gesture = best_gesture
            else:
                # 측정 중 — 계속 누적
                if gesture not in ("UNKNOWN", "STOP"):
                    measure_preds.append((gesture, confidence))

        elif state == "EXECUTE":
            # 결과 표시 2초 후 IDLE로
            if now - execute_start > 2.0:
                state = "IDLE"
                measure_preds = []

        # ── UI 그리기 ──
        if state == "IDLE":
            if gesture not in ("UNKNOWN", "STOP"):
                display_label = LABELS_KR.get(gesture, gesture)
                bar_color = COLORS.get(gesture, (60,60,60))
                conf_text = f"  ({confidence:.0f}%)"
            elif gesture == "STOP":
                display_label = "정지"
                bar_color = COLORS["STOP"]
                conf_text = ""
            else:
                display_label = "대기 중..."
                bar_color = (60, 60, 60)
                conf_text = ""

            cv2.rectangle(frame, (0,0), (w,54), bar_color, -1)
            if USE_PIL:
                frame = put_text(frame, f"{display_label}{conf_text}",
                                 (12, 8), font_large, (255,255,255))
            else:
                cv2.putText(frame, f"{display_label}{conf_text}",
                            (15, 38), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255,255,255), 2)

        elif state == "MEASURING":
            elapsed = now - measure_start
            remaining = max(0, MEASURE_SEC - elapsed)
            progress = min(1.0, elapsed / MEASURE_SEC)

            # 현재 가장 많은 제스처
            if measure_preds:
                all_g = [g for g, c in measure_preds]
                top_g = Counter(all_g).most_common(1)[0][0]
                top_label = LABELS_KR.get(top_g, top_g)
                top_confs = [c for g, c in measure_preds if g == top_g]
                avg_c = sum(top_confs) / len(top_confs)
            else:
                top_label = "..."
                avg_c = 0

            # 상단 바 (진행 상태)
            cv2.rectangle(frame, (0,0), (w,84), (40, 40, 40), -1)

            # 진행률 바
            bar_w = int(progress * (w - 40))
            bar_color_measure = (76, 175, 80)  # 초록
            cv2.rectangle(frame, (20, 62), (20 + bar_w, 76), bar_color_measure, -1)
            cv2.rectangle(frame, (20, 62), (w-20, 76), (100,100,100), 1)

            # 텍스트
            if USE_PIL:
                frame = put_text(frame, f"인식 중... {remaining:.1f}초",
                                 (12, 4), font_mid, (255,255,0))
                frame = put_text(frame, f"{top_label} ({avg_c:.0f}%)",
                                 (12, 32), font_large, (255,255,255))
            else:
                cv2.putText(frame, f"Measuring... {remaining:.1f}s",
                            (15, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,255,0), 2)
                cv2.putText(frame, f"{top_label} ({avg_c:.0f}%)",
                            (15, 55), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255,255,255), 2)

            # 수집 카운트
            cv2.putText(frame, f"samples: {len(measure_preds)}",
                        (w-150, 76), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (150,200,150), 1)

        elif state == "EXECUTE":
            elapsed = now - execute_start
            label_kr = LABELS_KR.get(execute_gesture, execute_gesture)

            if execute_blocked:
                # ── 경고 UI (빨간색) ──
                cv2.rectangle(frame, (0,0), (w,84), (40, 40, 180), -1)
                if USE_PIL:
                    frame = put_text(frame, f"✗ {label_kr} — 인식 불확실",
                                     (12, 4), font_large, (255,255,255))
                    frame = put_text(frame, f"신뢰도 {execute_conf:.0f}% → 다시 시도하세요",
                                     (12, 42), font_mid, (255,200,200))
                else:
                    cv2.putText(frame, f"X {label_kr} - LOW CONFIDENCE",
                                (15, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255,255,255), 2)
                    cv2.putText(frame, f"{execute_conf:.0f}% - Try again",
                                (15, 65), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,200,200), 2)
            else:
                # ── 실행 UI (제스처 색상) ──
                exec_color = COLORS.get(execute_gesture, (60,60,60))
                cv2.rectangle(frame, (0,0), (w,84), exec_color, -1)
                if USE_PIL:
                    frame = put_text(frame, f"✓ {label_kr} 실행!",
                                     (12, 4), font_large, (255,255,255))
                    frame = put_text(frame, f"신뢰도: {execute_conf:.0f}%",
                                     (12, 42), font_mid, (220,255,220))
                else:
                    cv2.putText(frame, f">> {label_kr} EXECUTE!",
                                (15, 35), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255,255,255), 2)
                    cv2.putText(frame, f"Confidence: {execute_conf:.0f}%",
                                (15, 65), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (220,255,220), 2)

        # 기울기
        if tilt is not None:
            bc = (156,39,176) if tilt > POUR_ANGLE_THRESHOLD else (200,200,200)
            cv2.putText(frame, f"Tilt: {int(tilt)} deg",
                        (10,h-22), cv2.FONT_HERSHEY_SIMPLEX, 0.5, bc, 1)

        # 손가락 디버그
        if result.multi_hand_landmarks:
            names = ["Th","In","Mi","Ri","Pi"]
            dbg = " ".join([f"{names[i]}:{'O' if finger_states[i] else 'x'}({openness[i]:.1f})" for i in range(5)])
            cv2.putText(frame, dbg, (10,h-48), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (180,220,255), 1)

        cv2.putText(frame, "Q: Quit", (w-80,h-10), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (150,150,150), 1)
        cv2.imshow("ChemiBot - Gesture Control v6", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'): break

    cap.release(); cv2.destroyAllWindows()


# ══════════════════════════════════════════════════════════════════
#  메인
# ══════════════════════════════════════════════════════════════════
def main():
    print("="*50)
    print("  ChemiBot v6 — 손동작 제어")
    print("  특징 추출(거리 기반) + ML 학습")
    print("="*50)

    model = None
    if os.path.exists(MODEL_PATH):
        print(f"\n[모델] 기존 파일 발견: {MODEL_PATH}")
        choice = input("기존 모델 사용? (y/n): ").strip().lower()
        if choice == 'y':
            with open(MODEL_PATH, "rb") as f:
                model = pickle.load(f)
            print(f"[INFO] 모델 로드 완료! (클래스: {list(model.classes_)})")

    if model is None:
        print(f"\n[학습] {len(GESTURES)}개 제스처 x {SAMPLES_PER_GESTURE}개 수집")
        features, labels = collect_data()
        if features is None:
            return
        print(f"\n수집 완료: {len(labels)}개")
        model = train_model(features, labels)

    print("\n[실시간 인식 시작]")
    run_realtime(model)


if __name__ == '__main__':
    main()