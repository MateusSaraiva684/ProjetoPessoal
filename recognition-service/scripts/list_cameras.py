import cv2


def main() -> None:
    found = False

    for index in range(10):
        cap = cv2.VideoCapture(index, cv2.CAP_MSMF)
        ok, frame = cap.read() if cap.isOpened() else (False, None)
        cap.release()

        if ok and frame is not None:
            height, width = frame.shape[:2]
            print(f"Camera encontrada: CAMERA_INDEX={index} ({width}x{height})")
            found = True

    if not found:
        print("Nenhuma camera abriu. Confira se o Iriun esta aberto no celular e no Windows.")


if __name__ == "__main__":
    main()
