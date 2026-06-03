from flask import Blueprint, request, jsonify
from db import get_db


# ══════════════════════════════════════════════════════════════════
# 비상 이력 API Blueprint
# - POST /api/emergency/start : 비상 발생 시 emergency_log INSERT
# - POST /api/emergency/end   : 비상 해제 시 resolved_at UPDATE
# ══════════════════════════════════════════════════════════════════

# Blueprint 생성 — app.py에서 register_blueprint로 등록
emergency_bp = Blueprint("emergency", __name__)


"""
비상 발생 시 호출 → emergency_log 테이블에 INSERT
Body(JSON):
    trigger_source : GAS_SENSOR / WPF_BUTTON / PI_BUTTON / FALL_DOWN
    gas_level      : 발생 시 가스 수치 (가스 센서일 때만, 없으면 null)
    researcher_id  : 당시 로그인한 연구원 ID (없으면 null)
    experiment_id  : 진행 중이던 실험 ID (없으면 null)
Response:
    {"ok": true, "id": 생성된_로그_ID}  ← id는 end 호출 시 필요
"""
@emergency_bp.route("/api/emergency/start", methods=["POST"])
def emergency_start():
    d = request.get_json()
    trigger_source = d.get("trigger_source")  # 발생원인
    gas_level      = d.get("gas_level")       # 가스 수치 (optional)
    researcher_id  = d.get("researcher_id")   # 연구원 ID (optional)
    experiment_id  = d.get("experiment_id")   # 실험 ID (optional)

    try:
        db = get_db()
        cur = db.cursor()
        cur.execute(
            """
            INSERT INTO emergency_log(trigger_source, gas_level, researcher_id, experiment_id)
            VALUES (%s, %s, %s, %s)
            """
            , (trigger_source, gas_level, researcher_id, experiment_id))
        db.commit()
        new_id = cur.lastrowid  # 생성된 행의 ID (end 호출 시 사용)
        db.close()
        print(f"[EMERGENCY] 적재 완료 ID={new_id} source={trigger_source}, {researcher_id}")
        return jsonify({"ok":True, "id":new_id})
    except Exception as e:
        return jsonify({"ok":False, "error":str(e)}),500




"""
비상 해제 시 호출 → resolved_at, duration_sec, resolved_by UPDATE
Body(JSON):
    id          : emergency_start에서 받은 emergency_log ID
    resolved_by : WPF_RESET / PI_BUTTON / ANOTHER
"""
@emergency_bp.route("/api/emergency/end", methods=["POST"])
def emergency_end():
    d           = request.get_json()
    log_id      = d.get("id")           # 업데이트할 로그 ID
    resolved_by = d.get("resolved_by")  # 해제 주체

    try :
        db = get_db()
        cur = db.cursor()
        cur.execute(
            """
             UPDATE emergency_log
                SET resolved_at  = NOW(),
                    duration_sec = TIMESTAMPDIFF(SECOND, occurred_at, NOW()),
                    resolved_by  = %s
              WHERE id = %s
                AND resolved_at IS NULL
            """
            , (resolved_by, log_id))
        db.commit()
        db.close()
        print(f"[EMERGENCY] 해제 완료 ID={log_id} by={resolved_by}")
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500
    

@emergency_bp.route("/api/emergency/update_researcher", methods=["POST"])
def emergency_update_researcher():
    """Pi 발생 비상에 researcher_id 업데이트 (WPF가 호출)"""
    d = request.get_json()
    researcher_id = d.get("researcher_id")

    try:
        db = get_db(); cur = db.cursor()
        # 현재 해제 안 된 비상 중 researcher_id 없는 것에 업데이트
        cur.execute("""
            UPDATE emergency_log
            SET researcher_id = %s
            WHERE researcher_id IS NULL
              AND resolved_at IS NULL
        """, (researcher_id,))
        db.commit(); db.close()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500 