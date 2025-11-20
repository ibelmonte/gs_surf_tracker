import cv2
import torch
import numpy as np
import math
import os
from collections import deque
import time


# -----------------------------------------------------------
# READ VIDEO SOURCE FROM ENV
# -----------------------------------------------------------
VIDEO_SOURCE = os.getenv("VIDEO_SOURCE", "0")

try:
    # Try webcam index (e.g., "0")
    VIDEO_SOURCE = int(VIDEO_SOURCE)
except ValueError:
    # Otherwise treat as file path or RTSP URL
    pass


# -----------------------------------------------------------
# PARAMETERS
# -----------------------------------------------------------
CONF_THRESHOLD = 0.4          # YOLO detection confidence
ANGLE_WINDOW = 5              # smoothing window for angle
MIN_TURN_ANGLE_DEG = 25       # angle change to qualify as a turn
MIN_FRAMES_BETWEEN_TURNS = 10 # avoid double-counting turns
BUFFER_SIZE = 50              # points kept for the trajectory


# -----------------------------------------------------------
# LOAD YOLOv5s MODEL
# -----------------------------------------------------------
print("[INFO] Loading YOLOv5s model...")
model = torch.hub.load("ultralytics/yolov5", "yolov5s", pretrained=True)
model.conf = CONF_THRESHOLD


# -----------------------------------------------------------
# OPEN VIDEO SOURCE
# -----------------------------------------------------------
print(f"[INFO] Opening video source: {VIDEO_SOURCE}")
cap = cv2.VideoCapture(VIDEO_SOURCE)

if not cap.isOpened():
    print("[ERROR] Cannot open video source.")
    exit(1)

fps = cap.get(cv2.CAP_PROP_FPS)
if fps == 0 or fps != fps:  # NaN check
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


# -----------------------------------------------------------
# TURN DETECTION FUNCTION
# -----------------------------------------------------------
def detect_turn(angle_list):
    """Return True if a new turn is detected based on angle change."""
    global last_turn_frame, frame_idx

    if len(angle_list) < 5:
        return False

    recent = np.array(angle_list)[-10:]

    if len(recent) < 3:
        return False

    prev_a = recent[-3]
    curr_a = recent[-2]
    next_a = recent[-1]

    # Look for a slope change → potential turn
    if (curr_a - prev_a) * (next_a - curr_a) < 0:

        angle_diff = abs(curr_a - prev_a)

        if angle_diff >= math.radians(MIN_TURN_ANGLE_DEG):

            # Avoid detecting multiple times in rapid sequence
            if frame_idx - last_turn_frame >= MIN_FRAMES_BETWEEN_TURNS:
                last_turn_frame = frame_idx
                return True

    return False


# -----------------------------------------------------------
# MAIN LOOP (HEADLESS)
# -----------------------------------------------------------
print("[INFO] Starting real-time turn detection (headless mode)...")

while True:
    ret, frame = cap.read()
    if not ret:
        print("[WARN] Could not read frame. Exiting...")
        break

    # Run YOLOv5 inference
    results = model(frame)
    detections = results.xyxy[0].cpu().numpy()

    # Filter only "person" class (COCO ID: 0)
    persons = [d for d in detections if int(d[5]) == 0]

    cx = cy = None

    if len(persons) > 0:
        # Choose the largest detected person (assumes it's the skier)
        best = max(persons, key=lambda d: (d[2] - d[0]) * (d[3] - d[1]))
        x1, y1, x2, y2, conf, cls = best
        x1, y1, x2, y2 = map(int, [x1, y1, x2, y2])

        cx = (x1 + x2) / 2
        cy = (y1 + y2) / 2

    # Update trajectory and angle history
    if cx is not None:
        trajectory.append((cx, cy))

        if len(trajectory) >= 2:
            (px, py), (nx, ny) = trajectory[-2], trajectory[-1]
            dx = nx - px
            dy = ny - py
            angle = math.atan2(dy, dx)

            angles_smooth.append(angle)

            # Smooth the angle curve
            if len(angles_smooth) >= ANGLE_WINDOW:
                window = list(angles_smooth)[-ANGLE_WINDOW:]  # FIXED deque slicing
                smoothed = sum(window) / len(window)

                # Replace the last angle with the smoothed one
                angles_smooth.pop()
                angles_smooth.append(smoothed)

            # Detect a turn
            if detect_turn(list(angles_smooth)):
                turn_count += 1
                timestamp = time.time() - start_time
                print(f"[TURN] frame={frame_idx}, time={timestamp:.2f}s, total_turns={turn_count}")

    frame_idx += 1


# -----------------------------------------------------------
# CLEANUP
# -----------------------------------------------------------
cap.release()
print(f"[INFO] Total turns detected: {turn_count}")
