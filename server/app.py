"""
ChemiBot — Flask API 서버 (통합)
- REST API + SSE: 모니터링 WPF (HTTP 폴링)
- 관리자 기능: 연구원 관리 / 실험 이력 / 시스템 설정
- 안면인식: 얼굴 등록 / 로그인 인증 (MySQL + face_recognition)
- React 빌드 서빙: manager_web/dist/
"""

from flask import Flask, jsonify, request, Response, send_from_directory
from flask_cors import CORS
from datetime import datetime
import json
import time
import random
import threading
import os
import io
import pickle
import sys

from db import get_db
from routes.emergency import emergency_bp

import face_recognition
import cv2
import mysql.connector
import numpy as np

# Allow unpickling face_data created under newer numpy module paths.
sys.modules.setdefault("numpy._core", np.core)
sys.modules.setdefault("numpy._core.numeric", np.core.numeric)
sys.modules.setdefault("numpy._core.multiarray", np.core.multiarray)

app = Flask(__name__)
CORS(app)
app.register_blueprint(emergency_bp)

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

DATA_FILE = "data.json"

_face_buf = []
_face_fail_count = 0
_face_buf_lock = threading.Lock()

FACE_REQUIRED = 1
FACE_WINDOW = 5
FACE_WINDOW_SEC = 8.0
FACE_THRESHOLD = 0.4
FACE_MAX_FAIL = 15


def sse_message(data):
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


def simulation_loop():
    ear_v, gx, gy, dw_v, dwelling = 0.32, 640.0, 400.0, 0.0, False
    while True:
        time.sleep(0.05)
        ear_v += (random.random() - 0.5) * 0.024
        if random.random() < 0.025:
            ear_v = 0.10 + random.random() * 0.08
        ear_v = max(0.10, min(0.48, ear_v))
        gx = max(160, min(1120, gx + (random.random() - 0.5) * 16))
        gy = max(80, min(720, gy + (random.random() - 0.5) * 11))
        if random.random() < 0.012:
            dwelling = not dwelling
        dw_v = min(100, dw_v + 2.2) if dwelling else max(0, dw_v - 3.8)

        with state_lock:
            th = state["params"]["ear_threshold"]
            blink = ear_v < th
            state["ear"] = round(ear_v, 3)
            state["gaze"] = {
                "cx": round(gx),
                "cy": round(gy),
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

            if state["fsm"] == "MOVING":
                state["robot"]["x"] += round((random.random() - 0.5) * 4, 1)
                state["robot"]["y"] += round((random.random() - 0.5) * 4, 1)


threading.Thread(target=simulation_loop, daemon=True).start()


def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)

    return {
        "researchers": [
            {"id": 1, "name": "김규대", "role": "관리자", "face_registered": True, "created": "2026-05-12"},
            {"id": 2, "name": "김수영", "role": "연구원", "face_registered": True, "created": "2026-05-12"},
            {"id": 3, "name": "정서현", "role": "연구원", "face_registered": True, "created": "2026-05-12"},
            {"id": 4, "name": "강은비", "role": "연구원", "face_registered": False, "created": "2026-05-12"},
        ],
        "usage_logs": [
            {"id": 1, "date": "2026-05-13", "researcher": "김수영", "start": "14:00", "end": "14:35", "status": "완료"},
            {"id": 2, "date": "2026-05-13", "researcher": "정서현", "start": "15:00", "end": "15:20", "status": "완료"},
            {"id": 3, "date": "2026-05-14", "researcher": "김규대", "start": "10:00", "end": "10:45", "status": "완료"},
            {"id": 4, "date": "2026-05-14", "researcher": "김수영", "start": "11:00", "end": "11:15", "status": "비상정지"},
            {"id": 5, "date": "2026-05-15", "researcher": "정서현", "start": "09:00", "end": "09:50", "status": "완료"},
        ],
        "error_logs": [
            {"id": 1, "date": "2026-05-14", "time": "11:12:34", "researcher": "김수영", "type": "비상정지", "desc": "긴급정지 버튼 동작"},
            {"id": 2, "date": "2026-05-13", "time": "14:28:11", "researcher": "김수영", "type": "안전반경초과", "desc": "안전 반경 초과"},
            {"id": 3, "date": "2026-05-13", "time": "15:15:02", "researcher": "정서현", "type": "연결오류", "desc": "myCobot Pi 연결 해제"},
        ],
        "settings": {
            "robot_ip": "192.168.0.20",
            "socket_port": "9001",
            "flask_port": "5000",
            "gas_warn": "100",
            "gas_danger": "200",
            "temp_min": "18",
            "temp_max": "28",
            "humid_min": "30",
            "humid_max": "60",
        },
    }


def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _decode_rgb_image(img_bytes: bytes) -> np.ndarray:
    arr = np.frombuffer(img_bytes, dtype=np.uint8)
    img_bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img_bgr is None:
        raise ValueError("Failed to decode JPEG bytes")
    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    return np.ascontiguousarray(img_rgb, dtype=np.uint8)


def _resize_for_face(img_rgb: np.ndarray, max_width: int = 320) -> tuple[np.ndarray, float]:
    h, w = img_rgb.shape[:2]
    if w <= max_width:
        return img_rgb, 1.0

    scale = max_width / float(w)
    new_w = max_width
    new_h = max(1, int(h * scale))
    resized = cv2.resize(img_rgb, (new_w, new_h), interpolation=cv2.INTER_AREA)
    return np.ascontiguousarray(resized, dtype=np.uint8), scale


@app.route("/stream")
def stream():
    def gen():
        while True:
            with state_lock:
                yield sse_message(
                    {k: state[k] for k in ("fsm", "ear", "gaze", "dwell", "robot", "gripper", "gaze_enabled")}
                )
            time.sleep(0.05)

    return Response(
        gen(),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.route("/api/state")
def get_state():
    with state_lock:
        return jsonify(state)


@app.route("/api/fsm", methods=["POST"])
def set_fsm():
    d = request.get_json()
    s = d.get("state", "IDLE").upper()
    if s not in ("IDLE", "MOVING", "GRIP", "ESTOP"):
        return jsonify({"error": "invalid"}), 400
    with state_lock:
        state["fsm"] = s
    return jsonify({"ok": True, "fsm": s})


@app.route("/api/move", methods=["POST"])
def move():
    d = request.get_json()
    with state_lock:
        for k in ("x", "y", "z", "rx", "ry", "rz"):
            if k in d:
                state["robot"][k] = d[k]
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
    g = request.get_json().get("state", "open")
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
    with state_lock:
        state["params"].update(request.get_json())
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


@app.route("/api/researchers/<int:rid>/face", methods=["POST"])
def register_face(rid):
    img_bytes = request.data
    if not img_bytes:
        return jsonify({"error": "이미지 데이터가 없습니다"}), 400

    try:
        img = face_recognition.load_image_file(io.BytesIO(img_bytes))

        img_bgr = cv2.imdecode(np.frombuffer(img_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
        if img_bgr is not None:
            lab = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2LAB)
            l, a, b = cv2.split(lab)
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            l = clahe.apply(l)
            lab = cv2.merge([l, a, b])
            img = cv2.cvtColor(cv2.cvtColor(lab, cv2.COLOR_LAB2BGR), cv2.COLOR_BGR2RGB)

        face_locations = face_recognition.face_locations(
            img,
            model="hog",
            number_of_times_to_upsample=2,
        )
        if not face_locations:
            return jsonify({"error": "얼굴을 찾지 못했습니다. 정면을 바라봐 주세요."}), 400

        encodings = face_recognition.face_encodings(
            img,
            known_face_locations=face_locations,
            num_jitters=3,
        )
    except Exception as e:
        return jsonify({"error": f"이미지 처리 실패: {str(e)}"}), 400

    if not encodings:
        return jsonify({"error": "얼굴을 찾지 못했습니다. 정면을 바라봐 주세요."}), 400

    reset = request.args.get("reset", "").lower() == "true"
    if reset:
        existing = []
    else:
        try:
            db = get_db()
            cur = db.cursor()
            cur.execute("SELECT face_data FROM researcher WHERE id=%s", (rid,))
            row = cur.fetchone()
            existing = []
            if row and row[0]:
                existing = pickle.loads(row[0])
                if not isinstance(existing, list):
                    existing = [existing]
            db.close()
        except Exception:
            existing = []

    existing.append(encodings[0])
    encoding_blob = pickle.dumps(existing)

    try:
        db = get_db()
        cur = db.cursor()
        cur.execute(
            "UPDATE researcher SET face_data=%s, face_registered_at=NOW(), updated_at=NOW() WHERE id=%s",
            (encoding_blob, rid),
        )
        affected = cur.rowcount
        db.commit()
        db.close()
    except Exception as e:
        return jsonify({"error": f"DB 저장 실패: {str(e)}"}), 500

    if affected == 0:
        return jsonify({"error": "해당 연구원을 찾을 수 없습니다"}), 404

    data = load_data()
    for r in data["researchers"]:
        if r["id"] == rid:
            r["face_registered"] = True
            save_data(data)
            return jsonify({"ok": True, "researcher": r})

    return jsonify({"ok": True, "id": rid})


@app.route("/api/face/login", methods=["POST"])
def face_login():
    global _face_fail_count

    img_bytes = request.data
    if not img_bytes:
        return jsonify({"ok": False, "reason": "이미지 데이터 없음"}), 400

    print(f"[DEBUG] 받은 바이트 수: {len(img_bytes)}")

    try:
        t0 = time.perf_counter()

        img_rgb = _decode_rgb_image(img_bytes)
        img_small, scale = _resize_for_face(img_rgb, max_width=320)

        print(
            f"[DEBUG] img shape={img_rgb.shape}, dtype={img_rgb.dtype}, contiguous={img_rgb.flags['C_CONTIGUOUS']}"
        )
        print(
            f"[DEBUG] small shape={img_small.shape}, dtype={img_small.dtype}, contiguous={img_small.flags['C_CONTIGUOUS']}, scale={scale:.3f}"
        )

        t1 = time.perf_counter()
        face_locations = face_recognition.face_locations(
            img_small,
            model="hog",
            number_of_times_to_upsample=0,
        )
        t2 = time.perf_counter()

        print(
            f"[DEBUG] face_locations={len(face_locations)} decode_ms={(t1 - t0) * 1000:.1f} detect_ms={(t2 - t1) * 1000:.1f}"
        )

        if not face_locations:
            return jsonify({"ok": False, "reason": "얼굴 없음", "retry": True})

        encodings = face_recognition.face_encodings(
            img_small,
            known_face_locations=face_locations,
            num_jitters=1,
        )
        t3 = time.perf_counter()

        print(f"[DEBUG] encodings={len(encodings)} encode_ms={(t3 - t2) * 1000:.1f} total_ms={(t3 - t0) * 1000:.1f}")

    except Exception as e:
        print(f"[DEBUG] 예외 발생: {type(e).__name__}: {str(e)}")
        return jsonify({"ok": False, "reason": f"이미지 처리 실패: {str(e)}"}), 400

    if not encodings:
        print(f"[DEBUG] 인코딩 실패 - face_locations: {len(face_locations)}")
        return jsonify({"ok": False, "reason": "얼굴 없음", "retry": True})

    target = encodings[0]

    try:
        db = get_db()
        cur = db.cursor(dictionary=True)
        cur.execute(
            "SELECT id, name, role, face_data FROM researcher "
            "WHERE face_data IS NOT NULL AND is_active = 1"
        )
        rows = cur.fetchall()
        db.close()
        print(f"[DEBUG] db rows={len(rows)}")
    except Exception as e:
        print(f"[DEBUG] DB 조회 예외: {type(e).__name__}: {str(e)}")
        return jsonify({"ok": False, "reason": f"DB 조회 실패: {str(e)}"}), 500

    if not rows:
        return jsonify({"ok": False, "reason": "등록된 얼굴이 없습니다"})

    best_match = None
    best_dist = 1.0

    for row in rows:
        try:
            face_blob = row["face_data"]
            blob_len = len(face_blob) if face_blob is not None else 0
            print(f"[DEBUG] researcher id={row['id']} name={row['name']} blob_len={blob_len}")

            stored = pickle.loads(face_blob)
            print(f"[DEBUG] pickle.loads ok for id={row['id']} type={type(stored).__name__}")

            if not isinstance(stored, list):
                stored = [stored]

            print(f"[DEBUG] stored vectors id={row['id']} count={len(stored)}")
            distances = face_recognition.face_distance(stored, target)
            dist = float(np.min(distances))
            print(f"[FACE] {row['name']}: dist={dist:.4f} (vectors={len(stored)})")
            if dist < best_dist:
                best_dist = dist
                best_match = row
        except Exception as e:
            print(
                f"[DEBUG] researcher match 예외 id={row.get('id')} "
                f"name={row.get('name')} {type(e).__name__}: {str(e)}"
            )
            continue

    if best_match:
        print(
            f"[FACE] best={best_match['name']} dist={best_dist:.4f} "
            f"{'PASS' if best_dist < FACE_THRESHOLD else 'FAIL'} (threshold={FACE_THRESHOLD})"
        )
    else:
        print("[FACE] 매칭 대상 없음")

    now = time.time()

    with _face_buf_lock:
        _face_buf[:] = [(t, mid, d) for t, mid, d in _face_buf if now - t < FACE_WINDOW_SEC]

        if best_match and best_dist < FACE_THRESHOLD:
            _face_fail_count = 0
            _face_buf.append((now, best_match["id"], best_dist))

            recent = _face_buf[-FACE_WINDOW:]
            matched_count = sum(1 for _, mid, _ in recent if mid == best_match["id"])

            if matched_count >= FACE_REQUIRED:
                matched_dists = [d for _, mid, d in recent if mid == best_match["id"]]
                avg_dist = float(np.mean(matched_dists))
                confidence = round(min(99.9, (1 - avg_dist ** 2) * 100), 1)
                _face_buf.clear()
                _face_fail_count = 0
                return jsonify(
                    {
                        "ok": True,
                        "id": best_match["id"],
                        "name": best_match["name"],
                        "role": best_match["role"],
                        "confidence": confidence,
                    }
                )

            return jsonify(
                {
                    "ok": False,
                    "retry": True,
                    "reason": f"인식 중... ({matched_count}/{FACE_REQUIRED})",
                }
            )

        _face_fail_count += 1

        if _face_fail_count >= FACE_MAX_FAIL:
            _face_buf.clear()
            _face_fail_count = 0
            return jsonify({"ok": False, "reason": "인증 실패", "retry": False})

    return jsonify({"ok": False, "reason": "얼굴 인식 중...", "retry": True})


@app.route("/api/researchers", methods=["GET"])
def get_researchers():
    return jsonify(load_data()["researchers"])


@app.route("/api/researchers", methods=["POST"])
def add_researcher():
    data = load_data()
    b = request.json
    name = b["name"]
    role = b.get("role", "연구원")

    db_role = "admin" if role == "관리자" else "researcher"
    try:
        db = get_db()
        cur = db.cursor()
        cur.execute(
            "INSERT INTO researcher (name, role, created_at, updated_at, is_active) "
            "VALUES (%s, %s, NOW(), NOW(), 1)",
            (name, db_role),
        )
        nid = cur.lastrowid
        db.commit()
        db.close()
    except Exception as e:
        print(f"[WARN] MySQL INSERT 실패: {e}")
        nid = max([r["id"] for r in data["researchers"]], default=0) + 1

    r = {
        "id": nid,
        "name": name,
        "role": role,
        "face_registered": False,
        "created": datetime.now().strftime("%Y-%m-%d"),
    }
    data["researchers"].append(r)
    save_data(data)
    return jsonify(r)


@app.route("/api/researchers/<int:rid>", methods=["PUT"])
def update_researcher(rid):
    data = load_data()
    b = request.json
    for r in data["researchers"]:
        if r["id"] == rid:
            r.update(b)
            save_data(data)
            try:
                db = get_db()
                cur = db.cursor()
                db_role = "admin" if r["role"] == "관리자" else "researcher"
                cur.execute(
                    "UPDATE researcher SET name=%s, role=%s, updated_at=NOW() WHERE id=%s",
                    (r["name"], db_role, rid),
                )
                db.commit()
                db.close()
            except Exception as e:
                print(f"[WARN] MySQL UPDATE 실패: {e}")
            return jsonify(r)
    return jsonify({"error": "not found"}), 404


@app.route("/api/researchers/<int:rid>", methods=["DELETE"])
def delete_researcher(rid):
    data = load_data()
    data["researchers"] = [r for r in data["researchers"] if r["id"] != rid]
    save_data(data)
    try:
        db = get_db()
        cur = db.cursor()
        cur.execute("DELETE FROM researcher WHERE id=%s", (rid,))
        db.commit()
        db.close()
    except Exception as e:
        print(f"[WARN] MySQL DELETE 실패: {e}")
    return jsonify({"ok": True})


@app.route("/api/usage")
def get_usage():
    return jsonify(load_data()["usage_logs"])


@app.route("/api/errors")
def get_errors():
    return jsonify(load_data()["error_logs"])


@app.route("/api/settings", methods=["GET"])
def get_settings():
    return jsonify(load_data()["settings"])


@app.route("/api/settings", methods=["POST"])
def save_settings():
    data = load_data()
    data["settings"].update(request.json)
    save_data(data)
    return jsonify({"ok": True})


@app.route("/api/dashboard")
def get_dashboard():
    data = load_data()
    return jsonify(
        {
            "total_researchers": len(data["researchers"]),
            "face_registered": sum(1 for r in data["researchers"] if r["face_registered"]),
            "total_usage": len(data["usage_logs"]),
            "total_errors": len(data["error_logs"]),
            "estop_count": sum(1 for e in data["error_logs"] if e["type"] == "비상정지"),
            "recent_usage": data["usage_logs"][-5:][::-1],
            "recent_errors": data["error_logs"][-5:][::-1],
        }
    )


@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve_react(path):
    dist = os.path.join(app.root_path, "manager_web", "dist")
    if path and os.path.exists(os.path.join(dist, path)):
        return send_from_directory(dist, path)

    index = os.path.join(dist, "index.html")
    if os.path.exists(index):
        return send_from_directory(dist, "index.html")

    return jsonify(
        {
            "message": "개발 중: npm run dev (localhost:3000) 로 접속",
            "api": "Flask API 정상 (localhost:5000)",
        }
    ), 200


if __name__ == "__main__":
    print("=" * 50)
    print("ChemiBot 통합 서버")
    print("  관리자 React: http://localhost:3000 (npm run dev)")
    print("  Flask API:    http://localhost:5000")
    print("  WPF 폴링:     http://localhost:5000/api/state")
    print("  얼굴 등록:    POST /api/researchers/{id}/face")
    print("  얼굴 로그인:  POST /api/face/login")
    print("  Python exe:   ", sys.executable)
    print("  Python ver:   ", sys.version)
    print("=" * 50)
    app.run(debug=False, host="0.0.0.0", port=5000, threaded=True)
