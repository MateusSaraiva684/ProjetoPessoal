import os

import cv2

CAMERA_INDEX = int(os.getenv("CAMERA_INDEX", "0"))

cap = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_MSMF)

if not cap.isOpened():
    print(f"Nao abriu a camera no indice {CAMERA_INDEX}")
    raise SystemExit(1)

print(f"Camera aberta no indice {CAMERA_INDEX}")

while True:
    ret, frame = cap.read()

    if not ret:
        print("Erro ao capturar frame")
        break

    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    cv2.imshow("Camera", frame)

    if cv2.waitKey(1) & 0xFF == 27:
        break

cap.release()
cv2.destroyAllWindows()
