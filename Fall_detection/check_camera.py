import cv2

print("카메라 인덱스 스캔 중...")
for i in range(5):
    cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
    if cap.isOpened():
        ret, frame = cap.read()
        if ret:
            print(f"  ✓ 카메라 {i} 사용 가능 ({int(cap.get(3))}x{int(cap.get(4))})")
            cv2.imshow(f"Camera {i}", frame)
            cv2.waitKey(1000)
        cap.release()
    else:
        print(f"  ✗ 카메라 {i} 없음")

cv2.destroyAllWindows()
print("완료")