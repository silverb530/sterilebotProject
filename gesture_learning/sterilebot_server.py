"""
SterileBot HTTP 서버 v2 — tube_transport.py 최신 버전 기반
엔드포인트:
  /status
  /home
  /pickup_move/<tube_num>        집기 위치 이동 (grip 이벤트 직전 대기)
  /pickup_grip                   그리퍼 닫기 + 저장된 복귀 경로 재생
  /drop/<slot>                   꽂기 (A1~B4)
  /pour/<slot>                   붓기 전체 시퀀스 (옆면집기→붓기→꽂기)
  /stir                          섞기 전체 시퀀스
  /reset                         리셋 (action_log 역순 복구)
  /grip/open
  /grip/close
"""
from http.server import HTTPServer, BaseHTTPRequestHandler
import json, threading, os, time

from tube_transport import (
    load_config, replay_trajectory, go_home, go_home_lift,
    gripper_open, gripper_close,
    downsample, send_safe, TIME_SCALE, REPLAY_SAMP,
    run_pour_full, run_reset, run_lift,
    mc, WAIT_STOP, WAIT_GRIP, GRIP_VALUE, SPEED_GRIP
)

# ── JSON 로드 ──
def _load(path):
    try:
        return json.load(open(path)) if os.path.exists(path) else {}
    except:
        return {}

load_config()
_pickups     = _load("tube_pickups.json")
_drops       = _load("tube_drops.json")
_lifts       = _load("lift_pickups.json")
_side_drops  = _load("side_drops.json")
_pour        = _load("pour_trajectory.json")
_stir_pick   = _load("stir_pickup.json")
_stir_action = _load("stir_action.json")
_stir_drop   = _load("stir_drop.json")
_reset_picks = _load("reset_pickups.json")
_reset_drops = _load("reset_drops.json")

print(f"[로드] 집기: {list(_pickups.keys())}")
print(f"[로드] 꽂기: {list(_drops.keys())}")
print(f"[로드] 붓기 슬롯: {list(_lifts.keys())}")

_busy = False
_stop_flag = False  # 긴급 정지 플래그
_grip_state = {"tube_num": None, "remaining_traj": []}
_drop_state = {"slot": None, "remaining_traj": []}  # 꽂기 위치 도달 후 대기

def run_async(fn, *args):
    global _busy, _stop_flag
    _busy = True
    _stop_flag = False  # 새 동작 시작 시 정지 플래그 해제
    try:    fn(*args)
    except Exception as e: print(f"[ERROR] {e}")
    finally: _busy = False

# ── 집기 위치까지만 이동 (grip 이벤트 직전 대기) ──
def _pickup_move(tube_num):
    key  = f"tube_{tube_num}"
    data = _pickups.get(key)
    if not data:
        print(f"[ERROR] {key} 없음"); return

    raw    = data["trajectory"]
    evts   = data["events"]
    samp   = data.get("replay_samp", REPLAY_SAMP)
    t_sc   = data.get("time_scale",  TIME_SCALE)
    g_val  = data.get("grip_value",  GRIP_VALUE)
    traj   = downsample(raw, samp)

    grip_t = next((ev["t"] for ev in evts if ev["action"] == "close"), None)

    mc.stop(); time.sleep(WAIT_STOP)
    gripper_open()

    # J6 먼저 정렬 → 첫 위치
    first = traj[0]["angles"]
    mc.send_angle(6, first[5], 15); time.sleep(2.5)
    send_safe(first, 15);           time.sleep(4.0)

    last_t = 0; remaining = []
    for pt in traj:
        if _stop_flag: break
        cur_t = pt["t"]
        if grip_t and cur_t >= grip_t - 0.2:
            remaining.append(pt)
            continue
        wait = max(0.08, (cur_t - last_t) * t_sc)
        last_t = cur_t
        send_safe(pt["angles"]); time.sleep(wait)

    # 남은 경로 + grip_value 저장
    _grip_state["tube_num"]       = tube_num
    _grip_state["remaining_traj"] = remaining
    _grip_state["grip_value"]     = g_val
    print(f"[서버] tube_{tube_num} 위치 도달 (잔여 {len(remaining)}프레임)")

# ── 잡기 + 저장된 복귀 경로 재생 ──
def _pickup_grip():
    g_val     = _grip_state.get("grip_value", GRIP_VALUE)
    remaining = _grip_state["remaining_traj"]

    mc.set_gripper_value(g_val, SPEED_GRIP); time.sleep(WAIT_GRIP)

    if remaining:
        print(f"[서버] 복귀 경로 재생 ({len(remaining)}프레임)")
        last_t = remaining[0]["t"]
        for pt in remaining:
            if _stop_flag: break
            cur_t = pt["t"]
            wait  = max(0.08, (cur_t - last_t) * TIME_SCALE)
            last_t = cur_t
            send_safe(pt["angles"]); time.sleep(wait)
    else:
        go_home()

    _grip_state["tube_num"]       = None
    _grip_state["remaining_traj"] = []
    print("[서버] 잡기 + 복귀 완료")

# ── 꽂기 위치까지만 이동 (open 이벤트 직전 대기) ──
def _drop_move(slot):
    data = _drops.get(slot)
    if not data:
        print(f"[ERROR] {slot} 꽂기 데이터 없음"); return

    raw  = data["trajectory"]
    evts = data["events"]
    traj = downsample(raw, REPLAY_SAMP)

    # open 이벤트 시간 찾기
    open_t = next((ev["t"] for ev in evts if ev["action"] == "open"), None)

    mc.stop(); time.sleep(WAIT_STOP)

    # 첫 위치로 이동
    send_safe(traj[0]["angles"], 15); time.sleep(4.0)

    last_t = 0; remaining = []
    for pt in traj:
        if _stop_flag: break
        cur_t = pt["t"]
        if open_t and cur_t >= open_t - 0.2:
            remaining.append(pt)
            continue
        wait = max(0.08, (cur_t - last_t) * TIME_SCALE)
        last_t = cur_t
        send_safe(pt["angles"]); time.sleep(wait)

    _drop_state["slot"]           = slot
    _drop_state["remaining_traj"] = remaining
    print(f"[서버] {slot} 꽂기 위치 도달 — RELEASE 대기")

# ── 그리퍼 열기 + 복귀 ──
def _drop_release():
    gripper_open()
    time.sleep(0.5)
    remaining = _drop_state["remaining_traj"]
    if remaining:
        last_t = remaining[0]["t"]
        for pt in remaining:
            if _stop_flag: break
            cur_t = pt["t"]
            wait  = max(0.08, (cur_t - last_t) * TIME_SCALE)
            last_t = cur_t
            send_safe(pt["angles"]); time.sleep(wait)
    go_home()
    _drop_state["slot"]           = None
    _drop_state["remaining_traj"] = []
    print("[서버] 꽂기 + 복귀 완료")
_pour_remaining = []  # 붓기 나머지 경로

def _beaker_move():
    """비커 위치까지만 이동 (붓기 직전)"""
    if not _pour:
        print("[ERROR] 붓기 데이터 없음"); return
    traj = _pour.get("trajectory", _pour) if isinstance(_pour, dict) else _pour
    SPLIT_T = 7.5  # 이 시간까지만 이동

    send_safe(traj[0]["angles"], 15); time.sleep(4.0)
    last_t = 0
    global _pour_remaining
    _pour_remaining = []
    for pt in traj:
        if _stop_flag: break
        cur_t = pt["t"]
        if cur_t >= SPLIT_T:
            _pour_remaining.append(pt)
            continue
        wait = max(0.08, (cur_t - last_t) * TIME_SCALE)
        last_t = cur_t
        send_safe(pt["angles"]); time.sleep(wait)
    print(f"[서버] 비커 위치 도달 — POUR 대기 ({len(_pour_remaining)}프레임 남음)")

def _beaker_pour():
    """실제 붓기 동작 (POUR 제스처 후 실행)"""
    global _pour_remaining
    if not _pour_remaining:
        print("[ERROR] 비커 이동 먼저 필요"); return
    last_t = _pour_remaining[0]["t"]
    for pt in _pour_remaining:
        if _stop_flag: break
        wait = max(0.08, (pt["t"] - last_t) * TIME_SCALE)
        last_t = pt["t"]
        send_safe(pt["angles"]); time.sleep(wait)
    _pour_remaining = []
    go_home_lift()
    print("[서버] 붓기 완료")
_side_drop_state = {"slot": None, "remaining_traj": []}

def _pickup_lift_move(slot):
    data = _lifts.get(slot)
    if not data: print(f"[ERROR] {slot} lift 없음"); return
    if isinstance(data, dict) and "trajectory" in data:
        traj = downsample(data["trajectory"], REPLAY_SAMP)
        evts = data.get("events", [])
    else:
        traj = downsample(data, REPLAY_SAMP); evts = []
    grip_t = next((ev["t"] for ev in evts if ev["action"] == "close"), None)
    mc.stop(); time.sleep(WAIT_STOP)
    gripper_open()
    send_safe(traj[0]["angles"], 15); time.sleep(4.0)
    last_t = 0; remaining = []
    for pt in traj:
        if _stop_flag: break
        cur_t = pt["t"]
        if grip_t and cur_t >= grip_t - 0.2:
            remaining.append(pt); continue
        wait = max(0.08, (cur_t - last_t) * TIME_SCALE)
        last_t = cur_t
        send_safe(pt["angles"]); time.sleep(wait)
    _grip_state["tube_num"] = slot
    _grip_state["remaining_traj"] = remaining
    print(f"[서버] {slot} 수평 집기 위치 도달 — GRAB 대기")

def _side_drop_move(slot):
    data = _side_drops.get(slot)
    if not data: print(f"[ERROR] {slot} side_drop 없음"); return
    if isinstance(data, dict) and "trajectory" in data:
        traj = downsample(data["trajectory"], REPLAY_SAMP)
        evts = data.get("events", [])
    else:
        traj = downsample(data, REPLAY_SAMP); evts = []
    open_t = next((ev["t"] for ev in evts if ev["action"] == "open"), None)
    mc.stop(); time.sleep(WAIT_STOP)
    send_safe(traj[0]["angles"], 15); time.sleep(4.0)
    last_t = 0; remaining = []
    for pt in traj:
        if _stop_flag: break
        cur_t = pt["t"]
        if open_t and cur_t >= open_t - 0.2:
            remaining.append(pt); continue
        wait = max(0.08, (cur_t - last_t) * TIME_SCALE)
        last_t = cur_t
        send_safe(pt["angles"]); time.sleep(wait)
    _side_drop_state["slot"] = slot
    _side_drop_state["remaining_traj"] = remaining
    print(f"[서버] {slot} 수평 꽂기 위치 도달 — RELEASE 대기")

def _side_drop_release():
    gripper_open(); time.sleep(0.5)
    remaining = _side_drop_state["remaining_traj"]
    if remaining:
        last_t = remaining[0]["t"]
        for pt in remaining:
            if _stop_flag: break
            wait = max(0.08, (pt["t"] - last_t) * TIME_SCALE)
            last_t = pt["t"]
            send_safe(pt["angles"]); time.sleep(wait)
    go_home()
    _side_drop_state["slot"] = None
    _side_drop_state["remaining_traj"] = []
    print("[서버] 수평 꽂기 완료")

def _run_stir():
    if not _stir_pick or not _stir_action or not _stir_drop:
        print("[ERROR] 섞기 데이터 없음"); return
    replay_trajectory(_stir_pick,   "막대기 집기")
    replay_trajectory(_stir_action, "섞기 동작")
    replay_trajectory(_stir_drop,   "막대기 내려놓기")
    go_home()
    print("[서버] 섞기 완료")

# ── 단계별 섞기 ──
_stir_grip_state   = {"remaining_traj": [], "grip_value": GRIP_VALUE}
_stir_drop_state   = {"remaining_traj": []}
_stir_beaker_state = {"remaining_traj": []}  # beaker_move 후 섞기 remaining 전용

def _stir_move():
    """막대 앞까지 이동 (grip 이벤트 직전 대기) — GRAB 대기"""
    if not _stir_pick:
        print("[ERROR] stir_pickup.json 없음"); return
    raw    = _stir_pick["trajectory"]
    evts   = _stir_pick.get("events", [])
    g_val  = _stir_pick.get("grip_value", GRIP_VALUE)
    traj   = downsample(raw, REPLAY_SAMP)
    grip_t = next((ev["t"] for ev in evts if ev["action"] == "close"), None)

    mc.stop(); time.sleep(WAIT_STOP)
    gripper_open()

    first = traj[0]["angles"]
    mc.send_angle(6, first[5], 15); time.sleep(2.5)
    send_safe(first, 15);           time.sleep(4.0)

    last_t = 0; remaining = []
    for pt in traj:
        if _stop_flag: break
        cur_t = pt["t"]
        if grip_t and cur_t >= grip_t - 0.2:
            remaining.append(pt); continue
        wait = max(0.08, (cur_t - last_t) * TIME_SCALE)
        last_t = cur_t
        send_safe(pt["angles"]); time.sleep(wait)

    _stir_grip_state["remaining_traj"] = remaining
    _stir_grip_state["grip_value"]     = g_val
    print(f"[서버] 막대 위치 도달 — GRAB 대기 (잔여 {len(remaining)}프레임)")

def _stir_grip():
    """GRAB 시: 막대 잡기 + 홈 복귀"""
    g_val     = _stir_grip_state.get("grip_value", GRIP_VALUE)
    remaining = _stir_grip_state["remaining_traj"]

    mc.set_gripper_value(g_val, SPEED_GRIP); time.sleep(WAIT_GRIP)

    if remaining:
        last_t = remaining[0]["t"]
        for pt in remaining:
            if _stop_flag: break
            wait = max(0.08, (pt["t"] - last_t) * TIME_SCALE)
            last_t = pt["t"]
            send_safe(pt["angles"]); time.sleep(wait)
    else:
        go_home()

    _stir_grip_state["remaining_traj"] = []
    print("[서버] 막대 잡기 + 홈 복귀 완료")

def _stir_beaker_move():
    """Beaker Dwell 시: 비커 위치까지만 이동 — SHAKE 대기"""
    if not _stir_action:
        print("[ERROR] stir_action.json 없음"); return
    raw  = _stir_action["trajectory"] if isinstance(_stir_action, dict) and "trajectory" in _stir_action else _stir_action
    SPLIT_T = 5.4  # 비커 위 도달 후 멈추는 지점

    # downsample 전에 분리 (downsample 후 t값이 바뀔 수 있음)
    before    = [pt for pt in raw if pt["t"] < SPLIT_T]
    remaining = [pt for pt in raw if pt["t"] >= SPLIT_T]

    before_ds    = downsample(before,    REPLAY_SAMP)
    remaining_ds = downsample(remaining, REPLAY_SAMP)

    if not before_ds:
        print("[ERROR] 이동 구간 없음"); return

    send_safe(before_ds[0]["angles"], 15); time.sleep(4.0)
    last_t = 0
    for pt in before_ds:
        if _stop_flag: break
        wait = max(0.08, (pt["t"] - last_t) * TIME_SCALE)
        last_t = pt["t"]
        send_safe(pt["angles"]); time.sleep(wait)

    if _stop_flag:
        print("[서버] 긴급 정지 — 비커 이동 중단")
        return
    _stir_beaker_state["remaining_traj"] = remaining_ds
    print(f"[서버] 비커 위 도달 — SHAKE 대기 (잔여 {len(remaining_ds)}프레임)")

def _stir_do():
    """SHAKE 제스처 시: 섞기 동작 재생 + 홈 복귀 (수평 자세)"""
    remaining = _stir_beaker_state.get("remaining_traj", [])
    if remaining:
        last_t = remaining[0]["t"]
        for pt in remaining:
            if _stop_flag: break
            wait = max(0.08, (pt["t"] - last_t) * TIME_SCALE)
            last_t = pt["t"]
            send_safe(pt["angles"]); time.sleep(wait)
    go_home_lift()  # 수평 자세 유지 홈 복귀
    _stir_beaker_state["remaining_traj"] = []
    print("[서버] 섞기 완료 + 홈 복귀")

def _stir_drop_move():
    """막대 잡은 채로 원위치(stir_drop) 앞까지 이동 — RELEASE 대기"""
    if not _stir_drop:
        print("[ERROR] stir_drop.json 없음"); return
    raw    = _stir_drop["trajectory"] if isinstance(_stir_drop, dict) and "trajectory" in _stir_drop else _stir_drop
    evts   = _stir_drop.get("events", []) if isinstance(_stir_drop, dict) else []
    traj   = downsample(raw, REPLAY_SAMP)
    open_t = next((ev["t"] for ev in evts if ev["action"] == "open"), None)

    send_safe(traj[0]["angles"], 15); time.sleep(4.0)

    last_t = 0; remaining = []
    for pt in traj:
        if _stop_flag: break
        cur_t = pt["t"]
        if open_t and cur_t >= open_t - 0.2:
            remaining.append(pt); continue
        wait = max(0.08, (cur_t - last_t) * TIME_SCALE)
        last_t = cur_t
        send_safe(pt["angles"]); time.sleep(wait)

    _stir_drop_state["remaining_traj"] = remaining
    print(f"[서버] 막대 원위치 도달 — RELEASE 대기 (잔여 {len(remaining)}프레임)")

def _stir_drop_release():
    """RELEASE 시: 막대 놓기 + 홈 복귀"""
    gripper_open(); time.sleep(0.5)
    remaining = _stir_drop_state["remaining_traj"]
    if remaining:
        last_t = remaining[0]["t"]
        for pt in remaining:
            if _stop_flag: break
            wait = max(0.08, (pt["t"] - last_t) * TIME_SCALE)
            last_t = pt["t"]
            send_safe(pt["angles"]); time.sleep(wait)
    go_home()
    _stir_drop_state["remaining_traj"] = []
    print("[서버] 막대 내려놓기 + 홈 복귀 완료")

# ── HTTP 응답 헬퍼 ──
def respond(h, data, code=200):
    body = json.dumps(data).encode()
    h.send_response(code)
    h.send_header("Content-Type", "application/json")
    h.end_headers()
    h.wfile.write(body)

# ── 핸들러 ──
class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print(f"[HTTP] {args[0]}")

    def do_GET(self):
        p = self.path

        if p == "/status":
            respond(self, {
                "busy":       _busy,
                "positioned": _grip_state["tube_num"] is not None,
                "tube":       _grip_state["tube_num"],
                "pickups":    list(_pickups.keys()),
                "drops":      list(_drops.keys()),
                "lifts":      list(_lifts.keys()),
            })

        elif p == "/home":
            if _busy: respond(self, {"ok": False, "reason": "동작 중"}); return
            threading.Thread(target=run_async, args=(go_home,), daemon=True).start()
            respond(self, {"ok": True, "action": "홈"})

        elif p == "/stop":
            # 즉시 정지 — busy 체크 없이 강제 실행
            def _do_stop():
                global _busy, _stop_flag
                _stop_flag = True  # 모든 궤적 재생 루프 중단
                mc.stop()
                _busy = False
                print("[서버] 긴급 정지 실행")
            _do_stop()
            respond(self, {"ok": True, "action": "정지"})

        elif p.startswith("/pickup_lift_move/"):
            slot = p.split("/")[-1].upper()
            if _busy: respond(self, {"ok": False, "reason": "동작 중"}); return
            if slot not in _lifts: respond(self, {"ok": False, "reason": f"{slot} lift 없음"}); return
            threading.Thread(target=run_async, args=(_pickup_lift_move, slot), daemon=True).start()
            respond(self, {"ok": True, "action": f"{slot} 수평 이동"})

        elif p.startswith("/side_drop_move/"):
            slot = p.split("/")[-1].upper()
            if _busy: respond(self, {"ok": False, "reason": "동작 중"}); return
            if slot not in _side_drops: respond(self, {"ok": False, "reason": f"{slot} 없음"}); return
            threading.Thread(target=run_async, args=(_side_drop_move, slot), daemon=True).start()
            respond(self, {"ok": True, "action": f"{slot} 수평 꽂기 이동"})

        elif p == "/side_drop_release":
            if _busy: respond(self, {"ok": False, "reason": "동작 중"}); return
            if _side_drop_state["slot"] is None: respond(self, {"ok": False, "reason": "위치 미도달"}); return
            threading.Thread(target=run_async, args=(_side_drop_release,), daemon=True).start()
            respond(self, {"ok": True, "action": "수평 놓기"})

        elif p.startswith("/pickup_lift/"):
            slot = p.split("/")[-1].upper()
            if _busy: respond(self, {"ok": False, "reason": "동작 중"}); return
            if slot not in _lifts:
                respond(self, {"ok": False, "reason": f"{slot} lift 데이터 없음"}); return
            def _do_lift():
                replay_trajectory(_lifts[slot], f"{slot} 수평 집기")
                go_home_lift()
            threading.Thread(target=run_async, args=(_do_lift,), daemon=True).start()
            respond(self, {"ok": True, "action": f"{slot} 수평 집기"})

        elif p.startswith("/pickup_move/"):
            tube = int(p.split("/")[-1])
            if _busy: respond(self, {"ok": False, "reason": "동작 중"}); return
            if f"tube_{tube}" not in _pickups:
                respond(self, {"ok": False, "reason": f"tube_{tube} 없음"}); return
            threading.Thread(target=run_async, args=(_pickup_move, tube), daemon=True).start()
            respond(self, {"ok": True, "action": f"tube_{tube} 이동"})

        elif p == "/pickup_grip":
            if _busy: respond(self, {"ok": False, "reason": "동작 중"}); return
            if _grip_state["tube_num"] is None:
                respond(self, {"ok": False, "reason": "위치 미도달"}); return
            threading.Thread(target=run_async, args=(_pickup_grip,), daemon=True).start()
            respond(self, {"ok": True, "action": "잡기+복귀"})

        elif p.startswith("/side_drop/"):
            slot = p.split("/")[-1].upper()
            if _busy: respond(self, {"ok": False, "reason": "동작 중"}); return
            if slot not in _side_drops:
                respond(self, {"ok": False, "reason": f"{slot} 옆면 꽂기 없음"}); return
            threading.Thread(target=run_async,
                             args=(replay_trajectory, _side_drops[slot], f"{slot} 옆면 꽂기"),
                             daemon=True).start()
            respond(self, {"ok": True, "action": f"{slot} 옆면 꽂기"})

        elif p.startswith("/drop_move/"):
            slot = p.split("/")[-1].upper()
            if _busy: respond(self, {"ok": False, "reason": "동작 중"}); return
            if slot not in _drops:
                respond(self, {"ok": False, "reason": f"{slot} 없음"}); return
            threading.Thread(target=run_async, args=(_drop_move, slot), daemon=True).start()
            respond(self, {"ok": True, "action": f"{slot} 꽂기 이동"})

        elif p == "/drop_release":
            if _busy: respond(self, {"ok": False, "reason": "동작 중"}); return
            if _drop_state["slot"] is None:
                respond(self, {"ok": False, "reason": "꽂기 위치 미도달"}); return
            threading.Thread(target=run_async, args=(_drop_release,), daemon=True).start()
            respond(self, {"ok": True, "action": "놓기 + 복귀"})

        elif p.startswith("/drop/"):
            slot = p.split("/")[-1].upper()
            if _busy: respond(self, {"ok": False, "reason": "동작 중"}); return
            if slot not in _drops:
                respond(self, {"ok": False, "reason": f"{slot} 없음"}); return
            threading.Thread(target=run_async,
                             args=(replay_trajectory, _drops[slot], f"{slot} 꽂기"),
                             daemon=True).start()
            respond(self, {"ok": True, "action": f"{slot} 꽂기"})

        elif p == "/beaker_move":
            if _busy: respond(self, {"ok": False, "reason": "동작 중"}); return
            threading.Thread(target=run_async, args=(_beaker_move,), daemon=True).start()
            respond(self, {"ok": True, "action": "비커 이동"})

        elif p == "/beaker_pour":
            if _busy: respond(self, {"ok": False, "reason": "동작 중"}); return
            if not _pour_remaining:
                respond(self, {"ok": False, "reason": "비커 이동 먼저"}); return
            threading.Thread(target=run_async, args=(_beaker_pour,), daemon=True).start()
            respond(self, {"ok": True, "action": "붓기"})

        elif p == "/pour_only":
            if _busy: respond(self, {"ok": False, "reason": "동작 중"}); return
            if not _pour:
                respond(self, {"ok": False, "reason": "붓기 데이터 없음"}); return
            def _do_pour_only():
                replay_trajectory(_pour, "비커 붓기")
                import time; mc.stop(); time.sleep(1.0)
                go_home_lift()
            threading.Thread(target=run_async, args=(_do_pour_only,), daemon=True).start()
            respond(self, {"ok": True, "action": "비커 붓기"})

        elif p.startswith("/pour/"):
            slot = p.split("/")[-1].upper()
            if _busy: respond(self, {"ok": False, "reason": "동작 중"}); return
            threading.Thread(target=run_async,
                             args=(run_pour_full, _lifts, _side_drops, _pour, slot),
                             daemon=True).start()
            respond(self, {"ok": True, "action": f"{slot} 붓기"})

        elif p == "/stir":
            if _busy: respond(self, {"ok": False, "reason": "동작 중"}); return
            threading.Thread(target=run_async, args=(_run_stir,), daemon=True).start()
            respond(self, {"ok": True, "action": "섞기"})

        elif p == "/stir_move":
            if _busy: respond(self, {"ok": False, "reason": "동작 중"}); return
            def _stir_move_and_release():
                global _stop_flag, _busy
                _busy = True
                _stop_flag = False
                _stir_move()
                _busy = False  # 막대 위치 도달 후 GRAB 대기 — busy 해제
            threading.Thread(target=_stir_move_and_release, daemon=True).start()
            respond(self, {"ok": True, "action": "막대 이동"})

        elif p == "/stir_grip":
            if _busy: respond(self, {"ok": False, "reason": "동작 중"}); return
            threading.Thread(target=run_async, args=(_stir_grip,), daemon=True).start()
            respond(self, {"ok": True, "action": "막대 잡기+복귀"})

        elif p == "/stir_beaker_move":
            if _busy: respond(self, {"ok": False, "reason": "동작 중"}); return
            def _stir_beaker_move_and_release():
                global _stop_flag, _busy
                _busy = True
                _stop_flag = False
                _stir_beaker_move()
                _busy = False  # 비커 위 도달 후 SHAKE 대기 — busy 해제
            threading.Thread(target=_stir_beaker_move_and_release, daemon=True).start()
            respond(self, {"ok": True, "action": "비커 위치 이동"})

        elif p == "/stir_do":
            if _busy: respond(self, {"ok": False, "reason": "동작 중"}); return
            threading.Thread(target=run_async, args=(_stir_do,), daemon=True).start()
            respond(self, {"ok": True, "action": "섞기 동작"})

        elif p == "/stir_drop_move":
            if _busy: respond(self, {"ok": False, "reason": "동작 중"}); return
            def _stir_drop_move_and_release():
                global _stop_flag, _busy
                _busy = True
                _stop_flag = False
                _stir_drop_move()
                _busy = False  # 막대 원위치 도달 후 RELEASE 대기 — busy 해제
            threading.Thread(target=_stir_drop_move_and_release, daemon=True).start()
            respond(self, {"ok": True, "action": "막대 원위치 이동"})

        elif p == "/stir_drop_release":
            if _busy: respond(self, {"ok": False, "reason": "동작 중"}); return
            threading.Thread(target=run_async, args=(_stir_drop_release,), daemon=True).start()
            respond(self, {"ok": True, "action": "막대 놓기+복귀"})

        elif p == "/reset":
            if _busy: respond(self, {"ok": False, "reason": "동작 중"}); return
            threading.Thread(target=run_async,
                             args=(run_reset, _pickups, _drops, _reset_picks, _reset_drops),
                             daemon=True).start()
            respond(self, {"ok": True, "action": "리셋"})

        elif p == "/grip/open":
            gripper_open()
            respond(self, {"ok": True})

        elif p == "/grip/close":
            gripper_close()
            respond(self, {"ok": True})

        else:
            respond(self, {"ok": False, "reason": "unknown"}, 404)


if __name__ == "__main__":
    import socketserver
    HTTPServer.allow_reuse_address = True
    server = HTTPServer(("0.0.0.0", 5001), Handler)
    print("=== SterileBot 서버 v2 (포트 5001) ===")
    try:    server.serve_forever()
    except KeyboardInterrupt:
        print("\n[종료]"); server.server_close()