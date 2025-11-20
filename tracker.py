import cv2
import numpy as np
import math
import os
from collections import deque
import time
from ultralytics import YOLO


# -----------------------------------------------------------
# READ VIDEO SOURCE
# -----------------------------------------------------------
VIDEO_SOURCE = os.getenv("VIDEO_SOURCE", "0")

try:
    VIDEO_SOURCE = int(VIDEO_SOURCE)
except ValueError:
    pass


# -----------------------------------------------------------
# PARAMETERS
# -----------------------------------------------------------
CONF_THRESHOLD = 0.4
ANGLE_WINDOW = 5
MIN_TURN_ANGLE_DEG = 25
MIN_FRAMES_BETWEEN_TURNS = 10
BUFFER_SIZE = 50


# -----------------------------------------------------------
# LOAD YOLOv8 MODEL
# -----------------------------------------------------------
print("[INFO] Loading YOLOv8 model...")
model = YOLO("yolov8n.pt")  # nano model (very fast)

print("[INFO] Model loaded.")


# -----------------------------------------------------------
# OPEN VIDEO SOURCE
# -----------------------------------------------------------
print(f"[INFO] Opening video source: {VIDEO_SOURCE}")
cap = cv2.VideoCapture(VIDEO_SOURCE)

if not cap.isOpened():
    print("[ERROR] Cannot open video source.")
    exit(1)

fps = cap.get(cv2.CAP_PROP_FPS)
if fps == 0 or fps != fps:
    fps = 30.0

print(f"[INFO] Estimated FPS: {fps}")


# -----------------------------------------------------------
# STATE VARIABLES
# -----------------------------------------------------------
trajectory = deque(maxlen=BUFFER_SIZE)
angles_smooth = deque(maxlen=BUFFER_SIZE)

turn_count = 0
last_turn_frame = -999
frame_idx = 0
start_time = time.time()


def detect_turn(angle_list):
    """Detect turning events."""
    global last_turn_frame, frame_idx

    if len(angle_list) < 5:
        return False

    recent = np.array(angle_list)[-10:]

    if len(recent) < 3:
        return False

    prev_a = recent[-3]
    curr_a = recent[-2]
    next_a = recent[-1]

    if (curr_a - prev_a) * (next_a - curr_a) < 0:
        diff = abs(curr_a - prev_a)

        if diff >= math.radians(MIN_TURN_ANGLE_DEG):
            if frame_idx - last_turn_frame >= MIN_FRAMES_BETWEEN_TURNS:
                last_turn_frame = frame_idx
                return True

    return False


# -----------------------------------------------------------
# MAIN LOOP
# -----------------------------------------------------------
print("[INFO] Starting real-time turn detection (YOLOv8, headless)...")

while True:
    ret, frame = cap.read()
    if not ret:
        print("[WARN] Could not read frame. Exiting...")
        break

    # YOLOv8 inference
    results = model(frame, verbose=False)[0]

    detections = []
    for box in results.boxes:
        x1, y1, x2, y2 = box.xyxy[0].tolist()
        conf = float(box.conf[0])
        cls = int(box.cls[0])
        detections.append([x1, y1, x2, y2, conf, cls])

    # Filter for persons only (class 0)
    persons = [d for d in detections if d[5] == 0]

    cx = cy = None

    if len(persons) > 0:
        best = max(persons, key=lambda d: (d[2] - d[0]) * (d[3] - d[1]))
        x1, y1, x2, y2, conf, cls = best
        cx = (x1 + x2) / 2
        cy = (y1 + y2) / 2

    if cx is not None:
        trajectory.append((cx, cy))

        if len(trajectory) >= 2:
            (px, py), (nx, ny) = trajectory[-2], trajectory[-1]
            dx = nx - px
            dy = ny - py
            angle = math.atan2(dy, dx)

            angles_smooth.append(angle)

            if len(angles_smooth) >= ANGLE_WINDOW:
                window = list(angles_smooth)[-ANGLE_WINDOW:]
                smoothed = sum(window) / len(window)
                angles_smooth.pop()
                angles_smooth.append(smoothed)

            if detect_turn(list(angles_smooth)):
                turn_count += 1
                timestamp = time.time() - start_time
                print(f"[TURN] frame={frame_idx}, time={timestamp:.2f}s, total_turns={turn_count}")

    frame_idx += 1


cap.release()
print(f"[INFO] Total turns detected: {turn_count}")
