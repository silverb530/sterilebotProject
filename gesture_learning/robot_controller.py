"""
ChemiBot Windows — 라즈베리파이 HTTP 서버로 로봇 제어 v2
Pi에서 sterilebot_server.py 먼저 실행 필요
"""
import requests
import threading
import time

class RobotController:
    def __init__(self, ip="192.168.0.32", port=5001):
        self.base    = f"http://{ip}:{port}"
        self.connected   = False
        self.playing     = False
        self.current_action = ""
        self.gripper_closed = False
        self._try_connect()

    def _try_connect(self):
        try:
            r = requests.get(f"{self.base}/status", timeout=3)
            if r.status_code == 200:
                self.connected = True
                data = r.json()
                print(f"[ROBOT] 연결 성공 ({self.base})")
                print(f"[ROBOT] 집기: {data.get('pickups')} / 꽂기: {data.get('drops')}")
                print(f"[ROBOT] 붓기 슬롯: {data.get('lifts')}")
        except Exception as e:
            print(f"[ROBOT] 연결 실패: {e}")

    def _get(self, path):
        if not self.connected:
            print(f"[ROBOT] 미연결 — {path} 스킵")
            return {"ok": False}
        try:
            r = requests.get(f"{self.base}{path}", timeout=10)
            return r.json()
        except Exception as e:
            print(f"[ROBOT] 요청 실패 {path}: {e}")
            return {"ok": False}

    def _poll_until_done(self, label):
        self.playing = True
        self.current_action = label
        time.sleep(1.0)
        while True:
            data = self._get("/status")
            if not data.get("busy", True):
                break
            time.sleep(0.5)
        self.playing = False
        self.current_action = ""

    def _start(self, path, label):
        r = self._get(path)
        if r.get("ok"):
            threading.Thread(target=self._poll_until_done,
                             args=(label,), daemon=True).start()
        return r.get("ok", False)

    # ── 기본 ──
    def go_home(self):
        return self._start("/home", "홈 복귀")

    def go_home_lift(self):
        """수평 자세 유지 홈 복귀"""
        return self._start("/home_lift", "수평 홈 복귀")

    def grip_close(self):
        self.gripper_closed = True
        self._get("/grip/close")

    def grip_open(self):
        self.gripper_closed = False
        self._get("/grip/open")

    def stop(self):
        self.playing = False
        self.current_action = "정지"
        try:
            self._get("/stop")
        except:
            pass
        print("[ROBOT] 정지")

    # ── 집기 ──
    def pickup_lift_move(self, slot):
        """수평 집기 위치 이동 (grip 직전 대기)"""
        return self._start(f"/pickup_lift_move/{slot.upper()}", f"{slot} 수평 이동")

    def side_drop_move(self, slot):
        """수평 꽂기 위치 이동 (open 직전 대기)"""
        return self._start(f"/side_drop_move/{slot.upper()}", f"{slot} 수평 꽂기 이동")

    def side_drop_release(self):
        """수평 꽂기 — 그리퍼 열기 + 복귀"""
        return self._start("/side_drop_release", "수평 놓기")

    def pickup_lift(self, slot):
        """슬롯에서 수평 집기 (lift_pickups.json 사용)"""
        return self._start(f"/pickup_lift/{slot.upper()}", f"{slot} 수평 집기")

    def pickup_move(self, tube_num):
        """튜브 위치까지 이동 (grip 이벤트 직전 대기)"""
        return self._start(f"/pickup_move/{tube_num}", f"tube_{tube_num} 이동")

    def pickup_grip(self):
        """그리퍼 닫기 + 저장된 복귀 경로 재생 (수직 홈)"""
        return self._start("/pickup_grip", "잡기+복귀")

    def pickup_grip_lift(self):
        """그리퍼 닫기 + 저장된 복귀 경로 재생 (수평 홈)"""
        return self._start("/pickup_grip_lift", "잡기+수평복귀")

    def pickup_tube(self, tube_num):
        """집기 단순 호출 (구버전 호환)"""
        return self.pickup_move(tube_num)

    # ── 꽂기 ──
    def side_drop(self, slot):
        """슬롯에 옆면 꽂기 (붓기 후 사용)"""
        return self._start(f"/side_drop/{slot.upper()}", f"{slot} 옆면 꽂기")

    def drop_move(self, slot):
        """슬롯 위치까지 이동 (open 이벤트 직전 대기)"""
        return self._start(f"/drop_move/{slot.upper()}", f"{slot} 꽂기 이동")

    def drop_release(self):
        """그리퍼 열기 + 복귀"""
        return self._start("/drop_release", "놓기 + 복귀")

    def drop_tube(self, slot):
        """슬롯에 꽂기 (A1~B4)"""
        return self._start(f"/drop/{slot.upper()}", f"{slot} 꽂기")

    # ── 붓기 ──
    def beaker_move(self):
        """비커 위치까지 이동 (붓기 직전 대기)"""
        return self._start("/beaker_move", "비커 이동")

    def beaker_pour(self):
        """실제 붓기 동작"""
        return self._start("/beaker_pour", "붓기")

    def pour_only(self):
        """비커에 붓기만 (이미 시험관 잡고 있을 때)"""
        return self._start("/pour_only", "비커 붓기")

    def pour(self, slot):
        """
        붓기 전체 시퀀스:
        ① 슬롯 옆면 집기 + 붓기용 영점
        ② 비커 붓기 + 붓기용 영점 복귀
        ③ 원래 슬롯 옆면 꽂기
        """
        return self._start(f"/pour/{slot.upper()}", f"{slot} 붓기")

    # ── 섞기 ──
    def stir(self):
        """막대기 집기 → 섞기 → 막대기 내려놓기 (전체 자동)"""
        return self._start("/stir", "섞기")

    def stir_move(self):
        """막대 앞까지 이동 (GRAB 대기)"""
        return self._start("/stir_move", "막대 이동")

    def stir_grip(self):
        """막대 잡기 + 홈 복귀"""
        return self._start("/stir_grip", "막대 잡기")

    def stir_beaker_move(self):
        """비커 위치로 이동 (SHAKE 대기)"""
        return self._start("/stir_beaker_move", "비커 위치 이동")

    def stir_do(self):
        """섞기 동작 + 홈 복귀"""
        return self._start("/stir_do", "섞기 동작")

    def stir_drop_move(self):
        """막대 원위치로 이동 (RELEASE 대기)"""
        return self._start("/stir_drop_move", "막대 원위치 이동")

    def stir_drop_release(self):
        """막대 놓기 + 홈 복귀"""
        return self._start("/stir_drop_release", "막대 놓기")

    # ── 리셋 ──
    def reset(self):
        """action_log 역순으로 시험관 원래 위치 복구"""
        return self._start("/reset", "리셋")

    # ── 상태 ──
    def get_status(self):
        return {
            "connected": self.connected,
            "playing":   self.playing,
            "action":    self.current_action,
            "gripper":   "닫힘" if self.gripper_closed else "열림",
        }