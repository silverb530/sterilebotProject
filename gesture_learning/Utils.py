#!/usr/bin/env python3
# =============================================================
#  SterileBot - 공통 유틸 함수
#  파일명: utils.py
#  용도  : calib.py, head_mouse.py에서 공통으로 사용
# =============================================================

import cv2
import numpy as np
import ctypes

# ────────────────────────────────────────────────
#  얼굴 방향 계산
# ────────────────────────────────────────────────
FACE_POINTS_IDX = [1, 2, 33, 263, 61, 291]
FACE_POINTS_3D  = np.array([
    (0.0,    0.0,    0.0),
    (0.0,   -330.0, -65.0),
    (-225.0,  170.0,-135.0),
    (225.0,   170.0,-135.0),
    (-150.0, -150.0,-125.0),
    (150.0,  -150.0,-125.0),
], dtype=np.float64)

def get_head_pose(landmarks, frame_w, frame_h):
    """얼굴 랜드마크로 yaw, pitch 계산"""
    points_2d = np.array([
        (int(landmarks[i].x * frame_w),
         int(landmarks[i].y * frame_h))
        for i in FACE_POINTS_IDX
    ], dtype=np.float64)

    focal_length = frame_w
    cam_matrix = np.array([
        [focal_length, 0,            frame_w / 2],
        [0,            focal_length, frame_h / 2],
        [0,            0,            1          ]
    ], dtype=np.float64)
    dist_coeffs = np.zeros((4, 1), dtype=np.float64)

    success, rot_vec, _ = cv2.solvePnP(
        FACE_POINTS_3D, points_2d,
        cam_matrix, dist_coeffs,
        flags=cv2.SOLVEPNP_ITERATIVE
    )
    if not success:
        return None, None
    rot_mat, _ = cv2.Rodrigues(rot_vec)
    angles, _, _, _, _, _ = cv2.RQDecomp3x3(rot_mat)
    return angles[1], angles[0]   # yaw, pitch

# ────────────────────────────────────────────────
#  변환 행렬 (캘리브레이션 결과)
# ────────────────────────────────────────────────
def compute_transform(calib_angles, calib_screen):
    """얼굴 각도 → 화면 좌표 변환 행렬 계산 (최소제곱법)"""
    A = np.array([[y, p, 1.0] for y, p in calib_angles], dtype=np.float64)
    B = np.array(calib_screen, dtype=np.float64)
    M, _, _, _ = np.linalg.lstsq(A, B, rcond=None)
    return M

def apply_transform(M, yaw, pitch):
    """각도 → 화면 좌표 변환"""
    result = np.array([yaw, pitch, 1.0]) @ M
    return float(result[0]), float(result[1])

# ────────────────────────────────────────────────
#  커서 제어 (ctypes)
# ────────────────────────────────────────────────
def mouse_move(x, y):
    """커서 위치 이동.
    SetCursorPos 사용 — mouse_event 와 달리 포그라운드 제약이 없어서
    WPF 등 다른 앱이 포그라운드일 때도 정상 동작.
    """
    ctypes.windll.user32.SetCursorPos(int(x), int(y))

def mouse_click():
    """왼쪽 클릭"""
    ctypes.windll.user32.mouse_event(0x0002, 0, 0, 0, 0)
    ctypes.windll.user32.mouse_event(0x0004, 0, 0, 0, 0)

def get_screen_size():
    """모니터 해상도 반환"""
    w = ctypes.windll.user32.GetSystemMetrics(0)
    h = ctypes.windll.user32.GetSystemMetrics(1)
    return w, h

# ────────────────────────────────────────────────
#  Tobii 스타일 형광 초록 커서
# ────────────────────────────────────────────────
def create_and_set_cursor():
    """Tobii 스타일 형광 초록 커서 적용"""
    try:
        from PIL import Image, ImageDraw

        size = 80
        img  = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        cx, cy = size // 2, size // 2

        r_outer = size // 2 - 4
        draw.ellipse(
            [cx-r_outer, cy-r_outer, cx+r_outer, cy+r_outer],
            fill=(0, 255, 157, 30),
            outline=(0, 255, 157, 180), width=2
        )
        r_inner = size // 2 - 18
        draw.ellipse(
            [cx-r_inner, cy-r_inner, cx+r_inner, cy+r_inner],
            fill=(0, 255, 157, 60),
            outline=(0, 255, 157, 230), width=2
        )
        draw.ellipse(
            [cx-5, cy-5, cx+5, cy+5],
            fill=(0, 255, 157, 255)
        )

        img_bgra = np.array(img.convert("RGBA"))
        img_bgra = img_bgra[:, :, [2, 1, 0, 3]]
        img_bgra = np.ascontiguousarray(img_bgra)
        h, w     = img_bgra.shape[:2]

        class BITMAPINFOHEADER(ctypes.Structure):
            _fields_ = [
                ("biSize",          ctypes.c_uint32),
                ("biWidth",         ctypes.c_int32),
                ("biHeight",        ctypes.c_int32),
                ("biPlanes",        ctypes.c_uint16),
                ("biBitCount",      ctypes.c_uint16),
                ("biCompression",   ctypes.c_uint32),
                ("biSizeImage",     ctypes.c_uint32),
                ("biXPelsPerMeter", ctypes.c_int32),
                ("biYPelsPerMeter", ctypes.c_int32),
                ("biClrUsed",       ctypes.c_uint32),
                ("biClrImportant",  ctypes.c_uint32),
            ]

        bmi               = BITMAPINFOHEADER()
        bmi.biSize        = ctypes.sizeof(BITMAPINFOHEADER)
        bmi.biWidth       = w
        bmi.biHeight      = -h
        bmi.biPlanes      = 1
        bmi.biBitCount    = 32
        bmi.biCompression = 0

        hdc       = ctypes.windll.user32.GetDC(0)
        ppvBits   = ctypes.c_void_p()
        hbm_color = ctypes.windll.gdi32.CreateDIBSection(
            hdc, ctypes.byref(bmi), 0,
            ctypes.byref(ppvBits), None, 0
        )
        ctypes.windll.user32.ReleaseDC(0, hdc)
        ctypes.memmove(ppvBits, img_bgra.tobytes(), img_bgra.nbytes)

        hbm_mask = ctypes.windll.gdi32.CreateBitmap(w, h, 1, 1, None)

        class ICONINFO(ctypes.Structure):
            _fields_ = [
                ("fIcon",    ctypes.c_bool),
                ("xHotspot", ctypes.c_uint32),
                ("yHotspot", ctypes.c_uint32),
                ("hbmMask",  ctypes.c_void_p),
                ("hbmColor", ctypes.c_void_p),
            ]

        ii          = ICONINFO()
        ii.fIcon    = False
        ii.xHotspot = cx
        ii.yHotspot = cy
        ii.hbmMask  = hbm_mask
        ii.hbmColor = hbm_color

        hcursor = ctypes.windll.user32.CreateIconIndirect(ctypes.byref(ii))
        ctypes.windll.gdi32.DeleteObject(hbm_color)
        ctypes.windll.gdi32.DeleteObject(hbm_mask)

        if hcursor:
            for cur_id in [32512, 32513, 32514, 32515, 32649]:
                ctypes.windll.user32.SetSystemCursor(
                    ctypes.windll.user32.CopyIcon(hcursor), cur_id)
            ctypes.windll.user32.DestroyIcon(hcursor)
            print("[INFO] 커서 적용 완료")
        else:
            print("[WARN] 커서 생성 실패")

    except ImportError:
        print("[WARN] Pillow 없음 → pip install Pillow")
    except Exception as e:
        print(f"[WARN] 커서 변경 실패: {e}")

def restore_cursor():
    """기본 커서 복원"""
    try:
        ctypes.windll.user32.SystemParametersInfoW(
            0x0057, 0, None, 0x01 | 0x02)
        print("[INFO] 기본 커서 복원됨")
    except Exception as e:
        print(f"[WARN] 커서 복원 실패: {e}")