import os
import math
import time
import shutil
import subprocess
from collections import deque

import cv2
import numpy as np
from ultralytics import YOLO
from ultralytics.utils.checks import check_yaml
import json


# -----------------------------------------------------------
# VIDEO ROTATION UTILITIES
# -----------------------------------------------------------

def get_video_rotation(video_path):
    """
    Detect rotation metadata from video file using ffprobe.
    Returns rotation angle (0, 90, 180, or 270).
    """
    try:
        # First try: Check rotation tag
        cmd = [
            'ffprobe', '-v', 'error',
            '-select_streams', 'v:0',
            '-show_entries', 'stream_tags=rotate',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            str(video_path)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)

        if result.returncode == 0 and result.stdout.strip():
            rotation = int(result.stdout.strip())
            print(f"[INFO] Detected video rotation metadata (rotate tag): {rotation}°")
            return rotation

        # Second try: Check side_data display matrix
        cmd = [
            'ffprobe', '-v', 'error',
            '-select_streams', 'v:0',
            '-show_entries', 'stream_side_data=rotation',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            str(video_path)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)

        if result.returncode == 0 and result.stdout.strip():
            rotation = int(float(result.stdout.strip()))
            print(f"[INFO] Detected video rotation metadata (side_data): {rotation}°")
            return rotation

    except (subprocess.TimeoutExpired, ValueError, FileNotFoundError) as e:
        print(f"[INFO] Could not detect rotation via ffprobe: {e}")

    print("[INFO] No rotation metadata found, assuming 0°")
    return 0


def rotate_frame(frame, rotation):
    """
    Rotate frame based on rotation angle.
    Rotation metadata indicates how much to rotate for correct display.
    Handles negative angles: -90 = counterclockwise 90°
    """
    # Normalize negative angles to positive equivalents
    rotation = rotation % 360

    if rotation == 0:
        return frame
    elif rotation == 90:
        return cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)
    elif rotation == 180:
        return cv2.rotate(frame, cv2.ROTATE_180)
    elif rotation == 270:
        return cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
    else:
        print(f"[WARN] Unsupported rotation angle: {rotation}°, not rotating")
        return frame


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

# Maneuver detection parameters
CONF_THRESHOLD = 0.4
BUFFER_SIZE = 70                      # per-surfer trajectory buffer
DEBUG_DETECTION = True                # enable debug output for detection
MIN_FRAMES_BETWEEN_MANEUVERS = 15     # per-surfer anti-spam between maneuvers

# Bounding box size filtering (to exclude people too close to camera)
MAX_BOX_WIDTH_RATIO = 0.6             # maximum box width as fraction of frame width (0.0-1.0)
MAX_BOX_HEIGHT_RATIO = 0.6            # maximum box height as fraction of frame height (0.0-1.0)
MIN_BOX_AREA_PIXELS = 400             # minimum box area to track (avoid tiny detections)

# Activity filtering (prevent stationary surfers from being detected)
MIN_MOVEMENT_DISTANCE = 100           # minimum total movement distance (pixels) to be considered active
MIN_ACTIVE_FRAMES = 10                # minimum frames with significant movement to enable detection
MOVEMENT_THRESHOLD_PER_FRAME = 3      # minimum pixel movement per frame to count as "active"

# Trajectory consistency (prevent ID swapping false detections)
MAX_POSITION_JUMP = 150               # maximum pixel jump between frames (to detect ID swaps)
CONSISTENCY_CHECK_FRAMES = 5          # frames to check for trajectory consistency

# Turn detection parameters
ANGLE_WINDOW = 5                      # smoothing window for angle calculation
MIN_TURN_ANGLE_DEG = 45               # minimum angle change to detect a turn
TURN_SUSTAIN_FRAMES = 5               # frames of consistent turning direction
MIN_TURN_SPEED_DEG_PER_S = 25         # minimum angular speed (deg/s)


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

# Detect video rotation metadata (can be overridden with ROTATION env var)
rotation_override = os.getenv("ROTATION")
if rotation_override and rotation_override.strip():
    rotation = int(rotation_override)
    print(f"[INFO] Using manual rotation override: {rotation}°")
else:
    rotation = get_video_rotation(VIDEO_SOURCE)

fps = cap.get(cv2.CAP_PROP_FPS)
if fps == 0 or fps != fps:
    fps = 25.0

frame_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
frame_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

# Normalize rotation and adjust dimensions if video is rotated 90° or 270°
rotation_normalized = rotation % 360
if rotation_normalized in (90, 270):
    frame_w, frame_h = frame_h, frame_w
    print(f"[INFO] Resolution (after {rotation}° rotation): {frame_w}x{frame_h}, FPS: {fps}")
else:
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
#   "maneuver_count": int,
#   "last_maneuver_frame": int,
#   "total_distance": float,
#   "active_frames": int,
#   "is_active": bool,
#   "events": [ ... ],
#   "surfer_dir": str,
#   "pictures_dir": str,
# }

track_states = {}
frame_idx = 0
start_time = time.time()


# -----------------------------------------------------------
# TRAJECTORY CONSISTENCY CHECK
# -----------------------------------------------------------

def is_trajectory_consistent(trajectory):
    """
    Check if trajectory is consistent (no sudden large jumps).
    Large jumps indicate potential ID swap by the tracker.

    Returns: True if consistent, False if likely ID swap
    """
    if len(trajectory) < CONSISTENCY_CHECK_FRAMES:
        return True  # Not enough data yet, assume consistent

    # Check recent positions for large jumps
    recent_positions = list(trajectory)[-CONSISTENCY_CHECK_FRAMES:]

    for i in range(1, len(recent_positions)):
        (x1, y1) = recent_positions[i-1]
        (x2, y2) = recent_positions[i]

        distance = math.sqrt((x2 - x1)**2 + (y2 - y1)**2)

        if distance > MAX_POSITION_JUMP:
            # Large jump detected - likely ID swap
            return False

    return True


# -----------------------------------------------------------
# MANEUVER DETECTION (PER-SURFER)
# -----------------------------------------------------------

def detect_maneuver(trajectory, angles, times, last_maneuver_frame, current_frame_idx, track_id=None):
    """
    Detects generic turns based on trajectory patterns.

    Returns: (detected, new_last_maneuver_frame, maneuver_type, metrics_dict)
    """

    # Anti-spam check first
    if current_frame_idx - last_maneuver_frame < MIN_FRAMES_BETWEEN_MANEUVERS:
        return False, last_maneuver_frame, None, None

    # Check if we have enough data
    if len(angles) < TURN_SUSTAIN_FRAMES + 2:
        return False, last_maneuver_frame, None, None

    # Ensure angles and times have matching lengths
    min_len = min(len(angles), len(times))
    angles_array = np.array(angles[-min_len:])
    t_array = np.array(times[-min_len:])

    # Calculate angle changes
    window = angles_array[-12:]  # Look at last 12 angles
    t = t_array[-12:]  # Take matching timestamps

    dtheta = np.diff(window)
    dt = np.diff(t)
    dt[dt == 0] = 1e-6
    angular_speed = np.abs(dtheta / dt)

    # 1) Check for sustained turning direction
    if len(dtheta) < TURN_SUSTAIN_FRAMES:
        return False, last_maneuver_frame, None, None

    recent_signs = np.sign(dtheta[-TURN_SUSTAIN_FRAMES:])
    sustained = np.sum(recent_signs == recent_signs[-1]) >= (TURN_SUSTAIN_FRAMES - 1)
    if not sustained:
        return False, last_maneuver_frame, None, None

    # 2) Calculate angle magnitude
    angle_change = window[-1] - window[-TURN_SUSTAIN_FRAMES]
    abs_angle = abs(angle_change)
    angle_deg = math.degrees(abs_angle)

    if angle_deg < MIN_TURN_ANGLE_DEG:
        return False, last_maneuver_frame, None, None

    # 3) Check angular speed
    if np.mean(angular_speed[-TURN_SUSTAIN_FRAMES:]) < math.radians(MIN_TURN_SPEED_DEG_PER_S):
        return False, last_maneuver_frame, None, None

    # Turn detected!
    direction = "left" if angle_change > 0 else "right"
    avg_angular_speed_rad = np.mean(angular_speed[-TURN_SUSTAIN_FRAMES:])
    avg_angular_speed_deg = math.degrees(avg_angular_speed_rad)

    if DEBUG_DETECTION and track_id is not None:
        print(f"[TURN DETECTED] ID={track_id}, frame={current_frame_idx}: "
              f"angle={angle_deg:.1f}°, ang_speed={avg_angular_speed_deg:.1f}°/s, "
              f"dir={direction}")

    metrics = {
        "angle_degrees": float(angle_deg),
        "direction": direction,
        "angular_speed_deg_s": float(avg_angular_speed_deg),
    }

    return True, current_frame_idx, "turn", metrics


# -----------------------------------------------------------
# MAIN LOOP
# -----------------------------------------------------------

print("[INFO] Starting multi-surfer tracking with BoTSORT...")

while True:
    ret, frame = cap.read()
    if not ret:
        print("[WARN] End of video.")
        break

    # Apply rotation if needed
    frame = rotate_frame(frame, rotation)

    # YOLOv8 tracking with BoTSORT (via YAML config)
    results = model.track(
        frame,
        persist=True,
        tracker=tracker_cfg,
        conf=CONF_THRESHOLD,
        verbose=False,
    )

    detected_maneuver_this_frame = None  # Track which maneuver was detected

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

        # Apply bounding box size filtering
        box_width = x2 - x1
        box_height = y2 - y1
        box_area = box_width * box_height

        width_ratio = box_width / frame_w
        height_ratio = box_height / frame_h

        # Skip if box is too large (person too close to camera)
        if width_ratio > MAX_BOX_WIDTH_RATIO or height_ratio > MAX_BOX_HEIGHT_RATIO:
            if DEBUG_DETECTION:
                print(f"[FILTER] Skipping track_id={track_id}: Box too large "
                      f"(w={width_ratio:.2f}, h={height_ratio:.2f}), likely not a surfer")
            continue

        # Skip if box is too small (noise or very distant)
        if box_area < MIN_BOX_AREA_PIXELS:
            if DEBUG_DETECTION:
                print(f"[FILTER] Skipping track_id={track_id}: Box too small "
                      f"(area={box_area:.0f}px), likely noise")
            continue

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
                "maneuver_count": 0,
                "last_maneuver_frame": -9999,
                "total_distance": 0.0,
                "active_frames": 0,
                "is_active": False,
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

        # Track activity (movement distance and active frames)
        if len(trajectory) >= 2:
            (px, py), (nx, ny) = trajectory[-2], trajectory[-1]
            dx = nx - px
            dy = ny - py

            # Calculate distance moved this frame
            frame_distance = math.sqrt(dx**2 + dy**2)

            # Check for ID swap (large position jump)
            if frame_distance > MAX_POSITION_JUMP:
                if DEBUG_DETECTION:
                    print(f"[ID SWAP] Surfer {track_id}: Large jump detected ({frame_distance:.1f}px), "
                          f"resetting activity tracking")
                # Reset activity tracking - likely ID swap
                state["total_distance"] = 0.0
                state["active_frames"] = 0
                state["is_active"] = False
            else:
                # Normal movement - update tracking
                state["total_distance"] += frame_distance

                # Count as active frame if significant movement
                if frame_distance >= MOVEMENT_THRESHOLD_PER_FRAME:
                    state["active_frames"] += 1

                # Update active status
                if (state["total_distance"] >= MIN_MOVEMENT_DISTANCE and
                    state["active_frames"] >= MIN_ACTIVE_FRAMES):
                    if not state["is_active"]:
                        state["is_active"] = True
                        if DEBUG_DETECTION:
                            print(f"[ACTIVE] Surfer {track_id} is now active: "
                                  f"distance={state['total_distance']:.1f}px, "
                                  f"active_frames={state['active_frames']}")

            # Calculate motion angle
            angle = math.atan2(dy, dx)
            angles.append(angle)

            # Smooth angle with sliding window
            if len(angles) >= ANGLE_WINDOW:
                window = list(angles)[-ANGLE_WINDOW:]
                smoothed = sum(window) / len(window)
                angles.pop()
                angles.append(smoothed)

        # Maneuver detection for this surfer (only if active AND trajectory is consistent)
        if (state["is_active"] and
            len(trajectory) >= TURN_SUSTAIN_FRAMES + 2):

            # Check trajectory consistency to prevent false detections from ID swaps
            if not is_trajectory_consistent(trajectory):
                if DEBUG_DETECTION:
                    print(f"[WARNING] Surfer {track_id}: Inconsistent trajectory detected (possible ID swap), "
                          f"skipping detection this frame")
            else:
                detected, new_last_maneuver_frame, maneuver_type, metrics = detect_maneuver(
                    list(trajectory),
                    list(angles),
                    list(timestamps),
                    state["last_maneuver_frame"],
                    frame_idx,
                    track_id=track_id,
                )

                if detected:
                    state["last_maneuver_frame"] = new_last_maneuver_frame
                    state["maneuver_count"] += 1
                    detected_maneuver_this_frame = True  # Track that a turn was detected

                    timestamp = time.time() - start_time

                    event = {
                        "frame": frame_idx,
                        "timestamp": timestamp,
                        "maneuver_type": maneuver_type,
                        "metrics": metrics,
                    }
                    state["events"].append(event)

                    # Save frame capture at the moment of maneuver detection
                    picture_path = os.path.join(state["pictures_dir"], f"{frame_idx}.png")
                    cv2.imwrite(picture_path, frame)

                    print(
                        f"[TURN] surfer_id={track_id}, frame={frame_idx}, "
                        f"time={timestamp:.2f}s, total_turns={state['maneuver_count']}, "
                        f"angle={metrics['angle_degrees']:.1f}°, dir={metrics['direction']}"
                    )

        # ---------------------------------------------------
        # DRAW OVERLAY FOR THIS SURFER (track_id)
        # ---------------------------------------------------
        x1i, y1i, x2i, y2i = map(int, [x1, y1, x2, y2])

        # bounding box
        cv2.rectangle(frame, (x1i, y1i), (x2i, y2i), (0, 255, 0), 2)

        label_id = f"ID: {track_id}"
        label_maneuvers = f"Turns: {state['maneuver_count']}"

        (tw1, th1), _ = cv2.getTextSize(label_id, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
        (tw2, th2), _ = cv2.getTextSize(label_maneuvers, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)

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
            label_maneuvers,
            (overlay_x1 + 8, overlay_y1 + th1 + th2 + 12),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 0, 0),
            2,
        )

    # Global turn flash if any surfer performed a turn in this frame
    if detected_maneuver_this_frame:
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

print("[INFO] Processing per-surfer data...")

surfers_with_maneuvers = 0
surfers_removed = 0
inactive_surfers = 0

for track_id, state in track_states.items():
    if state["maneuver_count"] == 0:
        # Remove surfer directory if no turns detected
        surfer_dir = state["surfer_dir"]
        if os.path.exists(surfer_dir):
            shutil.rmtree(surfer_dir)
            reason = "inactive" if not state["is_active"] else "no turns"
            print(f"[INFO] Removed surfer {track_id} ({reason}: "
                  f"distance={state['total_distance']:.1f}px, "
                  f"active_frames={state['active_frames']})")
            surfers_removed += 1
            if not state["is_active"]:
                inactive_surfers += 1
    else:
        # Save JSON only for surfers with turns
        json_path = os.path.join(state["surfer_dir"], "turns.json")
        data = {
            "id": track_id,
            "total_turns": state["maneuver_count"],
            "events": state["events"],
        }
        with open(json_path, "w") as f:
            json.dump(data, f, indent=4)

        print(f"[INFO] JSON saved for surfer {track_id} → {json_path} "
              f"({state['maneuver_count']} turns)")
        surfers_with_maneuvers += 1

print(f"[INFO] Final video → {OUTPUT_VIDEO_PATH}")
print(f"[INFO] Total surfers tracked: {len(track_states)}")
print(f"[INFO] Surfers with turns: {surfers_with_maneuvers}")
print(f"[INFO] Surfers removed: {surfers_removed} (inactive: {inactive_surfers})")
