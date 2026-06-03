"""
긴급 정지 핸들러 — WPF / Zone_tracker / gesture_control 공용

사용법:
    from stop_handler import emergency_stop, send_stop_to_zone_tracker

    # 로봇 물리 정지 (Pi 서버에 /stop 전송)
    emergency_stop("192.168.0.32", 5001)

    # Zone_tracker 상태 초기화 (제스처 소켓으로 STOP 전송)
    send_stop_to_zone_tracker("127.0.0.1", 9003)

    # 둘 다 동시에
    full_emergency_stop("192.168.0.32", 5001, "127.0.0.1", 9003)
"""

import requests
import socket
import json


def emergency_stop(robot_ip="192.168.0.32", robot_port=5001, timeout=3):
    """Pi 서버에 /stop 전송 → 로봇 물리 정지
    
    Returns:
        bool: 성공 여부
    """
    try:
        url = f"http://{robot_ip}:{robot_port}/stop"
        r = requests.get(url, timeout=timeout)
        data = r.json()
        print(f"[STOP] 로봇 정지: {data}")
        return data.get("ok", False)
    except Exception as e:
        print(f"[STOP] 로봇 정지 실패: {e}")
        return False


def send_stop_to_zone_tracker(host="127.0.0.1", port=9003):
    """Zone_tracker 제스처 소켓으로 STOP 전송 → 상태 초기화
    
    Returns:
        bool: 성공 여부
    """
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        sock.connect((host, port))
        msg = json.dumps({"gesture": "STOP", "finger": None, "action": "STOP"}) + "\n"
        sock.sendall(msg.encode())
        sock.close()
        print("[STOP] Zone_tracker에 STOP 전송 완료")
        return True
    except Exception as e:
        print(f"[STOP] Zone_tracker STOP 전송 실패: {e}")
        return False


def full_emergency_stop(robot_ip="192.168.0.32", robot_port=5001,
                        zt_host="127.0.0.1", zt_port=9003):
    """로봇 물리 정지 + Zone_tracker 상태 초기화 (WPF용)
    
    Returns:
        dict: {"robot": bool, "zone_tracker": bool}
    """
    result = {
        "robot": emergency_stop(robot_ip, robot_port),
        "zone_tracker": send_stop_to_zone_tracker(zt_host, zt_port),
    }
    print(f"[STOP] 결과: 로봇={'OK' if result['robot'] else 'FAIL'}, "
          f"Zone_tracker={'OK' if result['zone_tracker'] else 'FAIL'}")
    return result


if __name__ == "__main__":
    import sys
    ip = sys.argv[1] if len(sys.argv) > 1 else "192.168.0.32"
    print(f"긴급 정지 실행 (IP: {ip})")
    full_emergency_stop(robot_ip=ip)
