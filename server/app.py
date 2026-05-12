"""
SterileBot — Flask API 서버
- SSE (Server-Sent Events): 모니터 HTML에 실시간 데이터 스트리밍
- REST API: WPF 관리자 화면에서 명령 수신
"""

from flask import Flask, jsonify, request, Response, send_from_directory
from flask_cors import CORS
import json, time, math, random, threading

app = Flask(__name__, static_folder="web")
CORS(app)  # WPF, 브라우저 모두 허용

# ── 공유 상태 (실제로는 DB 또는 myCobot SDK 연결) ──────────────────
state = {
    "fsm": "IDLE",          # IDLE | MOVING | GRIP | ESTOP
    "ear": 0.32,
    "gaze": {"cx": 640, "cy": 400, "rx": 0, "ry": 0},
    "dwell": 0,
    "robot": {"x": 135, "y": -82, "z": 200, "rx": 0, "ry": 0, "rz": 0},
    "gripper": "open",
    "gaze_enabled": True,
    "params": {
        "ear_threshold": 0.20,
        "ear_ms": 150,
        "dwell_sec": 1.5,
        "dwell_radius": 30,
        "double_blink_sec": 0.5,
        "safe_radius": 260,
        "safe_z": 200,
        "grip_speed": 10,
        "move_speed": 30,
    },
}
state_lock = threading.Lock()


# ── SSE 헬퍼 ───────────────────────────────────────────────────────
def sse_message(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


# ── 백그라운드: 시뮬레이션 업데이트 (실제 프로젝트에서는 myCobot SDK로 교체) ──
def simulation_loop():
    """실제 프로젝트에서는 myCobot SDK / OpenCV 파이프라인으로 교체"""
    ear_v = 0.32
    gx, gy = 640.0, 400.0
    dw_v, dwelling = 0.0, False

    while True:
        time.sleep(0.05)  # 20 Hz

        # EAR
        ear_v += (random.random() - 0.5) * 0.024
        if random.random() < 0.025:
            ear_v = 0.10 + random.random() * 0.08
        ear_v = max(0.10, min(0.48, ear_v))

        # Gaze
        gx = max(160, min(1120, gx + (random.random() - 0.5) * 16))
        gy = max(80,  min(720,  gy + (random.random() - 0.5) * 11))

        # Dwell
        if random.random() < 0.012:
            dwelling = not dwelling
        if dwelling:
            dw_v = min(100, dw_v + 2.2)
        else:
            dw_v = max(0, dw_v - 3.8)

        with state_lock:
            th = state["params"]["ear_threshold"]
            blink = ear_v < th
            state["ear"] = round(ear_v, 3)
            state["gaze"] = {
                "cx": round(gx), "cy": round(gy),
                "rx": round((gx - 640) / 5.8),
                "ry": round((gy - 400) / 3.9),
            }
            state["dwell"] = round(dw_v, 1)

            if blink and state["gaze_enabled"]:
                state["fsm"] = "GRIP"
                state["gripper"] = "closed"
            elif dw_v >= 100 and state["gaze_enabled"]:
                state["fsm"] = "MOVING"
                dwelling = False
                dw_v = 0
            elif state["fsm"] in ("GRIP", "MOVING"):
                state["fsm"] = "IDLE"
                state["gripper"] = "open"

            # 로봇 좌표 시뮬레이션
            if state["fsm"] == "MOVING":
                state["robot"]["x"] += round((random.random() - 0.5) * 4, 1)
                state["robot"]["y"] += round((random.random() - 0.5) * 4, 1)
                state["robot"]["z"] += round((random.random() - 0.5) * 2, 1)


threading.Thread(target=simulation_loop, daemon=True).start()


# ══════════════════════════════════════════════════════════════════
# SSE 엔드포인트 — 모니터 HTML이 구독
# ══════════════════════════════════════════════════════════════════
@app.route("/stream")
def stream():
    """EventSource로 모니터 HTML에 20 Hz 스트리밍"""
    def generate():
        while True:
            with state_lock:
                payload = {
                    "fsm":     state["fsm"],
                    "ear":     state["ear"],
                    "gaze":    state["gaze"],
                    "dwell":   state["dwell"],
                    "robot":   state["robot"],
                    "gripper": state["gripper"],
                    "gaze_enabled": state["gaze_enabled"],
                }
            yield sse_message(payload)
            time.sleep(0.05)

    return Response(generate(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ══════════════════════════════════════════════════════════════════
# REST API — WPF 관리자 화면이 호출
# ══════════════════════════════════════════════════════════════════

# ── 상태 조회 ──────────────────────────────────────────────────────
@app.route("/api/state")
def get_state():
    with state_lock:
        return jsonify(state)


# ── FSM 제어 ──────────────────────────────────────────────────────
@app.route("/api/fsm", methods=["POST"])
def set_fsm():
    """
    WPF에서 POST /api/fsm  body: {"state": "ESTOP"}
    """
    data = request.get_json()
    new_fsm = data.get("state", "IDLE").upper()
    if new_fsm not in ("IDLE", "MOVING", "GRIP", "ESTOP"):
        return jsonify({"error": "invalid state"}), 400
    with state_lock:
        state["fsm"] = new_fsm
    return jsonify({"ok": True, "fsm": new_fsm})


# ── 로봇 좌표 이동 ────────────────────────────────────────────────
@app.route("/api/move", methods=["POST"])
def move():
    """
    WPF에서 POST /api/move
    body: {"x": 135, "y": -82, "z": 200, "rx": 0, "ry": 0, "rz": 0, "speed": 30}
    """
    data = request.get_json()
    with state_lock:
        for k in ("x", "y", "z", "rx", "ry", "rz"):
            if k in data:
                state["robot"][k] = data[k]
        state["fsm"] = "MOVING"
    # 실제: mycobot.send_coords([x,y,z,rx,ry,rz], speed, 1)
    return jsonify({"ok": True, "robot": state["robot"]})


@app.route("/api/home", methods=["POST"])
def go_home():
    with state_lock:
        state["robot"] = {"x": 0, "y": 0, "z": 200, "rx": 0, "ry": 0, "rz": 0}
        state["fsm"] = "MOVING"
    return jsonify({"ok": True})


# ── 그리퍼 ───────────────────────────────────────────────────────
@app.route("/api/gripper", methods=["POST"])
def set_gripper():
    """body: {"state": "open"} or {"state": "closed"}"""
    data = request.get_json()
    g = data.get("state", "open")
    with state_lock:
        state["gripper"] = g
        state["fsm"] = "GRIP" if g == "closed" else "IDLE"
    # 실제: mycobot.set_gripper_value(0 if open else 100, speed)
    return jsonify({"ok": True, "gripper": g})


# ── 시선 제어 토글 ────────────────────────────────────────────────
@app.route("/api/gaze_toggle", methods=["POST"])
def gaze_toggle():
    with state_lock:
        state["gaze_enabled"] = not state["gaze_enabled"]
        return jsonify({"ok": True, "gaze_enabled": state["gaze_enabled"]})


# ── 파라미터 업데이트 (WPF 파라미터 탭) ──────────────────────────
@app.route("/api/params", methods=["GET", "POST"])
def params():
    if request.method == "GET":
        with state_lock:
            return jsonify(state["params"])
    data = request.get_json()
    with state_lock:
        state["params"].update(data)
    return jsonify({"ok": True, "params": state["params"]})


# ── 캘리브레이션 데이터 저장 (WPF 캘리브레이션 탭) ───────────────
calib_points = []

@app.route("/api/calib", methods=["GET", "POST", "DELETE"])
def calib():
    global calib_points
    if request.method == "GET":
        return jsonify({"points": calib_points, "count": len(calib_points)})
    if request.method == "DELETE":
        calib_points = []
        return jsonify({"ok": True})
    # POST: 마커 한 쌍 추가
    data = request.get_json()
    # data = {"marker": 1, "px": 450, "py": 300, "mm_x": -60, "mm_y": -60}
    calib_points.append(data)
    return jsonify({"ok": True, "count": len(calib_points)})


# ── 정적 파일 서빙 (모니터 HTML) ──────────────────────────────────
@app.route("/")
def index():
    return send_from_directory("web", "sterilebot_monitor_v3.html")

if __name__ == "__main__":
    print("SterileBot Flask 서버 시작: http://localhost:5000")
    app.run(host="0.0.0.0", port=5000, threaded=True)