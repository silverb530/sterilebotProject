#!/usr/bin/env python3
# =============================================================
#  SterileBot - 2단계 구역 캘리브레이션
#  파일명: zone_calib.py
#
#  ▶ 사용법
#    1단계: 드래그로 큰 구역 박스 (A_TUBES, BEAKER 등)
#    2단계: 큰 구역 선택 후 세부 박스 (A시약, B시약 등)
#
#  ▶ 키
#    드래그    : 박스 그리기
#    Enter    : 이름 확정
#    Tab      : 선택된 구역의 세부 박스 등록 모드
#    ESC      : 취소 / 세부모드 종료
#    r        : 마지막 항목 삭제
#    s        : 저장 후 종료
# =============================================================

import cv2
import json
import os

CAMERA_INDEX = 2
SAVE_PATH    = "zone_data.json"

def main():
    print("=" * 55)
    print("  SterileBot - 2단계 구역 캘리브레이션")
    print("=" * 55)
    print("드래그: 박스  Enter: 이름확정  Tab: 세부등록")
    print("r: 삭제  s: 저장")
    print("=" * 55)

    zones = []
    if os.path.exists(SAVE_PATH):
        with open(SAVE_PATH, "r") as f:
            zones = json.load(f)
        print(f"[INFO] 기존 구역 로드: {len(zones)}개")

    cap = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_DSHOW)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    fw = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    fh = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    cv2.namedWindow("Zone Calib", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("Zone Calib", fw, fh)

    # 상태
    drawing     = False
    start_pt    = None
    current_pt  = None
    pending_box = None
    typing_name = ""
    is_typing   = False
    child_mode  = False   # 세부 박스 등록 모드
    selected_zone_idx = None  # 현재 세부 등록 중인 1단계 구역

    def on_mouse(event, x, y, flags, param):
        nonlocal drawing, start_pt, current_pt, pending_box, is_typing
        if is_typing:
            return
        if event == cv2.EVENT_LBUTTONDOWN:
            drawing    = True
            start_pt   = (x, y)
            current_pt = (x, y)
        elif event == cv2.EVENT_MOUSEMOVE:
            if drawing:
                current_pt = (x, y)
        elif event == cv2.EVENT_LBUTTONUP:
            if drawing:
                drawing    = False
                current_pt = (x, y)
                x1 = min(start_pt[0], current_pt[0])
                y1 = min(start_pt[1], current_pt[1])
                x2 = max(start_pt[0], current_pt[0])
                y2 = max(start_pt[1], current_pt[1])
                if abs(x2-x1) > 10 and abs(y2-y1) > 10:
                    pending_box = (x1, y1, x2, y2)
                    is_typing   = True

    cv2.setMouseCallback("Zone Calib", on_mouse)

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        display = frame.copy()
        h, w    = display.shape[:2]

        # 1단계 구역 표시
        for i, z in enumerate(zones):
            x1, y1, x2, y2 = z["x1"], z["y1"], z["x2"], z["y2"]
            is_selected = (child_mode and selected_zone_idx == i)
            color = (0, 220, 255) if is_selected else (0, 255, 157)
            thick = 3 if is_selected else 2
            cv2.rectangle(display, (x1,y1), (x2,y2), color, thick)
            cv2.putText(display, z["name"],
                        (x1+5, y1+25),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)

            # 세부 박스 표시
            for ch in z.get("children", []):
                cx1,cy1,cx2,cy2 = ch["x1"],ch["y1"],ch["x2"],ch["y2"]
                cv2.rectangle(display, (cx1,cy1), (cx2,cy2), (255,180,0), 2)
                cv2.putText(display, f"{ch['name']}({ch.get('slot','')})",
                            (cx1+3, cy1+20),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,180,0), 1)

        # 드래그 중 표시
        if drawing and start_pt and current_pt:
            x1 = min(start_pt[0], current_pt[0])
            y1 = min(start_pt[1], current_pt[1])
            x2 = max(start_pt[0], current_pt[0])
            y2 = max(start_pt[1], current_pt[1])
            cv2.rectangle(display, (x1,y1), (x2,y2), (0,200,255), 2)

        # 입력창
        if is_typing and pending_box:
            x1, y1, x2, y2 = pending_box
            cv2.rectangle(display, (x1,y1), (x2,y2), (0,200,255), 2)
            bx = w//2 - 280
            by = h//2 - 60

            cv2.rectangle(display, (bx,by), (bx+560,by+110), (30,30,30), -1)
            cv2.rectangle(display, (bx,by), (bx+560,by+110), (0,200,255), 2)

            if child_mode:
                cv2.putText(display, f"Child Name: {typing_name}_",
                            (bx+15, by+40),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255,255,255), 2)
                cv2.putText(display, "(e.g. A_reagent, B_reagent)",
                            (bx+15, by+70),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (180,180,180), 1)
                cv2.putText(display, "Enter=OK  ESC=Cancel",
                            (bx+15, by+95),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.55, (180,180,180), 1)
            else:
                cv2.putText(display, f"Zone Name: {typing_name}_",
                            (bx+15, by+45),
                            cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255,255,255), 2)
                cv2.putText(display, "Enter=OK  ESC=Cancel",
                            (bx+15, by+85),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (180,180,180), 1)

        else:
            if child_mode and selected_zone_idx is not None:
                zname = zones[selected_zone_idx]["name"]
                nch   = len(zones[selected_zone_idx].get("children", []))
                cv2.putText(display,
                            f"[Child Mode] {zname} ({nch}) | ESC=done r=del s=save",
                            (10, 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,220,255), 2)
            else:
                cv2.putText(display,
                            f"Drag=Zone | Tab=Child | r=del s=save ({len(zones)} zones)",
                            (10, 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0,255,255), 2)

        cv2.imshow("Zone Calib", display)
        key = cv2.waitKey(1) & 0xFF

        # 입력 모드
        if is_typing:
            if key == 13:  # Enter
                if typing_name:
                    if child_mode and selected_zone_idx is not None:
                        # 세부 박스 추가 (슬롯명은 별도 입력 안 하고 이름으로 대체)
                        x1, y1, x2, y2 = pending_box
                        if "children" not in zones[selected_zone_idx]:
                            zones[selected_zone_idx]["children"] = []
                        child_count = len(zones[selected_zone_idx]["children"])
                        # 슬롯은 자동으로 부모이름+번호
                        parent_name = zones[selected_zone_idx]["name"]
                        auto_slot   = f"{parent_name}_{child_count+1}"
                        zones[selected_zone_idx]["children"].append({
                            "name": typing_name,
                            "slot": auto_slot,
                            "x1": x1, "y1": y1,
                            "x2": x2, "y2": y2
                        })
                        print(f"[CALIB] 세부 추가: {typing_name} (slot={auto_slot})")
                    else:
                        x1, y1, x2, y2 = pending_box
                        zones.append({
                            "name": typing_name,
                            "x1": x1, "y1": y1,
                            "x2": x2, "y2": y2,
                            "children": []
                        })
                        print(f"[CALIB] 구역 추가: {typing_name}")
                is_typing   = False
                typing_name = ""
                pending_box = None

            elif key == 27:  # ESC
                is_typing   = False
                typing_name = ""
                pending_box = None

            elif key == 8:  # Backspace
                typing_name = typing_name[:-1]

            elif 32 <= key <= 126:
                typing_name += chr(key)

        else:
            if key == ord("s"):
                break

            elif key == 27:  # ESC → 세부모드 종료
                if child_mode:
                    child_mode        = False
                    selected_zone_idx = None
                    print("[CALIB] 세부 등록 완료")
                else:
                    break

            elif key == ord("r"):
                if child_mode and selected_zone_idx is not None:
                    children = zones[selected_zone_idx].get("children", [])
                    if children:
                        removed = children.pop()
                        print(f"[CALIB] 세부 삭제: {removed['name']}")
                else:
                    if zones:
                        removed = zones.pop()
                        print(f"[CALIB] 구역 삭제: {removed['name']}")

            elif key == 9:  # Tab → 세부 등록 모드
                if not child_mode and zones:
                    print("\n세부 등록할 구역 번호 선택:")
                    for i, z in enumerate(zones):
                        nch = len(z.get("children", []))
                        print(f"  {i}: {z['name']} (세부 {nch}개)")
                    # 마지막 구역 자동 선택
                    selected_zone_idx = len(zones) - 1
                    child_mode        = True
                    print(f"[CALIB] [{zones[selected_zone_idx]['name']}] 세부 등록 모드")
                    print("  드래그로 세부 박스 그리기 → Enter로 이름 확정")
                    print("  ESC → 완료")

    cap.release()
    cv2.destroyAllWindows()

    with open(SAVE_PATH, "w") as f:
        json.dump(zones, f, indent=2, ensure_ascii=False)
    print(f"\n[INFO] 저장 완료: {SAVE_PATH}")
    for z in zones:
        print(f"  {z['name']}: {len(z.get('children',[]))}개 세부구역")
        for ch in z.get("children", []):
            print(f"    {ch['name']} (slot={ch['slot']}): ({ch['x1']},{ch['y1']})→({ch['x2']},{ch['y2']})")


if __name__ == "__main__":
    main()