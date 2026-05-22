"""
ChemiBot — MediaPipe 손동작 제어 v5 (수정)
제스처 5개:
  이동(보자기) / 잡기(주먹) / 붓기(엄지) / 놓기(엄지+검지) / 흔들기(엄지+새끼)
정지: 손 안 보이면 자동
"""

import cv2
import mediapipe as mp
import numpy as np
import math
import time
import pickle
import os
# from pymycobot.mycobot import MyCobot

from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report

CAMERA_ID    = 0
CAM_W, CAM_H = 640, 480
ROBOT_X_MIN, ROBOT_X_MAX = -260, 260
ROBOT_Y_MIN, ROBOT_Y_MAX = -260, 260
ROBOT_Z_MIN, ROBOT_Z_MAX = 50, 300
ROBOT_Z_DEFAULT = 200
ROBOT_SPEED = 20
GESTURE_HOLD_TIME = 0.5
SMOOTH_FRAMES = 5
SHAKE_THRESHOLD = 30
POUR_ANGLE_THRESHOLD = 25

SAMPLES_PER_GESTURE = 100
MODEL_FILE = "gesture_model_v5.pkl"
DATA_FILE  = "gesture_data_v5.pkl"

GESTURES = ["MOVE", "GRAB", "POUR", "RELEASE", "SHAKE"]
GESTURE_INSTRUCTIONS = {
    "MOVE":    "손을 활짝 펴세요 (보자기)",
    "GRAB":    "주먹을 쥐세요",
    "POUR":    "엄지만 펴세요",
    "RELEASE": "엄지 + 검지를 펴세요",
    "SHAKE":   "엄지 + 새끼를 펴세요",
}

# mc = MyCobot('192.168.0.20', 9000); time.sleep(1)

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

def landmarks_to_features(landmarks):
    wrist = landmarks[0]
    coords = []
    for lm in landmarks:
        coords.append(lm.x - wrist.x)
        coords.append(lm.y - wrist.y)
        coords.append(lm.z - wrist.z)
    for tip_idx in [4, 8, 12, 16, 20]:
        dx = landmarks[tip_idx].x - wrist.x
        dy = landmarks[tip_idx].y - wrist.y
        coords.append(math.sqrt(dx*dx + dy*dy))
    tilt = abs(math.degrees(math.atan2(abs(landmarks[9].x-wrist.x), abs(wrist.y-landmarks[9].y)+0.001)))
    coords.append(tilt)
    return coords

def get_tilt(lm):
    return abs(math.degrees(math.atan2(abs(lm[9].x-lm[0].x), abs(lm[0].y-lm[9].y)+0.001)))

def get_hand_size(lm):
    return math.sqrt((lm[0].x-lm[9].x)**2 + (lm[0].y-lm[9].y)**2)


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
    print("="*50)

    for gesture in GESTURES:
        instruction = GESTURE_INSTRUCTIONS[gesture]
        collected = 0; ready_start = None; waiting = True
        print(f"\n[{gesture}] {instruction}")

        while collected < SAMPLES_PER_GESTURE:
            ret, frame = cap.read()
            if not ret: break
            frame = cv2.flip(frame, 1)
            result = hands.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            h, w = frame.shape[:2]

            cv2.rectangle(frame, (0,0), (w,60), (50,50,50), -1)
            frame = put_text(frame, f"{gesture}  [{collected}/{SAMPLES_PER_GESTURE}]", (12,5), font_large, (255,255,255))
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
                            frame = put_text(frame, f"{int(remaining)+1}초 후 수집...", (w//2-80, h//2-20), font_mid, (255,255,0))
                        else: waiting = False; print("  수집 시작!")
                    else:
                        all_features.append(landmarks_to_features(hlm.landmark))
                        all_labels.append(gesture)
                        collected += 1
                        cv2.circle(frame, (w-40, 40), 15, (0,255,0), -1)
                        time.sleep(0.05)
            else: ready_start = None

            cv2.imshow("ChemiBot - Data Collection", frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                cap.release(); cv2.destroyAllWindows(); return None, None

        print(f"  {gesture} 완료! ({collected}개)")
        waiting = True; ready_start = None
        for _ in range(40):
            ret, frame = cap.read()
            if not ret: break
            frame = cv2.flip(frame, 1); h, w = frame.shape[:2]
            cv2.rectangle(frame, (0,0), (w,h), (30,30,30), -1)
            frame = put_text(frame, f"{gesture} 완료!", (w//2-60, h//2-40), font_large, (0,255,0))
            frame = put_text(frame, "다음 제스처 준비...", (w//2-80, h//2+10), font_mid, (200,200,200))
            cv2.imshow("ChemiBot - Data Collection", frame)
            cv2.waitKey(50)

    cap.release(); cv2.destroyAllWindows()
    with open(DATA_FILE, "wb") as f:
        pickle.dump({"features": all_features, "labels": all_labels}, f)
    print(f"\n데이터 저장: {DATA_FILE} ({len(all_labels)}개)")
    return all_features, all_labels


# ══════════════════════════════════════════════════════════════════
#  학습
# ══════════════════════════════════════════════════════════════════
def train_model(features, labels):
    X, y = np.array(features), np.array(labels)
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    print("\n모델 학습 중...")
    model = RandomForestClassifier(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)
    acc = accuracy_score(y_test, model.predict(X_test))
    print(f"정확도: {acc*100:.1f}%")
    print("\n클래스별 성능:")
    print(classification_report(y_test, model.predict(X_test)))
    with open(MODEL_FILE, "wb") as f: pickle.dump(model, f)
    print(f"모델 저장: {MODEL_FILE}")
    return model


# ══════════════════════════════════════════════════════════════════
#  좌표 변환 (XYZ)
# ══════════════════════════════════════════════════════════════════
def px2robot(px, py, hand_size):
    rx = round(ROBOT_X_MIN + (px/CAM_W) * (ROBOT_X_MAX-ROBOT_X_MIN), 1)
    ry = round(ROBOT_Y_MIN + (py/CAM_H) * (ROBOT_Y_MAX-ROBOT_Y_MIN), 1)
    rz = round(max(ROBOT_Z_MIN, min(ROBOT_Z_MAX, 400 - hand_size * 1500)), 1)
    return (rx, ry, rz)

class Smooth:
    def __init__(self): self.h=[]
    def update(self, x, y, z):
        self.h.append((x,y,z))
        if len(self.h) > SMOOTH_FRAMES: self.h.pop(0)
        return (round(sum(p[0] for p in self.h)/len(self.h),1),
                round(sum(p[1] for p in self.h)/len(self.h),1),
                round(sum(p[2] for p in self.h)/len(self.h),1))


# ══════════════════════════════════════════════════════════════════
#  로봇 제어
# ══════════════════════════════════════════════════════════════════
def robot_move(x,y,z): print(f"  [ROBOT] 이동 X:{x} Y:{y} Z:{z}")
# mc.send_coords([x, y, z, 0, 0, 0], ROBOT_SPEED, 1)

def robot_grip(): print("  [ROBOT] 잡기")
# mc.set_gripper_value(100, 20)

def robot_release(): print("  [ROBOT] 놓기")
# mc.set_gripper_value(0, 20)

def robot_pour(a): print(f"  [ROBOT] 붓기 {int(a)}도")
# coords = mc.get_coords()
# if coords: mc.send_coords([coords[0], coords[1], coords[2], 0, 0, a], 10, 1)

def robot_shake(x,y): print("  [ROBOT] 흔들기")
# for _ in range(3):
#     mc.send_coords([x-20, y, 120, 0, 0, 0], 30, 1); time.sleep(0.4)
#     mc.send_coords([x+20, y, 120, 0, 0, 0], 30, 1); time.sleep(0.4)

def robot_stop(): print("  [ROBOT] 정지")
# mc.stop()


# ══════════════════════════════════════════════════════════════════
#  실시간 인식
# ══════════════════════════════════════════════════════════════════
COLORS = {"MOVE":(76,175,80), "GRAB":(33,150,243), "RELEASE":(255,193,7),
          "POUR":(156,39,176), "SHAKE":(255,87,34), "STOP":(100,100,100), "UNKNOWN":(60,60,60)}
LABELS_KR = {"MOVE":"이동", "GRAB":"잡기", "RELEASE":"놓기",
             "POUR":"붓기", "SHAKE":"흔들기", "STOP":"정지", "UNKNOWN":"..."}

def run_realtime(model):
    cap = cv2.VideoCapture(CAMERA_ID)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAM_W)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAM_H)

    sm = Smooth()
    shake_history = []
    last_gesture = "UNKNOWN"
    last_gesture_time = 0
    last_robot_xyz = (0, 0, ROBOT_Z_DEFAULT)
    grabbed = False
    pred_history = []
    no_hand_frames = 0

    print("\n" + "="*50)
    print("  실시간 제스처 인식!")
    print("  보자기=이동 | 주먹=잡기 | 엄지=붓기")
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
        pour_angle = None
        robot_xyz = last_robot_xyz

        if result.multi_hand_landmarks:
            no_hand_frames = 0
            for hlm in result.multi_hand_landmarks:
                mp_draw.draw_landmarks(frame, hlm, mp_hands.HAND_CONNECTIONS)
                lm = hlm.landmark
                tilt = get_tilt(lm)
                hand_size = get_hand_size(lm)

                features = landmarks_to_features(lm)
                pred = model.predict([features])[0]
                proba = model.predict_proba([features])[0]
                confidence = max(proba) * 100

                pred_history.append(pred)
                if len(pred_history) > 5: pred_history.pop(0)
                from collections import Counter
                gesture = Counter(pred_history).most_common(1)[0][0]

                px, py = int(lm[0].x*CAM_W), int(lm[0].y*CAM_H)
                now = time.time()

                if gesture == "MOVE":
                    rx, ry, rz = px2robot(px, py, hand_size)
                    robot_xyz = sm.update(rx, ry, rz)
                    last_robot_xyz = robot_xyz
                    robot_move(*robot_xyz)

                elif gesture == "GRAB":
                    if last_gesture != "GRAB": last_gesture_time = now
                    elif now - last_gesture_time > GESTURE_HOLD_TIME and not grabbed:
                        robot_grip(); grabbed = True

                elif gesture == "RELEASE":
                    if last_gesture != "RELEASE": last_gesture_time = now
                    elif now - last_gesture_time > GESTURE_HOLD_TIME and grabbed:
                        robot_release(); grabbed = False

                elif gesture == "POUR":
                    pour_angle = max(0, min(90, tilt)) if tilt else 45
                    robot_pour(pour_angle)

                elif gesture == "SHAKE":
                    if last_gesture != "SHAKE": last_gesture_time = now
                    elif now - last_gesture_time > GESTURE_HOLD_TIME:
                        robot_shake(last_robot_xyz[0], last_robot_xyz[1])

                last_gesture = gesture
        else:
            no_hand_frames += 1
            if no_hand_frames > 10:
                gesture = "STOP"
                if last_gesture != "STOP":
                    robot_stop(); last_gesture = "STOP"
                pred_history.clear()

        # ── UI ──
        color = COLORS.get(gesture, (60,60,60))
        cv2.rectangle(frame, (0,0), (w,54), color, -1)
        label = LABELS_KR.get(gesture, "...")
        conf_text = f"  ({confidence:.0f}%)" if confidence > 0 else ""
        if USE_PIL:
            frame = put_text(frame, label + conf_text, (12,8), font_large, (255,255,255))
        else:
            cv2.putText(frame, f"{gesture} {conf_text}", (15,38), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255,255,255), 2)

        # XYZ 좌표
        cv2.putText(frame, f"Robot: X={robot_xyz[0]}  Y={robot_xyz[1]}  Z={robot_xyz[2]} mm",
                   (10,h-45), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200,200,200), 1)

        # 기울기
        if tilt is not None:
            bc = (156,39,176) if tilt > POUR_ANGLE_THRESHOLD else (200,200,200)
            cv2.putText(frame, f"Tilt: {int(tilt)} deg", (10,h-22), cv2.FONT_HERSHEY_SIMPLEX, 0.5, bc, 1)
            bw = int(tilt/90*200)
            cv2.rectangle(frame, (130,h-30), (130+bw,h-18), bc, -1)
            cv2.rectangle(frame, (130,h-30), (330,h-18), (100,100,100), 1)

        # 붓기 각도
        if gesture == "POUR" and pour_angle is not None:
            if USE_PIL:
                frame = put_text(frame, f"붓기 각도: {int(pour_angle)}도", (10,h-90), font_small, (200,150,255))
            else:
                cv2.putText(frame, f"Pour: {int(pour_angle)} deg", (10,h-65), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200,150,255), 1)

        cv2.putText(frame, "Q: Quit", (w-80,h-10), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (150,150,150), 1)
        cv2.imshow("ChemiBot - Gesture Control", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'): break

    cap.release(); cv2.destroyAllWindows()


# ══════════════════════════════════════════════════════════════════
#  메인
# ══════════════════════════════════════════════════════════════════
def main():
    print("="*50)
    print("  ChemiBot v5 — 손동작 제어 (XYZ)")
    print("  이동=보자기 | 잡기=주먹 | 붓기=엄지")
    print("  놓기=엄지+검지 | 흔들기=엄지+새끼")
    print("="*50)

    model = None
    if os.path.exists(MODEL_FILE):
        print(f"\n기존 모델 발견: {MODEL_FILE}")
        choice = input("기존 모델 사용? (y/n): ").strip().lower()
        if choice == 'y':
            with open(MODEL_FILE, "rb") as f: model = pickle.load(f)
            print("모델 로드 완료!")

    if model is None:
        print(f"\n[1단계] 데이터 수집 (5개 x {SAMPLES_PER_GESTURE}개)")
        features, labels = collect_data()
        if features is None: return
        print(f"\n[2단계] 학습 ({len(labels)}개)")
        model = train_model(features, labels)

    print("\n[3단계] 실시간 인식")
    run_realtime(model)

if __name__ == '__main__':
    main()