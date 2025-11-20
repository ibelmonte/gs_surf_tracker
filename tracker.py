import cv2
import numpy as np
import math
import os
from collections import deque
import time
from ultralytics import YOLO
import json
import csv


# -----------------------------------------------------------
# CONFIGURATION
# -----------------------------------------------------------

VIDEO_SOURCE = os.getenv("VIDEO_SOURCE", "/app/data/input.mp4")

try:
    VIDEO_SOURCE = int(VIDEO_SOURCE)
except ValueError:
    pass

OUTPUT_PATH = "/app/data/output.mp4"
CSV_PATH = "/app/data/turns.csv"
JSON_PATH = "/app/data/turns.json"

# Turn detection parameters
CONF_THRESHOLD = 0.4
ANGLE_WINDOW = 5
MIN_TURN_ANGLE_DEG = 45
MIN_TURN_SPEED_DEG_PER_S = 25
TURN_SUSTAIN_FRAMES = 6
MIN_FRAMES_BETWEEN_TURNS = 15
BUFFER_SIZE = 70


# -----------------------------------------------------------
# LOAD YOLOv8
# -----------------------------------------------------------

print("[INFO] Loading YOLOv8 model...")
model = YOLO("yolov8n.pt")
print("[INFO] Model loaded.")


# -----------------------------------------------------------
# OPEN VIDEO
# -----------------------------------------------------------

print(f"[INFO] Opening video source: {VIDEO_SOURCE}")
cap = cv2.VideoCapture(VIDEO_SOURCE)

if not cap.isOpened():
    print("[ERROR] Cannot open video source.")
    exit(1)

fps = cap.get(cv2.CAP_PROP_FPS)
if fps == 0 or fps != fps:
    fps = 30.0

frame_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
frame_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

print(f"[INFO] Resolution: {frame_w}x{frame_h}, FPS: {fps}")


# -----------------------------------------------------------
# OUTPUT VIDEO
# -----------------------------------------------------------

fourcc = cv2.VideoWriter_fourcc(*"mp4v")
out = cv2.VideoWriter(OUTPUT_PATH, fourcc, fps, (frame_w, frame_h))

print(f"[INFO] Exporting video → {OUTPUT_PATH}")


# -----------------------------------------------------------
# STATE
# -----------------------------------------------------------

trajectory = deque(maxlen=BUFFER_SIZE)
angles_smooth = deque(maxlen=BUFFER_SIZE)
timestamps = deque(maxlen=BUFFER_SIZE)

turn_count = 0
last_turn_frame = -999
frame_idx = 0
start_time = time.time()

turn_events = []


# -----------------------------------------------------------
# TURN DETECTOR
# -----------------------------------------------------------

def detect_turn(angles, times):
    global last_turn_frame, frame_idx

    if len(angles) < 12:
        return False, None, None

    window = np.array(angles[-12:])
    t = np.array(times[-12:])

    dtheta = np.diff(window)
    dt = np.diff(t)
    angular_speed = np.abs(dtheta / dt)

    # sustained turning
    recent_signs = np.sign(dtheta[-TURN_SUSTAIN_FRAMES:])
    sustained = np.sum(recent_signs == recent_signs[-1]) >= TURN_SUSTAIN_FRAMES - 1
    if not sustained:
        return False, None, None

    # magnitude
    angle_change = window[-1] - window[-TURN_SUSTAIN_FRAMES]
    abs_angle = abs(angle_change)
    if abs_angle < math.radians(MIN_TURN_ANGLE_DEG):
        return False, None, None

    # speed
    if np.mean(angular_speed[-TURN_SUSTAIN_FRAMES:]) < math.radians(MIN_TURN_SPEED_DEG_PER_S):
        return False, None, None

    # anti-spam
    if frame_idx - last_turn_frame < MIN_FRAMES_BETWEEN_TURNS:
        return False, None, None

    last_turn_frame = frame_idx

    # direction (left/right)
    direction = "left" if angle_change > 0 else "right"

    # severity
    angle_deg = math.degrees(abs_angle)
    if angle_deg < 60:
        severity = "mild"
    elif angle_deg < 90:
        severity = "medium"
    else:
        severity = "strong"

    return True, direction, severity


# -----------------------------------------------------------
# MAIN LOOP
# -----------------------------------------------------------

print("[INFO] Starting turn detection...")

while True:
    ret, frame = cap.read()
    if not ret:
        print("[WARN] End of video.")
        break

    results = model(frame, verbose=False)[0]

    detections = []
    for box in results.boxes:
        x1, y1, x2, y2 = box.xyxy[0].tolist()
        conf = float(box.conf[0])
        cls = int(box.cls[0])
        detections.append([x1, y1, x2, y2, conf, cls])

    persons = [d for d in detections if d[5] == 0]

    cx = cy = None
    best_box = None

    # pick the largest "person"
    if len(persons) > 0:
        best_box = max(persons, key=lambda d: (d[2] - d[0]) * (d[3] - d[1]))
        x1, y1, x2, y2, conf, cls = best_box
        cx = (x1 + x2) / 2
        cy = (y1 + y2) / 2

    turn_detected = False

    if cx is not None:
        trajectory.append((cx, cy))
        timestamps.append(time.time())

        if len(trajectory) >= 2:
            (px, py), (nx, ny) = trajectory[-2], trajectory[-1]
            dx = nx - px
            dy = ny - py
            angle = math.atan2(dy, dx)
            angles_smooth.append(angle)

            if len(angles_smooth) >= ANGLE_WINDOW:
                win = list(angles_smooth)[-ANGLE_WINDOW:]
                smoothed = sum(win) / len(win)
                angles_smooth.pop()
                angles_smooth.append(smoothed)

            detected, direction, severity = detect_turn(
                list(angles_smooth),
                list(timestamps)
            )

            if detected:
                turn_count += 1
                turn_detected = True

                timestamp = time.time() - start_time
                angle_deg = math.degrees(
                    abs(angles_smooth[-1] - angles_smooth[-TURN_SUSTAIN_FRAMES])
                )

                event = {
                    "frame": frame_idx,
                    "timestamp": timestamp,
                    "direction": direction,
                    "severity": severity,
                    "angle_degrees": angle_deg,
                }
                turn_events.append(event)

                print(f"[TURN] frame={frame_idx}, time={timestamp:.2f}s, "
                      f"turn={turn_count}, {direction}, {severity}, {angle_deg:.1f}°")

    # -------------------------------------------------------
    # DRAW OVERLAYS
    # -------------------------------------------------------

    # bounding box + counter
    if best_box is not None:
        x1, y1, x2, y2, conf, cls = best_box
        x1, y1, x2, y2 = map(int, [x1, y1, x2, y2])

        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)

        label = f"Turns: {turn_count}"
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)
        cv2.rectangle(frame, (x1, y1), (x1 + tw + 10, y1 + th + 10), (0, 255, 0), -1)
        cv2.putText(frame, label, (x1 + 5, y1 + th),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)

    # TURN! flash
    if turn_detected:
        cv2.putText(frame, "TURN!", (frame_w // 2 - 80, 80),
                    cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 0, 255), 4)

    out.write(frame)
    frame_idx += 1


# -----------------------------------------------------------
# SAVE CSV + JSON
# -----------------------------------------------------------

cap.release()
out.release()

with open(CSV_PATH, "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=[
        "frame", "timestamp", "direction", "severity", "angle_degrees"
    ])
    writer.writeheader()
    writer.writerows(turn_events)

with open(JSON_PATH, "w") as f:
    json.dump(turn_events, f, indent=4)

print(f"[INFO] CSV saved → {CSV_PATH}")
print(f"[INFO] JSON saved → {JSON_PATH}")
print(f"[INFO] Total turns detected: {turn_count}")
