"""
카메라 매핑 헬퍼.

각 PC 마다 다른 카메라 환경을 코드 수정 없이 처리하기 위한 모듈.
같은 폴더의 camera_map.json 을 읽고, DirectShow 장치 목록에서
키워드 매칭으로 OpenCV 인덱스를 자동으로 찾아준다.

또한 WPF 같은 다른 언어에서도 사용할 수 있도록
camera_indices.json 을 자동으로 생성한다.

camera_map.json 형식 (예시):
{
  "face":    "asd",        # 얼굴 트래킹 카메라의 이름 일부
  "lab":     "Logitech",   # 실험실 카메라의 이름 일부
  "gesture": "HD Webcam",  # 손/제스처 카메라의 이름 일부
  "arm":     ""            # 로봇암 카메라 (없으면 빈 문자열 또는 키 제외)
}

생성되는 camera_indices.json (자동, gitignore):
{
  "face":    0,
  "lab":     1,
  "gesture": 2,
  "arm":     -1            # 매칭 실패 시 -1
}

사용 (Python):
    from camera_finder import get_camera_index
    cam_idx = get_camera_index("face", fallback=1)

사용 (WPF/C#):
    camera_indices.json 을 읽어서 키에 해당하는 인덱스 사용.

진단:
    python camera_finder.py
    → 카메라 목록 + 매핑 결과 + camera_indices.json 자동 갱신
"""
import json
import os
import sys

_DEVICES_CACHE = None
_MAP_CACHE = None

_HERE = os.path.dirname(os.path.abspath(__file__))
_MAP_PATH = os.path.join(_HERE, "camera_map.json")
_INDICES_PATH = os.path.join(_HERE, "camera_indices.json")


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
    """camera_map.json 을 읽어 캐시. 없으면 빈 dict."""
    global _MAP_CACHE
    if _MAP_CACHE is not None:
        return _MAP_CACHE

    if not os.path.exists(_MAP_PATH):
        print(f"[INFO] camera_map.json 없음 → 카메라 매핑 비활성화", flush=True)
        print(f"       위치: {_MAP_PATH}", flush=True)
        print(f"       camera_map.example.json 을 복사해서 만드세요.", flush=True)
        _MAP_CACHE = {}
        return _MAP_CACHE

    try:
        with open(_MAP_PATH, encoding="utf-8") as f:
            _MAP_CACHE = json.load(f)
        # _comment 같은 메타 키 제거
        _MAP_CACHE = {k: v for k, v in _MAP_CACHE.items() if not k.startswith("_")}
    except Exception as e:
        print(f"[WARN] camera_map.json 읽기 실패: {e}", flush=True)
        _MAP_CACHE = {}
    return _MAP_CACHE


def _find_index_for_keyword(keyword):
    """키워드와 매칭되는 카메라의 OpenCV 인덱스 반환. 없으면 -1."""
    if not keyword:
        return -1
    devices = _list_devices()
    for i, name in enumerate(devices):
        if keyword.lower() in name.lower():
            return i
    return -1


def get_camera_index(role, fallback=0):
    """
    용도(role) 에 해당하는 카메라의 OpenCV 인덱스를 반환.
    Python 스크립트에서 사용.
    """
    mp = _load_map()
    keyword = mp.get(role)
    if not keyword:
        print(f"[INFO] '{role}' 매핑 없음 → fallback 인덱스 {fallback} 사용", flush=True)
        return fallback

    idx = _find_index_for_keyword(keyword)
    if idx >= 0:
        devices = _list_devices()
        print(f"[INFO] '{role}' = '{keyword}' → 인덱스 {idx} ({devices[idx]})", flush=True)
        return idx

    devices = _list_devices()
    print(f"[WARN] '{role}' = '{keyword}' 매칭 실패 → fallback 인덱스 {fallback}", flush=True)
    print(f"       연결된 카메라: {devices}", flush=True)
    return fallback


def write_indices_file():
    """
    camera_map.json 의 모든 키를 매핑하여 camera_indices.json 생성.
    WPF 같은 외부 프로그램이 이걸 읽어서 사용.
    매핑 안 되는 항목은 -1.
    """
    mp = _load_map()
    result = {}
    for role, keyword in mp.items():
        idx = _find_index_for_keyword(keyword) if keyword else -1
        result[role] = idx

    try:
        with open(_INDICES_PATH, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(f"[OK] camera_indices.json 생성: {result}", flush=True)
        return True
    except Exception as e:
        print(f"[WARN] camera_indices.json 쓰기 실패: {e}", flush=True)
        return False


def list_all_cameras():
    """진단용: 모든 카메라의 OpenCV 인덱스와 이름 출력."""
    devices = _list_devices()
    if not devices:
        print("연결된 카메라가 없거나 pygrabber 가 설치되지 않았습니다.")
        return []
    for i, name in enumerate(devices):
        print(f"  [{i}]  {name}")
    return devices


# 이 모듈이 import 될 때 자동으로 camera_indices.json 도 갱신
# (WPF 가 항상 최신 매핑을 볼 수 있도록)
try:
    write_indices_file()
except Exception:
    pass


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

    print("\n[3] camera_indices.json 갱신:")
    write_indices_file()

    print("\n" + "=" * 60)