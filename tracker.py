import os
import math
import time
from collections import deque

import cv2
import numpy as np
from ultralytics import YOLO
from ultralytics.utils.checks import check_yaml
import json


# -----------------------------------------------------------
# CONFIGURATION
# -----------------------------------------------------------

VIDEO_SOURCE = os.getenv("VIDEO_SOURCE", "/app/data/input.mp4")

try:
    VIDEO_SOURCE = int(VIDEO_SOURCE)  # webcam index
except ValueError:
    pass  # treat as path or URL

DATA_DIR = "/app/data"
OUTPUT_DIR = os.path.join(DATA_DIR, "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

OUTPUT_VIDEO_PATH = os.path.join(OUTPUT_DIR, "output.mp4")

# Turn detection parameters
CONF_THRESHOLD = 0.4
ANGLE_WINDOW = 5
MIN_TURN_ANGLE_DEG = 45          # minimum turn angle (deg)
MIN_TURN_SPEED_DEG_PER_S = 25    # minimum angular speed (deg/s)
TURN_SUSTAIN_FRAMES = 6          # frames in which direction must be consistent
MIN_FRAMES_BETWEEN_TURNS = 15    # per-surfer anti-spam
BUFFER_SIZE = 70                  # per-surfer trajectory buffer


# -----------------------------------------------------------
# LOAD YOLOv8 MODEL + BoTSORT CONFIG
# -----------------------------------------------------------

print("[INFO] Loading YOLOv8 model...")
model = YOLO("yolov8n.pt")
print("[INFO] YOLOv8 loaded.")

# Load BoTSORT tracker config from local YAML
BOT_SORT_YAML_PATH = "/app/botsort.yaml"
tracker_cfg = check_yaml(BOT_SORT_YAML_PATH)
print(f"[INFO] Using BoTSORT config: {BOT_SORT_YAML_PATH}")


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
    fps = 25.0

frame_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
frame_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

print(f"[INFO] Resolution: {frame_w}x{frame_h}, FPS: {fps}")


# -----------------------------------------------------------
# OUTPUT VIDEO WRITER
# -----------------------------------------------------------

fourcc = cv2.VideoWriter_fourcc(*"mp4v")
out = cv2.VideoWriter(OUTPUT_VIDEO_PATH, fourcc, fps, (frame_w, frame_h))

print(f"[INFO] Exporting video → {OUTPUT_VIDEO_PATH}")


# -----------------------------------------------------------
# PER-SURFER STATE (track_id from BoTSORT)
# -----------------------------------------------------------

# track_id → state
# state = {
#   "trajectory": deque[(cx, cy)],
#   "angles": deque[float],
#   "timestamps": deque[float],
#   "turn_count": int,
#   "last_turn_frame": int,
#   "events": [ ... ],
# }

track_states = {}
frame_idx = 0
start_time = time.time()


# -----------------------------------------------------------
# TURN DETECTION (PER-SURFER)
# -----------------------------------------------------------

def detect_turn(angles, times, last_turn_frame, current_frame_idx):
    """
    Robust turn detector:
      - requires consistent angular direction
      - requires minimum angle magnitude
      - requires minimum angular speed
      - per-track anti-spam
    angles, times are plain Python lists here.
    """
    if len(angles) < 12:
        return False, last_turn_frame, None, None, None

    window = np.array(angles[-12:])
    t = np.array(times[-12:])

    dtheta = np.diff(window)
    dt = np.diff(t)
    dt[dt == 0] = 1e-6
    angular_speed = np.abs(dtheta / dt)

    # 1) Sustained turning direction
    recent_signs = np.sign(dtheta[-TURN_SUSTAIN_FRAMES:])
    sustained = np.sum(recent_signs == recent_signs[-1]) >= (TURN_SUSTAIN_FRAMES - 1)
    if not sustained:
        return False, last_turn_frame, None, None, None

    # 2) Angle magnitude over sustain window
    angle_change = window[-1] - window[-TURN_SUSTAIN_FRAMES]
    abs_angle = abs(angle_change)
    if abs_angle < math.radians(MIN_TURN_ANGLE_DEG):
        return False, last_turn_frame, None, None, None

    # 3) Angular speed threshold
    if np.mean(angular_speed[-TURN_SUSTAIN_FRAMES:]) < math.radians(MIN_TURN_SPEED_DEG_PER_S):
        return False, last_turn_frame, None, None, None

    # 4) Anti-spam (per surfer)
    if current_frame_idx - last_turn_frame < MIN_FRAMES_BETWEEN_TURNS:
        return False, last_turn_frame, None, None, None

    new_last_turn_frame = current_frame_idx

    # Direction of the turn
    direction = "left" if angle_change > 0 else "right"

    # Severity
    angle_deg = math.degrees(abs_angle)
    if angle_deg < 60:
        severity = "mild"
    elif angle_deg < 90:
        severity = "medium"
    else:
        severity = "strong"

    return True, new_last_turn_frame, direction, severity, angle_deg


# -----------------------------------------------------------
# MAIN LOOP
# -----------------------------------------------------------

print("[INFO] Starting multi-surfer tracking with BoTSORT...")

while True:
    ret, frame = cap.read()
    if not ret:
        print("[WARN] End of video.")
        break

    # YOLOv8 tracking with BoTSORT (via YAML config)
    results = model.track(
        frame,
        persist=True,
        tracker=tracker_cfg,
        conf=CONF_THRESHOLD,
        verbose=False,
    )

    any_turn_detected = False

    if not results:
        out.write(frame)
        frame_idx += 1
        continue

    result = results[0]

    if not result.boxes:
        out.write(frame)
        frame_idx += 1
        continue

    boxes_xyxy = result.boxes.xyxy.cpu().numpy()
    classes = result.boxes.cls.int().cpu().tolist()
    ids = result.boxes.id

    if ids is None:
        out.write(frame)
        frame_idx += 1
        continue

    track_ids = ids.int().cpu().tolist()

    # -------------------------------------------------------
    # PROCESS EACH DETECTED PERSON (SURFER)
    # -------------------------------------------------------
    for box, cls, track_id in zip(boxes_xyxy, classes, track_ids):
        # Keep only "person" class
        if cls != 0:
            continue

        x1, y1, x2, y2 = box
        cx = (x1 + x2) / 2.0
        cy = (y1 + y2) / 2.0

        # Get or create state for this surfer (track_id from BoTSORT)
        state = track_states.get(track_id)
        if state is None:
            # Create directory structure for this surfer
            surfer_dir = os.path.join(OUTPUT_DIR, "elements", str(track_id))
            pictures_dir = os.path.join(surfer_dir, "pictures")
            os.makedirs(pictures_dir, exist_ok=True)

            state = {
                "trajectory": deque(maxlen=BUFFER_SIZE),
                "angles": deque(maxlen=BUFFER_SIZE),
                "timestamps": deque(maxlen=BUFFER_SIZE),
                "turn_count": 0,
                "last_turn_frame": -9999,
                "events": [],
                "surfer_dir": surfer_dir,
                "pictures_dir": pictures_dir,
            }
            track_states[track_id] = state

        trajectory = state["trajectory"]
        angles = state["angles"]
        timestamps = state["timestamps"]

        # Update trajectory & timestamps
        trajectory.append((cx, cy))
        timestamps.append(time.time())

        if len(trajectory) >= 2:
            (px, py), (nx, ny) = trajectory[-2], trajectory[-1]
            dx = nx - px
            dy = ny - py

            # Motion angle
            angle = math.atan2(dy, dx)
            angles.append(angle)

            # Smooth angle with sliding window (convert deque → list for slicing)
            if len(angles) >= ANGLE_WINDOW:
                window = list(angles)[-ANGLE_WINDOW:]
                smoothed = sum(window) / len(window)
                angles.pop()
                angles.append(smoothed)

            # Turn detection for this surfer
            detected, new_last_turn_frame, direction, severity, angle_deg = detect_turn(
                list(angles),
                list(timestamps),
                state["last_turn_frame"],
                frame_idx,
            )

            if detected:
                state["last_turn_frame"] = new_last_turn_frame
                state["turn_count"] += 1
                any_turn_detected = True

                timestamp = time.time() - start_time

                event = {
                    "frame": frame_idx,
                    "timestamp": timestamp,
                    "direction": direction,
                    "severity": severity,
                    "angle_degrees": angle_deg,
                }
                state["events"].append(event)

                # Save frame capture at the moment of turn detection
                picture_path = os.path.join(state["pictures_dir"], f"{frame_idx}.png")
                cv2.imwrite(picture_path, frame)

                print(
                    f"[TURN] surfer_id={track_id}, frame={frame_idx}, "
                    f"time={timestamp:.2f}s, total_turns={state['turn_count']}, "
                    f"{direction}, {severity}, {angle_deg:.1f}°"
                )

        # ---------------------------------------------------
        # DRAW OVERLAY FOR THIS SURFER (track_id)
        # ---------------------------------------------------
        x1i, y1i, x2i, y2i = map(int, [x1, y1, x2, y2])

        # bounding box
        cv2.rectangle(frame, (x1i, y1i), (x2i, y2i), (0, 255, 0), 2)

        label_id = f"ID: {track_id}"
        label_turns = f"Turns: {state['turn_count']}"

        (tw1, th1), _ = cv2.getTextSize(label_id, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
        (tw2, th2), _ = cv2.getTextSize(label_turns, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)

        box_w = max(tw1, tw2) + 16
        box_h = th1 + th2 + 20

        overlay_x1 = x1i
        overlay_y1 = max(0, y1i - box_h)
        overlay_x2 = overlay_x1 + box_w
        overlay_y2 = overlay_y1 + box_h

        cv2.rectangle(
            frame,
            (overlay_x1, overlay_y1),
            (overlay_x2, overlay_y2),
            (0, 255, 0),
            -1,
        )

        cv2.putText(
            frame,
            label_id,
            (overlay_x1 + 8, overlay_y1 + th1 + 4),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 0, 0),
            2,
        )

        cv2.putText(
            frame,
            label_turns,
            (overlay_x1 + 8, overlay_y1 + th1 + th2 + 12),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 0, 0),
            2,
        )

    # Global TURN! flash if any surfer turned in this frame
    if any_turn_detected:
        cv2.putText(
            frame,
            "TURN!",
            (frame_w // 2 - 80, 80),
            cv2.FONT_HERSHEY_SIMPLEX,
            2,
            (0, 0, 255),
            4,
        )

    out.write(frame)
    frame_idx += 1


# -----------------------------------------------------------
# EXPORT PER-SURFER JSON FILES
# -----------------------------------------------------------

cap.release()
out.release()

print("[INFO] Saving per-surfer JSON files...")

for track_id, state in track_states.items():
    json_path = os.path.join(state["surfer_dir"], "turns.json")
    data = {
        "id": track_id,
        "total_turns": state["turn_count"],
        "events": state["events"],
    }
    with open(json_path, "w") as f:
        json.dump(data, f, indent=4)

    print(f"[INFO] JSON saved for surfer {track_id} → {json_path}")

print(f"[INFO] Final video → {OUTPUT_VIDEO_PATH}")
print(f"[INFO] Total surfers tracked (track IDs): {len(track_states)}")
