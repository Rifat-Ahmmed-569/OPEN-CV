import threading
import time
from typing import Optional

import cv2
import serial
from ultralytics import YOLO

SERIAL_PORT = "/dev/ttyACM0"
BAUD_RATE = 9600
DISTANCE_THRESHOLD_CM = 60.96
PERSON_CONFIDENCE_THRESHOLD = 0.55
PERSON_CLASS_ID = 0

LATEST_DISTANCE_CM: Optional[float] = None
DISTANCE_LOCK = threading.Lock()
LAST_SENT_STATE: Optional[str] = None
ARDUINO_SERIAL: Optional[serial.Serial] = None
SERIAL_THREAD_STOP = threading.Event()


def get_person_detector():
    model = YOLO("yolov8n.pt")
    return model


def detect_person(frame):
    model = get_person_detector()
    results = model(frame, verbose=False)[0]
    boxes = []
    confidences = []

    for box in results.boxes:
        cls_id = int(box.cls.item())
        conf = float(box.conf.item())
        if cls_id != PERSON_CLASS_ID or conf < PERSON_CONFIDENCE_THRESHOLD:
            continue
        x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
        boxes.append((x1, y1, max(0, x2 - x1), max(0, y2 - y1)))
        confidences.append(conf)

    if not boxes:
        return False, [], []

    return True, boxes, confidences


def get_latest_distance() -> Optional[float]:
    with DISTANCE_LOCK:
        return LATEST_DISTANCE_CM


def set_latest_distance(value: Optional[float]) -> None:
    global LATEST_DISTANCE_CM
    with DISTANCE_LOCK:
        LATEST_DISTANCE_CM = value


def serial_reader() -> None:
    global ARDUINO_SERIAL

    try:
        ARDUINO_SERIAL = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.1)
    except serial.SerialException as exc:
        print(f"Could not open {SERIAL_PORT}: {exc}", flush=True)
        SERIAL_THREAD_STOP.set()
        return

    while not SERIAL_THREAD_STOP.is_set():
        try:
            line = ARDUINO_SERIAL.readline()
        except serial.SerialException:
            print(f"Arduino disconnected from {SERIAL_PORT}", flush=True)
            break

        if not line:
            continue

        text = line.decode("utf-8", errors="replace").strip()
        if not text:
            continue

        try:
            distance_cm = float(text)
        except ValueError:
            continue

        if distance_cm <= 0 or distance_cm > 10000:
            continue

        set_latest_distance(distance_cm)

    try:
        ARDUINO_SERIAL.close()
    except Exception:
        pass
    ARDUINO_SERIAL = None


def send_command(command: str) -> None:
    global LAST_SENT_STATE

    if ARDUINO_SERIAL is None:
        return

    payload = (command + "\n").encode("utf-8")
    try:
        ARDUINO_SERIAL.write(payload)
        ARDUINO_SERIAL.flush()
    except serial.SerialException:
        print(f"Arduino disconnected from {SERIAL_PORT}", flush=True)
        return

    LAST_SENT_STATE = command


def determine_status(human_detected: bool, distance_cm: Optional[float]) -> str:
    if not human_detected:
        return "SAFE"
    if distance_cm is None:
        return "SAFE"
    if distance_cm < DISTANCE_THRESHOLD_CM:
        return "STOP"
    return "SAFE"


def draw_overlay(frame, human_detected, distance_cm, status):
    height, width = frame.shape[:2]
    text_y = 30

    if human_detected:
        label = "HUMAN DETECTED"
        cv2.putText(
            frame,
            label,
            (20, text_y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 255, 0),
            2,
            cv2.LINE_AA,
        )
        text_y += 30
    else:
        label = "NO HUMAN"
        cv2.putText(
            frame,
            label,
            (20, text_y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 0, 255),
            2,
            cv2.LINE_AA,
        )
        text_y += 30

    if distance_cm is None:
        distance_text = "Distance: Waiting..."
    else:
        distance_ft = distance_cm / 30.48
        distance_text = f"Distance: {distance_cm:.1f} cm ({distance_ft:.2f} ft)"

    cv2.putText(
        frame,
        distance_text,
        (20, text_y),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )
    text_y += 30

    cv2.putText(
        frame,
        f"STATUS: {status}",
        (20, text_y),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )

    if status == "STOP":
        color = (0, 0, 255)
    else:
        color = (0, 255, 0)

    cv2.rectangle(frame, (10, 10), (width - 10, height - 10), color, 2)


def main() -> None:
    global LAST_SENT_STATE

    serial_thread = threading.Thread(target=serial_reader, daemon=True)
    serial_thread.start()

    time.sleep(0.5)
    if ARDUINO_SERIAL is None:
        raise SystemExit(f"Could not open {SERIAL_PORT}")

    LAST_SENT_STATE = None
    send_command("SAFE")

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        raise SystemExit("Could not open camera.")

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("Camera read failed.", flush=True)
                break

            human_detected, boxes, confidences = detect_person(frame)

            for (x, y, w, h), confidence in zip(boxes, confidences):
                cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
                label = f"person {confidence:.2f}"
                cv2.putText(
                    frame,
                    label,
                    (x, max(0, y - 10)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (0, 255, 0),
                    2,
                    cv2.LINE_AA,
                )

            distance_cm = get_latest_distance()
            status = determine_status(human_detected, distance_cm)
            if not human_detected:
                cv2.putText(frame, "NO HUMAN", (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2, cv2.LINE_AA)
            draw_overlay(frame, human_detected, distance_cm, status)

            if status != LAST_SENT_STATE:
                send_command(status)

            cv2.imshow("Human Detection + Safety", frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    finally:
        SERIAL_THREAD_STOP.set()
        cap.release()
        cv2.destroyAllWindows()
        if ARDUINO_SERIAL is not None:
            try:
                ARDUINO_SERIAL.close()
            except Exception:
                pass


if __name__ == "__main__":
    main()
