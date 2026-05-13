"""
SterileBot — Flask API 서버
- REST API + SSE: 모니터링 WPF (HTTP 폴링) / 관리자 React (fetch/SSE)
- 정적 파일: 관리자 React 빌드 결과물 serve (web/dist/)
"""

from flask import Flask, jsonify, request, Response, send_from_directory
from flask_cors import CORS
import json, time, random, threading, os

# 관리자 React 빌드 결과물 serve (npm run build → web/dist/)
app = Flask(__name__, static_folder="manager_web/dist", static_url_path="")
CORS(app)  # WPF(폴링), React 개발서버(3000) 모두 허용

# ── 공유 상태 ──────────────────────────────────────────────────────
state = {
    "fsm": "IDLE",
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


def sse_message(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


def simulation_loop():
    ear_v = 0.32
    gx, gy = 640.0, 400.0
    dw_v, dwelling = 0.0, False

    while True:
        time.sleep(0.05)

        ear_v += (random.random() - 0.5) * 0.024
        if random.random() < 0.025:
            ear_v = 0.10 + random.random() * 0.08
        ear_v = max(0.10, min(0.48, ear_v))

        gx = max(160, min(1120, gx + (random.random() - 0.5) * 16))
        gy = max(80,  min(720,  gy + (random.random() - 0.5) * 11))

        if random.random() < 0.012:
            dwelling = not dwelling
        dw_v = min(100, dw_v + 2.2) if dwelling else max(0, dw_v - 3.8)

        with state_lock:
            th = state["params"]["ear_threshold"]
            blink = ear_v < th
            state["ear"]  = round(ear_v, 3)
            state["gaze"] = {
                "cx": round(gx), "cy": round(gy),
                "rx": round((gx - 640) / 5.8),
                "ry": round((gy - 400) / 3.9),
            }
            state["dwell"] = round(dw_v, 1)

            if blink and state["gaze_enabled"]:
                state["fsm"] = "GRIP"; state["gripper"] = "closed"
            elif dw_v >= 100 and state["gaze_enabled"]:
                state["fsm"] = "MOVING"; dwelling = False; dw_v = 0
            elif state["fsm"] in ("GRIP", "MOVING"):
                state["fsm"] = "IDLE"; state["gripper"] = "open"

            if state["fsm"] == "MOVING":
                state["robot"]["x"] += round((random.random() - 0.5) * 4, 1)
                state["robot"]["y"] += round((random.random() - 0.5) * 4, 1)
                state["robot"]["z"] += round((random.random() - 0.5) * 2, 1)


threading.Thread(target=simulation_loop, daemon=True).start()


# ── SSE ───────────────────────────────────────────────────────────
@app.route("/stream")
def stream():
    def generate():
        while True:
            with state_lock:
                payload = {
                    "fsm":          state["fsm"],
                    "ear":          state["ear"],
                    "gaze":         state["gaze"],
                    "dwell":        state["dwell"],
                    "robot":        state["robot"],
                    "gripper":      state["gripper"],
                    "gaze_enabled": state["gaze_enabled"],
                }
            yield sse_message(payload)
            time.sleep(0.05)

    return Response(generate(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ── REST API ──────────────────────────────────────────────────────
@app.route("/api/state")
def get_state():
    with state_lock:
        return jsonify(state)


@app.route("/api/fsm", methods=["POST"])
def set_fsm():
    data = request.get_json()
    new_fsm = data.get("state", "IDLE").upper()
    if new_fsm not in ("IDLE", "MOVING", "GRIP", "ESTOP"):
        return jsonify({"error": "invalid state"}), 400
    with state_lock:
        state["fsm"] = new_fsm
    return jsonify({"ok": True, "fsm": new_fsm})


@app.route("/api/move", methods=["POST"])
def move():
    data = request.get_json()
    with state_lock:
        for k in ("x", "y", "z", "rx", "ry", "rz"):
            if k in data:
                state["robot"][k] = data[k]
        state["fsm"] = "MOVING"
    return jsonify({"ok": True, "robot": state["robot"]})


@app.route("/api/home", methods=["POST"])
def go_home():
    with state_lock:
        state["robot"] = {"x": 0, "y": 0, "z": 200, "rx": 0, "ry": 0, "rz": 0}
        state["fsm"] = "MOVING"
    return jsonify({"ok": True})


@app.route("/api/gripper", methods=["POST"])
def set_gripper():
    data = request.get_json()
    g = data.get("state", "open")
    with state_lock:
        state["gripper"] = g
        state["fsm"] = "GRIP" if g == "closed" else "IDLE"
    return jsonify({"ok": True, "gripper": g})


@app.route("/api/gaze_toggle", methods=["POST"])
def gaze_toggle():
    with state_lock:
        state["gaze_enabled"] = not state["gaze_enabled"]
        return jsonify({"ok": True, "gaze_enabled": state["gaze_enabled"]})


@app.route("/api/params", methods=["GET", "POST"])
def params():
    if request.method == "GET":
        with state_lock:
            return jsonify(state["params"])
    data = request.get_json()
    with state_lock:
        state["params"].update(data)
    return jsonify({"ok": True, "params": state["params"]})


calib_points = []

@app.route("/api/calib", methods=["GET", "POST", "DELETE"])
def calib():
    global calib_points
    if request.method == "GET":
        return jsonify({"points": calib_points, "count": len(calib_points)})
    if request.method == "DELETE":
        calib_points = []
        return jsonify({"ok": True})
    calib_points.append(request.get_json())
    return jsonify({"ok": True, "count": len(calib_points)})


# ── 관리자 React 서빙 ─────────────────────────────────────────────
# 개발 중 : npm run dev → http://localhost:3000
# 배포 시 : npm run build → web/dist/ → Flask가 serve
@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve_react(path):
    dist = os.path.join(app.root_path, "manager_web", "dist")
    if path and os.path.exists(os.path.join(dist, path)):
        return send_from_directory(dist, path)
    index = os.path.join(dist, "index.html")
    if os.path.exists(index):
        return send_from_directory(dist, "index.html")
    return jsonify({
        "message": "개발 중: npm run dev (localhost:3000) 로 접속하세요.",
        "api": "Flask API 정상 실행 중 (localhost:5000)"
    }), 200


if __name__ == "__main__":
    print("SterileBot Flask 서버 시작: http://localhost:5000")
    print("관리자 React 개발: http://localhost:3000 (npm run dev)")
    app.run(host="0.0.0.0", port=5000, threaded=True)