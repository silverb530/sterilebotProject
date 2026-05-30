# =============================================================
#  SterileBot - robot_controller.py 의 RESET 확장 모듈 (v2)
#  파일명: robot_reset_ext.py
#
#  ▶ v2 변경
#    - 그리퍼 동작(close/open) 후 항상 /home 자동 추가
#    - return_held: 2단계 → 3단계
#    - return_tube: 4단계 → 6단계
# =============================================================

import time
import requests
from robot_controller import RobotController


# ─────────────────────────────────────────────
#  헬퍼
# ─────────────────────────────────────────────
def _wait_until_done_sync(self, label, timeout=30.0):
    """Pi /status busy=False 까지 폴링"""
    time.sleep(0.5)
    t0 = time.time()
    while time.time() - t0 < timeout:
        data = self._get_silent("/status")
        if not data.get("busy", True):
            return True
        time.sleep(0.3)
    print(f"[ROBOT] {label} 타임아웃")
    return False


def _get_silent(self, path):
    """폴링용 — 로그 없음"""
    if not self.connected:
        return {"ok": False}
    try:
        r = requests.get(f"{self.base}{path}", timeout=3)
        if r.status_code == 200:
            return r.json()
        return {"ok": False}
    except Exception:
        return {"ok": False}


# ─────────────────────────────────────────────
#  return_held: 잡은 것을 시약통 N 으로 놓고 home 복귀 (3단계)
# ─────────────────────────────────────────────
def return_held(self, tube_num, sync=True, step_callback=None):
    """
    잡고 있는 tube → 시약통 N 으로 놓기 → home
      1) /pickup_move/N   시약통 N 위치로 이동 (잡은 채로)
      2) /grip/open       그리퍼 열기 = 놓기
      3) /home            홈 복귀
    """
    if not self.connected:
        print("[ROBOT] 미연결 — return_held 스킵")
        return False

    def proceed(label):
        if step_callback is None:
            return True
        return step_callback(label)

    label = f"리셋(잡힘) → tube_{tube_num}"
    self.playing = True
    self.current_action = label

    try:
        # 1) 시약통 위치로 이동
        if not proceed(f"/pickup_move/{tube_num}"):
            return False
        r = self._get(f"/pickup_move/{tube_num}")
        if not r.get("ok"):
            print(f"[ROBOT] return_held 실패: /pickup_move/{tube_num}")
            return False
        if sync and not self._wait_until_done_sync(f"시약통 {tube_num} 이동"):
            return False

        # 2) 그리퍼 열기 (놓기)
        if not proceed("/grip/open"):
            return False
        self._get("/grip/open")
        self.gripper_closed = False
        time.sleep(0.5)

        # 3) 홈 복귀
        if not proceed("/home"):
            return False
        self._get("/home")
        if sync and not self._wait_until_done_sync("home"):
            return False

        return True
    finally:
        self.playing = False
        self.current_action = ""


# ─────────────────────────────────────────────
#  return_tube: 슬롯에서 집어 시약통 N 으로 복귀 (6단계)
# ─────────────────────────────────────────────
def return_tube(self, slot, tube_num, sync=True, step_callback=None):
    """
    슬롯 → 시약통 N 으로 복귀 (잡기 후 home, 놓기 후 home 포함)
      1) /drop/slot       슬롯 위치로 이동
      2) /grip/close      그리퍼 닫기 = 잡기
      3) /home            홈 복귀 (잡은 채로)
      4) /pickup_move/N   시약통 N 위치로 이동
      5) /grip/open       그리퍼 열기 = 놓기
      6) /home            홈 복귀
    """
    if not self.connected:
        print("[ROBOT] 미연결 — return_tube 스킵")
        return False

    def proceed(label):
        if step_callback is None:
            return True
        return step_callback(label)

    label = f"리셋 {slot} → tube_{tube_num}"
    self.playing = True
    self.current_action = label

    try:
        # 1) 슬롯 위치로 이동
        if not proceed(f"/drop/{slot}"):
            return False
        r = self._get(f"/drop/{slot}")
        if not r.get("ok"):
            print(f"[ROBOT] return_tube 실패: /drop/{slot}")
            return False
        if sync and not self._wait_until_done_sync(f"{slot} 이동"):
            return False

        # 2) 그리퍼 닫기 (잡기)
        if not proceed("/grip/close"):
            return False
        self._get("/grip/close")
        self.gripper_closed = True
        time.sleep(0.6)

        # 3) 홈 복귀 (잡은 채로)
        if not proceed("/home"):
            return False
        self._get("/home")
        if sync and not self._wait_until_done_sync("home (잡은 채)"):
            return False

        # 4) 시약통 위치로 이동
        if not proceed(f"/pickup_move/{tube_num}"):
            return False
        r = self._get(f"/pickup_move/{tube_num}")
        if not r.get("ok"):
            print(f"[ROBOT] return_tube 실패: /pickup_move/{tube_num}")
            return False
        if sync and not self._wait_until_done_sync(f"시약통 {tube_num} 이동"):
            return False

        # 5) 그리퍼 열기 (놓기)
        if not proceed("/grip/open"):
            return False
        self._get("/grip/open")
        self.gripper_closed = False
        time.sleep(0.5)

        # 6) 홈 복귀
        if not proceed("/home"):
            return False
        self._get("/home")
        if sync and not self._wait_until_done_sync("home"):
            return False

        return True
    finally:
        self.playing = False
        self.current_action = ""


# ─────────────────────────────────────────────
#  monkey patch
# ─────────────────────────────────────────────
RobotController._wait_until_done_sync = _wait_until_done_sync
RobotController._get_silent            = _get_silent
RobotController.return_held            = return_held
RobotController.return_tube            = return_tube

print("[robot_reset_ext v2] RESET 메서드 추가 (각 그리퍼 동작 후 home 자동 복귀)")