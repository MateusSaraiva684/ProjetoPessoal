import os
import time

import cv2
import requests

API_URL = os.getenv("RECOGNITION_API_URL", "http://localhost:8001/api/recognize")
API_KEY = os.getenv("RECOGNITION_API_KEYS", "").split(",")[0].strip()
REQUEST_TIMEOUT_SECONDS = int(os.getenv("RECOGNITION_REQUEST_TIMEOUT_SECONDS", "10"))
CAMERA_INDEX = int(os.getenv("CAMERA_INDEX", "0"))

if not API_KEY:
    raise RuntimeError("Configure RECOGNITION_API_KEYS antes de enviar frames para a API")

headers = {"Authorization": f"Bearer {API_KEY}"}

cap = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_MSMF)

if not cap.isOpened():
    print(f"Nao abriu a camera no indice {CAMERA_INDEX}")
    raise SystemExit(1)

print(f"Sistema iniciado na camera {CAMERA_INDEX}... pressione Q para sair")

while True:
    ret, frame = cap.read()

    if not ret:
        print("Erro ao capturar imagem")
        break

    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    cv2.imshow("Camera", frame)

    try:
        print("Enviando frame...")

        _, img_encoded = cv2.imencode(".jpg", frame)
        files = {"file": ("frame.jpg", img_encoded.tobytes(), "image/jpeg")}

        response = requests.post(
            API_URL,
            files=files,
            headers=headers,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        data = response.json()

        job_id = data.get("job_id")

        if job_id:
            print(f"Job: {job_id}")

            while True:
                result_response = requests.get(
                    f"{API_URL}/{job_id}",
                    headers=headers,
                    timeout=REQUEST_TIMEOUT_SECONDS,
                )
                result_response.raise_for_status()
                result = result_response.json()

                print("Status:", result["status"])

                if result["status"] == "completed":
                    res = result["result"]

                    if res["status"] == "success":
                        print(f"{res['nome']} reconhecido")
                    else:
                        print("Desconhecido")

                    break

                if result["status"] == "failed":
                    print("Job falhou")
                    break

                time.sleep(1)

    except Exception as exc:
        print("Erro:", exc)

    time.sleep(3)

    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

cap.release()
cv2.destroyAllWindows()
