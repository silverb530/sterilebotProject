"""
대피 안내 음성 재생 테스트
1 입력 → 비상 신호 (음성 재생)
0 입력 → 해제
q 입력 → 종료
"""

import os
import threading
import winsound

ALARM_FILE = r"C:\SterileBot\Test_Alarm\비상대피안내.wav"


def play_sound():
    if os.path.exists(ALARM_FILE):
        print(f"[재생] {ALARM_FILE}")
        winsound.PlaySound(ALARM_FILE, winsound.SND_FILENAME)
    else:
        print(f"[오류] 파일을 찾을 수 없습니다: {ALARM_FILE}")


def main():
    print("=" * 40)
    print("  대피 음성 재생 테스트")
    print(f"  파일: {ALARM_FILE}")
    print("=" * 40)
    print("  1 → 비상 (음성 재생)")
    print("  0 → 해제")
    print("  q → 종료")
    print("=" * 40 + "\n")

    while True:
        cmd = input("입력: ").strip()

        if cmd == "1":
            print("[비상] 음성 재생 시작")
            threading.Thread(target=play_sound, daemon=True).start()

        elif cmd == "0":
            print("[해제] 정상 상태")
            winsound.PlaySound(None, winsound.SND_PURGE)

        elif cmd == "q":
            print("[종료]")
            break

        else:
            print("[안내] 1=비상, 0=해제, q=종료")


if __name__ == "__main__":
    main()