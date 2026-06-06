#!/usr/bin/env python3
# =============================================================
#  SterileBot - 캘리브레이션
#  파일명: calib.py
#
#  ▶ 실행
#    python calib.py
#    python calib.py --name minju   (사용자 이름 지정)
#
#  ▶ 저장 위치
#    calib_data/default.npy         (이름 없을 때)
#    calib_data/minju.npy           (이름 지정 시)
#
#  ▶ 순서
#    1. 전체화면 캘리브레이션 창 표시
#    2. 빨간 점 위치를 바라보고 Space
#    3. 16개 완료 → 파일 저장 → 자동 종료
# =============================================================

import cv2
import numpy as np
import mediapipe as mp
import sys
import os
import argparse
import time
from collections import deque
from Utils import get_head_pose, compute_transform, get_screen_size

# ────────────────────────────────────────────────
#  설정값
# ────────────────────────────────────────────────
CAMERA_INDEX  = 1
CALIB_POINTS  = 16      # 4x4 격자
SAMPLE_COUNT  = 20      # 포인트당 샘플 수 (많을수록 정확)
PROCESS_EVERY = 2
SAVE_DIR      = "calib_data"

# ────────────────────────────────────────────────
#  캘리브레이션 포인트 생성 (4x4 격자)
# ────────────────────────────────────────────────
def make_calib_points(screen_w, screen_h):
    mx = int(screen_w * 0.05)
    my = int(screen_h * 0.05)
    xs = [mx,
          mx + (screen_w-2*mx)//3,
          mx + (screen_w-2*mx)*2//3,
          screen_w - mx]
    ys = [my,
          my + (screen_h-2*my)//3,
          my + (screen_h-2*my)*2//3,
          screen_h - my]
    return [(x, y) for y in ys for x in xs]

# ────────────────────────────────────────────────
#  main
# ────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", type=str, default="default",
                        help="사용자 이름 (저장 파일명)")
    args = parser.parse_args()

    save_path = os.path.join(SAVE_DIR, f"{args.name}.npy")
    os.makedirs(SAVE_DIR, exist_ok=True)

    print("=" * 55)
    print("  Head Mouse Calibration")
    print("=" * 55)
    print(f"사용자: {args.name}")
    print(f"저장 위치: {save_path}")
    print(f"포인트 수: {CALIB_POINTS}개")
    print("Space: 포인트 수집 / q: 종료")
    print("=" * 55)

    screen_w, screen_h = get_screen_size()

    cap = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_DSHOW)
    if not cap.isOpened():
        print(f"[ERROR] 웹캠 {CAMERA_INDEX} 열기 실패")
        sys.exit(1)

    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    frame_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    calib_points = make_calib_points(screen_w, screen_h)
    calib_angles = []
    calib_screen = []
    samples_buf  = []
    calib_idx    = 0
    collecting   = False
    frame_count  = 0
    yaw, pitch   = None, None

    # 전체화면 창
    cv2.namedWindow("Calibration", cv2.WND_PROP_FULLSCREEN)
    cv2.setWindowProperty("Calibration", cv2.WND_PROP_FULLSCREEN,
                          cv2.WINDOW_FULLSCREEN)

    mp_face_mesh = mp.solutions.face_mesh

    print(f"\n[CALIB] Point 1/{CALIB_POINTS}")
    print(f"[CALIB] 화면의 {calib_points[0]} 위치를 바라보고 Space\n")

    with mp_face_mesh.FaceMesh(
        max_num_faces=1,
        refine_landmarks=False,
        min_detection_confidence=0.7,
        min_tracking_confidence=0.7
    ) as face_mesh:

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            frame_count += 1
            frame = cv2.flip(frame, 1)

            if frame_count % PROCESS_EVERY == 0:
                rgb    = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                result = face_mesh.process(rgb)
                yaw, pitch = None, None
                if result.multi_face_landmarks:
                    lm = result.multi_face_landmarks[0].landmark
                    yaw, pitch = get_head_pose(lm, frame_w, frame_h)

            # 전체화면용 디스플레이
            display = cv2.resize(frame, (screen_w, screen_h))

            # 포인트 표시
            for i, (px, py) in enumerate(calib_points):
                if i == calib_idx:
                    # 현재 포인트: 빨간 큰 원 + 펄스 효과
                    t   = time.time()
                    r   = int(28 + 6 * abs(np.sin(t * 3)))
                    cv2.circle(display, (px, py), r+6,
                               (0, 0, 180, 100), 2)
                    cv2.circle(display, (px, py), r, (0, 0, 255), -1)
                    cv2.circle(display, (px, py), 10, (255,255,255), -1)
                    cv2.putText(display, str(i+1),
                                (px+38, py+8),
                                cv2.FONT_HERSHEY_SIMPLEX,
                                1.0, (0,0,255), 2)
                elif i < calib_idx:
                    cv2.circle(display, (px, py), 15, (0,200,80), -1)
                else:
                    cv2.circle(display, (px, py), 15, (80,80,80), -1)

            # 상태 텍스트
            if collecting and yaw is not None:
                samples_buf.append((yaw, pitch))
                pct = int(len(samples_buf) / SAMPLE_COUNT * 100)

                # 진행 바
                bw = 400
                bx = screen_w//2 - bw//2
                by = screen_h - 80
                cv2.rectangle(display, (bx, by), (bx+bw, by+20),
                              (60,60,60), -1)
                cv2.rectangle(display, (bx, by),
                              (bx+int(bw*pct/100), by+20),
                              (0,255,100), -1)
                cv2.putText(display,
                            f"Collecting {pct}%  ({len(samples_buf)}/{SAMPLE_COUNT})",
                            (bx, by-10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0,255,100), 2)

                if len(samples_buf) >= SAMPLE_COUNT:
                    avg_yaw   = np.mean([s[0] for s in samples_buf])
                    avg_pitch = np.mean([s[1] for s in samples_buf])
                    calib_angles.append((avg_yaw, avg_pitch))
                    calib_screen.append(calib_points[calib_idx])
                    samples_buf = []
                    collecting  = False
                    calib_idx  += 1
                    print(f"[CALIB] Point {calib_idx}/{CALIB_POINTS} 완료")

                    if calib_idx >= CALIB_POINTS:
                        # 변환 행렬 계산 후 저장
                        M = compute_transform(calib_angles, calib_screen)
                        np.save(save_path, {
                            "transform_M":  M,
                            "calib_angles": np.array(calib_angles),
                            "calib_screen": np.array(calib_screen),
                            "screen_w":     screen_w,
                            "screen_h":     screen_h,
                        })
                        print(f"\n[CALIB] 완료! 저장: {save_path}")
                        print(f"[CALIB] 이제 python head_mouse.py --name {args.name} 실행")

                        # 완료 화면 잠깐 표시
                        display[:] = (20, 40, 20)
                        cv2.putText(display, "Calibration Complete!",
                                    (screen_w//2 - 280, screen_h//2 - 30),
                                    cv2.FONT_HERSHEY_SIMPLEX,
                                    2.0, (0,255,100), 3)
                        cv2.putText(display,
                                    f"Saved: {save_path}",
                                    (screen_w//2 - 200, screen_h//2 + 40),
                                    cv2.FONT_HERSHEY_SIMPLEX,
                                    1.0, (200,200,200), 2)
                        cv2.imshow("Calibration", display)
                        cv2.waitKey(2000)
                        break
                    else:
                        print(f"\n[CALIB] Point {calib_idx+1}/{CALIB_POINTS}")
                        print(f"[CALIB] {calib_points[calib_idx]} 위치를 바라보고 Space\n")
            else:
                status = "Press SPACE" if yaw is not None else "No face detected"
                color  = (0,255,255) if yaw is not None else (0,80,255)
                cv2.putText(display,
                            f"Point {calib_idx+1}/{CALIB_POINTS}  {status}",
                            (30, 60),
                            cv2.FONT_HERSHEY_SIMPLEX, 1.2, color, 2)

            # EAR 없이 안내
            if yaw is not None:
                cv2.putText(display,
                            f"yaw:{yaw:.1f}  pitch:{pitch:.1f}",
                            (30, screen_h - 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7,
                            (180,180,180), 1)

            cv2.imshow("Calibration", display)

            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                print("[INFO] 캘리브레이션 취소")
                break
            elif key == ord(" ") and not collecting and yaw is not None:
                collecting  = True
                samples_buf = []
                print(f"[CALIB] 수집 시작... ({SAMPLE_COUNT}개)")

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()