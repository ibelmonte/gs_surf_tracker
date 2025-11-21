import os
import math
import time
import shutil
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

# Maneuver detection parameters
CONF_THRESHOLD = 0.4
BUFFER_SIZE = 70                      # per-surfer trajectory buffer
DEBUG_DETECTION = True                # enable debug output for detection
MIN_FRAMES_BETWEEN_MANEUVERS = 15     # per-surfer anti-spam between maneuvers

# Activity filtering (prevent stationary surfers from being detected)
MIN_MOVEMENT_DISTANCE = 100           # minimum total movement distance (pixels) to be considered active
MIN_ACTIVE_FRAMES = 10                # minimum frames with significant movement to enable detection
MOVEMENT_THRESHOLD_PER_FRAME = 3      # minimum pixel movement per frame to count as "active"

# Trajectory consistency (prevent ID swapping false detections)
MAX_POSITION_JUMP = 150               # maximum pixel jump between frames (to detect ID swaps)
CONSISTENCY_CHECK_FRAMES = 5          # frames to check for trajectory consistency

# Drop detection parameters (initial descent after catching wave)
MIN_DROP_DISTANCE_PIXELS = 15         # minimum vertical descent in pixels
MIN_DROP_VELOCITY_PX_PER_S = 8        # minimum downward speed (pixels/second)
DROP_SUSTAIN_FRAMES = 4               # frames of sustained downward movement

# Turn detection parameters (bottom turn, snap, cutback)
ANGLE_WINDOW = 5                      # smoothing window for angle calculation
MIN_TURN_ANGLE_DEG = 45               # minimum angle change to detect any turn
TURN_SUSTAIN_FRAMES = 5               # frames of consistent turning direction
MIN_TURN_SPEED_DEG_PER_S = 25         # minimum angular speed (deg/s)

# Maneuver classification based on characteristics (not just position)
# SNAP: Explosive, sharp turn (high speed + sharp angle)
MIN_SNAP_ANGLE_DEG = 55               # minimum angle for snap
MIN_SNAP_SPEED_DEG_PER_S = 40         # high angular speed = explosive/snap

# CUTBACK: Large directional change (turning back toward wave)
MIN_CUTBACK_ANGLE_DEG = 85            # large angle change (was 120, too high)

# BOTTOM TURN: Default turn that doesn't fit snap/cutback criteria
MIN_BOTTOM_TURN_ANGLE_DEG = 45        # minimum angle for bottom turn


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
#   "maneuver_count": int,
#   "last_maneuver_frame": int,
#   "drop_detected": bool,
#   "min_y": float,
#   "max_y": float,
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

def detect_maneuver(trajectory, angles, times, last_maneuver_frame, current_frame_idx,
                    drop_detected, min_y, max_y, track_id=None):
    """
    Detects surfing maneuvers based on trajectory patterns.
    Detects: Drop, Bottom Turn, Snap, Cutback

    Returns: (detected, new_last_maneuver_frame, maneuver_type, metrics_dict, new_drop_detected)
    """

    # Anti-spam check first
    if current_frame_idx - last_maneuver_frame < MIN_FRAMES_BETWEEN_MANEUVERS:
        return False, last_maneuver_frame, None, None, drop_detected

    # --- PRIORITY 1: DROP DETECTION (only if not yet detected) ---
    if not drop_detected and len(trajectory) >= DROP_SUSTAIN_FRAMES + 2:
        # Extract Y positions from trajectory
        y_positions = [pos[1] for pos in trajectory]
        y_array = np.array(y_positions)
        t_array = np.array(times)

        # Calculate vertical velocity
        dy = np.diff(y_array)
        dt = np.diff(t_array)
        dt[dt == 0] = 1e-6
        vertical_velocity = dy / dt

        if len(vertical_velocity) >= DROP_SUSTAIN_FRAMES:
            recent_velocity = vertical_velocity[-DROP_SUSTAIN_FRAMES:]
            recent_dy = dy[-DROP_SUSTAIN_FRAMES:]

            downward_frames = np.sum(recent_dy > 0)
            total_drop_distance = np.sum(recent_dy[recent_dy > 0])
            avg_velocity = np.mean(np.abs(recent_velocity))

            # Check all drop criteria
            if (downward_frames >= DROP_SUSTAIN_FRAMES - 1 and
                total_drop_distance >= MIN_DROP_DISTANCE_PIXELS and
                avg_velocity >= MIN_DROP_VELOCITY_PX_PER_S):

                # Drop detected!
                max_velocity = np.max(np.abs(recent_velocity))
                duration = t_array[-1] - t_array[-DROP_SUSTAIN_FRAMES]

                metrics = {
                    "distance_pixels": float(total_drop_distance),
                    "max_velocity_px_s": float(max_velocity),
                    "avg_velocity_px_s": float(avg_velocity),
                    "duration_seconds": float(duration),
                }

                if DEBUG_DETECTION and track_id is not None:
                    print(f"[DROP DETECTED] ID={track_id}, frame={current_frame_idx}, "
                          f"distance={total_drop_distance:.1f}px, vel={avg_velocity:.1f}px/s")

                return True, current_frame_idx, "drop", metrics, True  # Set drop_detected to True

    # --- PRIORITY 2: TURN DETECTION (Bottom Turn, Snap, Cutback) ---
    if len(angles) < TURN_SUSTAIN_FRAMES + 2:
        return False, last_maneuver_frame, None, None, drop_detected

    # Ensure angles and times have matching lengths
    # (angles can be shorter than times since they're derived from trajectory pairs)
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
        return False, last_maneuver_frame, None, None, drop_detected

    recent_signs = np.sign(dtheta[-TURN_SUSTAIN_FRAMES:])
    sustained = np.sum(recent_signs == recent_signs[-1]) >= (TURN_SUSTAIN_FRAMES - 1)
    if not sustained:
        return False, last_maneuver_frame, None, None, drop_detected

    # 2) Calculate angle magnitude
    angle_change = window[-1] - window[-TURN_SUSTAIN_FRAMES]
    abs_angle = abs(angle_change)
    angle_deg = math.degrees(abs_angle)

    if angle_deg < MIN_TURN_ANGLE_DEG:
        return False, last_maneuver_frame, None, None, drop_detected

    # 3) Check angular speed
    if np.mean(angular_speed[-TURN_SUSTAIN_FRAMES:]) < math.radians(MIN_TURN_SPEED_DEG_PER_S):
        return False, last_maneuver_frame, None, None, drop_detected

    # --- CLASSIFY TURN TYPE based on angle and speed (not position) ---

    # Direction
    direction = "left" if angle_change > 0 else "right"

    # Calculate average angular speed
    avg_angular_speed_rad = np.mean(angular_speed[-TURN_SUSTAIN_FRAMES:])
    avg_angular_speed_deg = math.degrees(avg_angular_speed_rad)

    # Enhanced debug output
    if DEBUG_DETECTION and track_id is not None:
        current_y = trajectory[-1][1]
        y_range = max_y - min_y if max_y > min_y else 1.0
        relative_position = (current_y - min_y) / y_range
        print(f"[TURN ANALYSIS] ID={track_id}, frame={current_frame_idx}: "
              f"angle={angle_deg:.1f}°, ang_speed={avg_angular_speed_deg:.1f}°/s, "
              f"pos={relative_position:.2f}")

    # Classify maneuver based on characteristics
    maneuver_type = None

    # Priority 1: SNAP - Explosive turn (high speed + sharp angle)
    if (avg_angular_speed_deg >= MIN_SNAP_SPEED_DEG_PER_S and
        angle_deg >= MIN_SNAP_ANGLE_DEG):
        maneuver_type = "snap"
        if DEBUG_DETECTION and track_id is not None:
            print(f"  → SNAP (speed {avg_angular_speed_deg:.1f}°/s >= {MIN_SNAP_SPEED_DEG_PER_S}°/s, "
                  f"angle {angle_deg:.1f}° >= {MIN_SNAP_ANGLE_DEG}°)")

    # Priority 2: CUTBACK - Large directional change
    elif angle_deg >= MIN_CUTBACK_ANGLE_DEG:
        maneuver_type = "cutback"
        if DEBUG_DETECTION and track_id is not None:
            print(f"  → CUTBACK (angle {angle_deg:.1f}° >= {MIN_CUTBACK_ANGLE_DEG}°)")

    # Priority 3: BOTTOM TURN - Standard turn
    elif angle_deg >= MIN_BOTTOM_TURN_ANGLE_DEG:
        maneuver_type = "bottom_turn"
        if DEBUG_DETECTION and track_id is not None:
            print(f"  → BOTTOM_TURN (angle {angle_deg:.1f}° >= {MIN_BOTTOM_TURN_ANGLE_DEG}°)")

    else:
        # Angle too small, not classified
        if DEBUG_DETECTION and track_id is not None:
            print(f"  → NOT classified (angle {angle_deg:.1f}° < {MIN_BOTTOM_TURN_ANGLE_DEG}°)")
        return False, last_maneuver_frame, None, None, drop_detected

    # Turn detected and classified!
    current_y = trajectory[-1][1]
    y_range = max_y - min_y if max_y > min_y else 1.0
    relative_position = (current_y - min_y) / y_range

    metrics = {
        "angle_degrees": float(angle_deg),
        "direction": direction,
        "angular_speed_deg_s": float(avg_angular_speed_deg),
        "position_relative": float(relative_position),
    }

    return True, current_frame_idx, maneuver_type, metrics, drop_detected


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
                "drop_detected": False,
                "min_y": float('inf'),
                "max_y": float('-inf'),
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

        # Update min/max Y for position-based classification
        state["min_y"] = min(state["min_y"], cy)
        state["max_y"] = max(state["max_y"], cy)

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
            len(trajectory) >= max(DROP_SUSTAIN_FRAMES + 2, TURN_SUSTAIN_FRAMES + 2)):

            # Check trajectory consistency to prevent false detections from ID swaps
            if not is_trajectory_consistent(trajectory):
                if DEBUG_DETECTION:
                    print(f"[WARNING] Surfer {track_id}: Inconsistent trajectory detected (possible ID swap), "
                          f"skipping detection this frame")
            else:
                detected, new_last_maneuver_frame, maneuver_type, metrics, new_drop_detected = detect_maneuver(
                    list(trajectory),
                    list(angles),
                    list(timestamps),
                    state["last_maneuver_frame"],
                    frame_idx,
                    state["drop_detected"],
                    state["min_y"],
                    state["max_y"],
                    track_id=track_id,
                )

                if detected:
                    state["last_maneuver_frame"] = new_last_maneuver_frame
                    state["maneuver_count"] += 1
                    state["drop_detected"] = new_drop_detected
                    detected_maneuver_this_frame = maneuver_type  # Track the maneuver type for overlay

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

                    # Print appropriate message based on maneuver type
                    if maneuver_type == "drop":
                        print(
                            f"[{maneuver_type.upper()}] surfer_id={track_id}, frame={frame_idx}, "
                            f"time={timestamp:.2f}s, total_maneuvers={state['maneuver_count']}, "
                            f"distance={metrics['distance_pixels']:.1f}px, "
                            f"max_vel={metrics['max_velocity_px_s']:.1f}px/s"
                        )
                    else:
                        print(
                            f"[{maneuver_type.upper()}] surfer_id={track_id}, frame={frame_idx}, "
                            f"time={timestamp:.2f}s, total_maneuvers={state['maneuver_count']}, "
                            f"angle={metrics['angle_degrees']:.1f}°, dir={metrics['direction']}"
                        )

        # ---------------------------------------------------
        # DRAW OVERLAY FOR THIS SURFER (track_id)
        # ---------------------------------------------------
        x1i, y1i, x2i, y2i = map(int, [x1, y1, x2, y2])

        # bounding box
        cv2.rectangle(frame, (x1i, y1i), (x2i, y2i), (0, 255, 0), 2)

        label_id = f"ID: {track_id}"
        label_maneuvers = f"Maneuvers: {state['maneuver_count']}"

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

    # Global maneuver flash if any surfer performed a maneuver in this frame
    if detected_maneuver_this_frame:
        # Map maneuver types to display text
        maneuver_display = {
            "drop": "DROP!",
            "bottom_turn": "BOTTOM TURN!",
            "snap": "SNAP!",
            "cutback": "CUTBACK!",
        }
        display_text = maneuver_display.get(detected_maneuver_this_frame, "MANEUVER!")

        cv2.putText(
            frame,
            display_text,
            (frame_w // 2 - 120, 80),
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
        # Remove surfer directory if no maneuvers detected
        surfer_dir = state["surfer_dir"]
        if os.path.exists(surfer_dir):
            shutil.rmtree(surfer_dir)
            reason = "inactive" if not state["is_active"] else "no maneuvers"
            print(f"[INFO] Removed surfer {track_id} ({reason}: "
                  f"distance={state['total_distance']:.1f}px, "
                  f"active_frames={state['active_frames']})")
            surfers_removed += 1
            if not state["is_active"]:
                inactive_surfers += 1
    else:
        # Save JSON only for surfers with maneuvers
        json_path = os.path.join(state["surfer_dir"], "turns.json")
        data = {
            "id": track_id,
            "total_maneuvers": state["maneuver_count"],
            "events": state["events"],
        }
        with open(json_path, "w") as f:
            json.dump(data, f, indent=4)

        print(f"[INFO] JSON saved for surfer {track_id} → {json_path} "
              f"({state['maneuver_count']} maneuvers)")
        surfers_with_maneuvers += 1

print(f"[INFO] Final video → {OUTPUT_VIDEO_PATH}")
print(f"[INFO] Total surfers tracked: {len(track_states)}")
print(f"[INFO] Surfers with maneuvers: {surfers_with_maneuvers}")
print(f"[INFO] Surfers removed: {surfers_removed} (inactive: {inactive_surfers})")
