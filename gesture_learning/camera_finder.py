"""
카메라 매핑 헬퍼.

각 PC 마다 다른 카메라 환경을 코드 수정 없이 처리하기 위한 모듈.
같은 폴더의 camera_map.json 을 읽고, DirectShow 장치 목록에서
키워드 매칭으로 OpenCV 인덱스를 자동으로 찾아준다.

camera_map.json 형식 (예시):
{
  "face":    "asd",        # 얼굴 트래킹 카메라의 이름 일부
  "lab":     "Logitech",   # 실험실 카메라의 이름 일부
  "gesture": "HD Webcam"   # 손/제스처 카메라의 이름 일부
}

사용:
    from camera_finder import get_camera_index
    cam_idx = get_camera_index("face", fallback=1)

진단:
    python camera_finder.py
    → 현재 연결된 모든 카메라의 인덱스와 이름 출력
"""
import json
import os
import sys

_DEVICES_CACHE = None
_MAP_CACHE = None


def _list_devices():
    """OpenCV 인덱스 순서대로 DirectShow 카메라 이름 목록 반환."""
    global _DEVICES_CACHE
    if _DEVICES_CACHE is not None:
        return _DEVICES_CACHE

    try:
        from pygrabber.dshow_graph import FilterGraph
        _DEVICES_CACHE = FilterGraph().get_input_devices()
    except ImportError:
        print("[WARN] pygrabber 미설치 — 카메라 이름 매칭 불가", flush=True)
        print("       해결: pip install pygrabber", flush=True)
        _DEVICES_CACHE = []
    except Exception as e:
        print(f"[WARN] 카메라 목록 조회 실패: {e}", flush=True)
        _DEVICES_CACHE = []

    return _DEVICES_CACHE


def _load_map():
    """이 파일 옆의 camera_map.json 을 읽어 캐시. 없으면 빈 dict."""
    global _MAP_CACHE
    if _MAP_CACHE is not None:
        return _MAP_CACHE

    here = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(here, "camera_map.json")

    if not os.path.exists(path):
        print(f"[INFO] camera_map.json 없음 → 카메라 매핑 비활성화", flush=True)
        print(f"       위치: {path}", flush=True)
        print(f"       camera_map.example.json 을 복사해서 만드세요.", flush=True)
        _MAP_CACHE = {}
        return _MAP_CACHE

    try:
        with open(path, encoding="utf-8") as f:
            _MAP_CACHE = json.load(f)
        # _comment 같은 메타 키 제거 (실제 매핑만 남김)
        _MAP_CACHE = {k: v for k, v in _MAP_CACHE.items() if not k.startswith("_")}
    except Exception as e:
        print(f"[WARN] camera_map.json 읽기 실패: {e}", flush=True)
        _MAP_CACHE = {}
    return _MAP_CACHE


def get_camera_index(role, fallback=0):
    """
    용도(role) 에 해당하는 카메라의 OpenCV 인덱스를 반환.

    role: "face" | "lab" | "gesture" 등 camera_map.json 의 키.
    fallback: 매핑 안 됐거나 매칭 실패 시 사용할 인덱스 (코드 기본값).

    매칭 규칙:
        camera_map.json["role"] 값(키워드, 대소문자 무시)이
        DirectShow 카메라 이름 안에 포함된 첫 번째 인덱스 반환.
    """
    mp = _load_map()
    keyword = mp.get(role)
    if not keyword:
        print(f"[INFO] '{role}' 매핑 없음 → fallback 인덱스 {fallback} 사용", flush=True)
        return fallback

    devices = _list_devices()
    if not devices:
        print(f"[INFO] 카메라 목록 비어있음 → fallback 인덱스 {fallback} 사용", flush=True)
        return fallback

    for i, name in enumerate(devices):
        if keyword.lower() in name.lower():
            print(f"[INFO] '{role}' = '{keyword}' → 인덱스 {i} ({name})", flush=True)
            return i

    print(f"[WARN] '{role}' = '{keyword}' 매칭 실패 → fallback 인덱스 {fallback}", flush=True)
    print(f"       연결된 카메라: {devices}", flush=True)
    return fallback


def list_all_cameras():
    """진단용: 모든 카메라의 OpenCV 인덱스와 이름 출력."""
    devices = _list_devices()
    if not devices:
        print("연결된 카메라가 없거나 pygrabber 가 설치되지 않았습니다.")
        return []
    for i, name in enumerate(devices):
        print(f"  [{i}]  {name}")
    return devices


if __name__ == "__main__":
    # 단독 실행: 진단 모드
    print("=" * 60)
    print(" 카메라 진단")
    print("=" * 60)
    print("\n[1] 연결된 카메라:")
    devices = list_all_cameras()

    print("\n[2] camera_map.json 매핑 결과:")
    mp = _load_map()
    if not mp:
        print("  (매핑 없음)")
    else:
        for role in mp.keys():
            idx = get_camera_index(role, fallback=-1)
            if idx == -1:
                print(f"  '{role}': 매칭 실패")

    print("\n" + "=" * 60)
