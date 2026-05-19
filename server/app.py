"""
ChemiBot — Flask API 서버 (통합)
- REST API + SSE: 모니터링 WPF (HTTP 폴링)
- 관리자 기능: 연구원 관리 / 실험 이력 / 시스템 설정
- React 빌드 서빙: manager_web/dist/
"""

from flask import Flask, jsonify, request, Response, send_from_directory
from flask_cors import CORS
from datetime import datetime
import json, time, random, threading, os

app = Flask(__name__)
CORS(app)

# ══════════════════════════════════════════════════════════════════
#  1. 실시간 상태 (WPF 모니터링용)
# ══════════════════════════════════════════════════════════════════
state = {
    "fsm": "IDLE",
    "ear": 0.32,
    "gaze": {"cx": 640, "cy": 400, "rx": 0, "ry": 0},
    "dwell": 0,
    "robot": {"x": 135, "y": -82, "z": 200, "rx": 0, "ry": 0, "rz": 0},
    "gripper": "open",
    "gaze_enabled": True,
    "params": {
        "ear_threshold": 0.20, "ear_ms": 150,
        "dwell_sec": 1.5, "dwell_radius": 30,
        "double_blink_sec": 0.5,
        "safe_radius": 260, "safe_z": 200,
        "grip_speed": 10, "move_speed": 30,
    },
}
state_lock = threading.Lock()

def sse_message(data): return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

def simulation_loop():
    ear_v, gx, gy, dw_v, dwelling = 0.32, 640.0, 400.0, 0.0, False
    while True:
        time.sleep(0.05)
        ear_v += (random.random() - 0.5) * 0.024
        if random.random() < 0.025: ear_v = 0.10 + random.random() * 0.08
        ear_v = max(0.10, min(0.48, ear_v))
        gx = max(160, min(1120, gx + (random.random() - 0.5) * 16))
        gy = max(80, min(720, gy + (random.random() - 0.5) * 11))
        if random.random() < 0.012: dwelling = not dwelling
        dw_v = min(100, dw_v + 2.2) if dwelling else max(0, dw_v - 3.8)
        with state_lock:
            th = state["params"]["ear_threshold"]
            blink = ear_v < th
            state["ear"] = round(ear_v, 3)
            state["gaze"] = {"cx": round(gx), "cy": round(gy), "rx": round((gx-640)/5.8), "ry": round((gy-400)/3.9)}
            state["dwell"] = round(dw_v, 1)
            if blink and state["gaze_enabled"]: state["fsm"] = "GRIP"; state["gripper"] = "closed"
            elif dw_v >= 100 and state["gaze_enabled"]: state["fsm"] = "MOVING"; dwelling = False; dw_v = 0
            elif state["fsm"] in ("GRIP", "MOVING"): state["fsm"] = "IDLE"; state["gripper"] = "open"
            if state["fsm"] == "MOVING":
                state["robot"]["x"] += round((random.random()-0.5)*4, 1)
                state["robot"]["y"] += round((random.random()-0.5)*4, 1)

threading.Thread(target=simulation_loop, daemon=True).start()

@app.route("/stream")
def stream():
    def gen():
        while True:
            with state_lock:
                yield sse_message({k: state[k] for k in ("fsm","ear","gaze","dwell","robot","gripper","gaze_enabled")})
            time.sleep(0.05)
    return Response(gen(), mimetype="text/event-stream", headers={"Cache-Control":"no-cache","X-Accel-Buffering":"no"})

@app.route("/api/state")
def get_state():
    with state_lock: return jsonify(state)

@app.route("/api/fsm", methods=["POST"])
def set_fsm():
    d = request.get_json(); s = d.get("state","IDLE").upper()
    if s not in ("IDLE","MOVING","GRIP","ESTOP"): return jsonify({"error":"invalid"}), 400
    with state_lock: state["fsm"] = s
    return jsonify({"ok":True,"fsm":s})

@app.route("/api/move", methods=["POST"])
def move():
    d = request.get_json()
    with state_lock:
        for k in ("x","y","z","rx","ry","rz"):
            if k in d: state["robot"][k] = d[k]
        state["fsm"] = "MOVING"
    return jsonify({"ok":True,"robot":state["robot"]})

@app.route("/api/home", methods=["POST"])
def go_home():
    with state_lock: state["robot"] = {"x":0,"y":0,"z":200,"rx":0,"ry":0,"rz":0}; state["fsm"] = "MOVING"
    return jsonify({"ok":True})

@app.route("/api/gripper", methods=["POST"])
def set_gripper():
    g = request.get_json().get("state","open")
    with state_lock: state["gripper"] = g; state["fsm"] = "GRIP" if g=="closed" else "IDLE"
    return jsonify({"ok":True,"gripper":g})

@app.route("/api/gaze_toggle", methods=["POST"])
def gaze_toggle():
    with state_lock: state["gaze_enabled"] = not state["gaze_enabled"]; return jsonify({"ok":True,"gaze_enabled":state["gaze_enabled"]})

@app.route("/api/params", methods=["GET","POST"])
def params():
    if request.method == "GET":
        with state_lock: return jsonify(state["params"])
    with state_lock: state["params"].update(request.get_json())
    return jsonify({"ok":True,"params":state["params"]})

calib_points = []
@app.route("/api/calib", methods=["GET","POST","DELETE"])
def calib():
    global calib_points
    if request.method == "GET": return jsonify({"points":calib_points,"count":len(calib_points)})
    if request.method == "DELETE": calib_points = []; return jsonify({"ok":True})
    calib_points.append(request.get_json()); return jsonify({"ok":True,"count":len(calib_points)})


# ══════════════════════════════════════════════════════════════════
#  2. 관리자 기능
# ══════════════════════════════════════════════════════════════════
DATA_FILE = "data.json"

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f: return json.load(f)
    return {
        "researchers": [
            {"id":1,"name":"김규대","role":"관리자","face_registered":True,"created":"2026-05-12"},
            {"id":2,"name":"김수영","role":"연구원","face_registered":True,"created":"2026-05-12"},
            {"id":3,"name":"정서현","role":"연구원","face_registered":True,"created":"2026-05-12"},
            {"id":4,"name":"강은비","role":"연구원","face_registered":False,"created":"2026-05-12"},
        ],
        "usage_logs": [
            {"id":1,"date":"2026-05-13","researcher":"김수영","start":"14:00","end":"14:35","status":"완료"},
            {"id":2,"date":"2026-05-13","researcher":"정서현","start":"15:00","end":"15:20","status":"완료"},
            {"id":3,"date":"2026-05-14","researcher":"김규대","start":"10:00","end":"10:45","status":"완료"},
            {"id":4,"date":"2026-05-14","researcher":"김수영","start":"11:00","end":"11:15","status":"비상정지"},
            {"id":5,"date":"2026-05-15","researcher":"정서현","start":"09:00","end":"09:50","status":"완료"},
        ],
        "error_logs": [
            {"id":1,"date":"2026-05-14","time":"11:12:34","researcher":"김수영","type":"비상정지","desc":"이중 깜빡임으로 긴급정지 발동"},
            {"id":2,"date":"2026-05-13","time":"14:28:11","researcher":"김수영","type":"안전반경초과","desc":"좌표 (280,-50,150) 안전 반경 260mm 초과"},
            {"id":3,"date":"2026-05-13","time":"15:15:02","researcher":"정서현","type":"연결끊김","desc":"myCobot Pi 연결 해제됨"},
        ],
        "settings": {"robot_ip":"192.168.0.20","socket_port":"9001","flask_port":"5000","gas_warn":"100","gas_danger":"200","temp_min":"18","temp_max":"28","humid_min":"30","humid_max":"60"}
    }

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f: json.dump(data, f, ensure_ascii=False, indent=2)

@app.route("/api/researchers", methods=["GET"])
def get_researchers(): return jsonify(load_data()["researchers"])

@app.route("/api/researchers", methods=["POST"])
def add_researcher():
    data = load_data(); b = request.json
    nid = max([r["id"] for r in data["researchers"]], default=0) + 1
    r = {"id":nid,"name":b["name"],"role":b.get("role","연구원"),"face_registered":False,"created":datetime.now().strftime("%Y-%m-%d")}
    data["researchers"].append(r); save_data(data); return jsonify(r)

@app.route("/api/researchers/<int:rid>", methods=["PUT"])
def update_researcher(rid):
    data = load_data()
    for r in data["researchers"]:
        if r["id"] == rid: r.update(request.json); save_data(data); return jsonify(r)
    return jsonify({"error":"not found"}), 404

@app.route("/api/researchers/<int:rid>", methods=["DELETE"])
def delete_researcher(rid):
    data = load_data(); data["researchers"] = [r for r in data["researchers"] if r["id"] != rid]; save_data(data); return jsonify({"ok":True})

@app.route("/api/researchers/<int:rid>/face", methods=["POST"])
def register_face(rid):
    data = load_data()
    for r in data["researchers"]:
        if r["id"] == rid: r["face_registered"] = True; save_data(data); return jsonify(r)
    return jsonify({"error":"not found"}), 404

@app.route("/api/usage")
def get_usage(): return jsonify(load_data()["usage_logs"])

@app.route("/api/errors")
def get_errors(): return jsonify(load_data()["error_logs"])

@app.route("/api/settings", methods=["GET"])
def get_settings(): return jsonify(load_data()["settings"])

@app.route("/api/settings", methods=["POST"])
def save_settings():
    data = load_data(); data["settings"].update(request.json); save_data(data); return jsonify({"ok":True})

@app.route("/api/dashboard")
def get_dashboard():
    data = load_data()
    return jsonify({
        "total_researchers":len(data["researchers"]),
        "face_registered":sum(1 for r in data["researchers"] if r["face_registered"]),
        "total_usage":len(data["usage_logs"]),
        "total_errors":len(data["error_logs"]),
        "estop_count":sum(1 for e in data["error_logs"] if e["type"]=="비상정지"),
        "recent_usage":data["usage_logs"][-5:][::-1],
        "recent_errors":data["error_logs"][-5:][::-1],
    })

# ══════════════════════════════════════════════════════════════════
#  3. React 빌드 서빙
# ══════════════════════════════════════════════════════════════════
@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve_react(path):
    dist = os.path.join(app.root_path, "manager_web", "dist")
    if path and os.path.exists(os.path.join(dist, path)):
        return send_from_directory(dist, path)
    index = os.path.join(dist, "index.html")
    if os.path.exists(index):
        return send_from_directory(dist, "index.html")
    return jsonify({"message":"개발 중: npm run dev (localhost:3000) 로 접속","api":"Flask API 정상 (localhost:5000)"}), 200

if __name__ == "__main__":
    print("=" * 50)
    print("ChemiBot 통합 서버")
    print("  관리자 React: http://localhost:3000 (npm run dev)")
    print("  Flask API:    http://localhost:5000")
    print("  WPF 폴링:     http://localhost:5000/api/state")
    print("=" * 50)
    app.run(host="0.0.0.0", port=5000, threaded=True)
