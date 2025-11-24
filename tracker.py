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
import mediapipe as mp


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

# Initialize MediaPipe Pose
print("[INFO] Initializing MediaPipe Pose...")
mp_pose = mp.solutions.pose
pose_detector = mp_pose.Pose(
    static_image_mode=False,
    model_complexity=1,  # 0=Lite, 1=Full, 2=Heavy
    enable_segmentation=False,
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5
)
print("[INFO] MediaPipe Pose initialized.")


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
#   "pose_features_history": deque[dict],  # history of pose features
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
# POSE FEATURE EXTRACTION
# -----------------------------------------------------------

def extract_pose_features(pose_landmarks, frame_w, frame_h):
    """
    Extract surf-relevant features from MediaPipe pose landmarks.

    Returns dict with:
    - body_lean: angle of body lean (degrees, 0=vertical)
    - knee_bend: average knee bend angle (degrees)
    - arm_extension: average arm extension ratio (0-1)
    - center_mass_y: vertical position of center of mass (normalized 0-1)
    - shoulder_rotation: shoulder line angle vs horizontal (degrees)
    - hip_shoulder_alignment: alignment between hips and shoulders
    """
    if not pose_landmarks:
        return None

    landmarks = pose_landmarks.landmark

    # Helper to get landmark coordinates (normalized)
    def get_landmark(idx):
        lm = landmarks[idx]
        return np.array([lm.x, lm.y, lm.z]), lm.visibility

    # Key landmarks (MediaPipe Pose indices)
    LEFT_SHOULDER = 11
    RIGHT_SHOULDER = 12
    LEFT_HIP = 23
    RIGHT_HIP = 24
    LEFT_KNEE = 25
    RIGHT_KNEE = 26
    LEFT_ANKLE = 27
    RIGHT_ANKLE = 28
    LEFT_ELBOW = 13
    RIGHT_ELBOW = 14
    LEFT_WRIST = 15
    RIGHT_WRIST = 16

    features = {}

    try:
        # Get key points
        l_shoulder, l_shoulder_vis = get_landmark(LEFT_SHOULDER)
        r_shoulder, r_shoulder_vis = get_landmark(RIGHT_SHOULDER)
        l_hip, l_hip_vis = get_landmark(LEFT_HIP)
        r_hip, r_hip_vis = get_landmark(RIGHT_HIP)
        l_knee, l_knee_vis = get_landmark(LEFT_KNEE)
        r_knee, r_knee_vis = get_landmark(RIGHT_KNEE)
        l_ankle, l_ankle_vis = get_landmark(LEFT_ANKLE)
        r_ankle, r_ankle_vis = get_landmark(RIGHT_ANKLE)
        l_elbow, l_elbow_vis = get_landmark(LEFT_ELBOW)
        r_elbow, r_elbow_vis = get_landmark(RIGHT_ELBOW)
        l_wrist, l_wrist_vis = get_landmark(LEFT_WRIST)
        r_wrist, r_wrist_vis = get_landmark(RIGHT_WRIST)

        # Calculate center points
        shoulder_center = (l_shoulder + r_shoulder) / 2
        hip_center = (l_hip + r_hip) / 2

        # 1. Body lean angle (torso angle from vertical)
        torso_vec = shoulder_center - hip_center
        vertical_vec = np.array([0, -1, 0])  # Y points down in image coords

        # Angle in 2D (ignore z)
        torso_2d = torso_vec[:2]
        vertical_2d = vertical_vec[:2]

        if np.linalg.norm(torso_2d) > 0:
            cos_angle = np.dot(torso_2d, vertical_2d) / (np.linalg.norm(torso_2d) * np.linalg.norm(vertical_2d))
            cos_angle = np.clip(cos_angle, -1, 1)
            body_lean = math.degrees(math.acos(cos_angle))
        else:
            body_lean = 0

        features["body_lean"] = body_lean

        # 2. Knee bend angles
        def calculate_angle(a, b, c):
            """Calculate angle at point b formed by points a-b-c"""
            ba = a - b
            bc = c - b

            if np.linalg.norm(ba) == 0 or np.linalg.norm(bc) == 0:
                return 180.0

            cosine = np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc))
            cosine = np.clip(cosine, -1, 1)
            angle = math.degrees(math.acos(cosine))
            return angle

        left_knee_angle = calculate_angle(l_hip, l_knee, l_ankle)
        right_knee_angle = calculate_angle(r_hip, r_knee, r_ankle)

        # Average knee bend (lower angle = more bent)
        knee_angles = []
        if l_knee_vis > 0.5 and l_hip_vis > 0.5 and l_ankle_vis > 0.5:
            knee_angles.append(left_knee_angle)
        if r_knee_vis > 0.5 and r_hip_vis > 0.5 and r_ankle_vis > 0.5:
            knee_angles.append(right_knee_angle)

        features["knee_bend"] = np.mean(knee_angles) if knee_angles else 180.0

        # 3. Arm extension (shoulder-elbow-wrist angle)
        left_arm_angle = calculate_angle(l_shoulder, l_elbow, l_wrist)
        right_arm_angle = calculate_angle(r_shoulder, r_elbow, r_wrist)

        arm_angles = []
        if l_shoulder_vis > 0.5 and l_elbow_vis > 0.5 and l_wrist_vis > 0.5:
            arm_angles.append(left_arm_angle)
        if r_shoulder_vis > 0.5 and r_elbow_vis > 0.5 and r_wrist_vis > 0.5:
            arm_angles.append(right_arm_angle)

        # Extension ratio: 180° = fully extended (1.0), 0° = fully bent (0.0)
        avg_arm_angle = np.mean(arm_angles) if arm_angles else 180.0
        features["arm_extension"] = avg_arm_angle / 180.0

        # 4. Center of mass (approximate as midpoint of shoulders and hips)
        center_mass = (shoulder_center + hip_center) / 2
        features["center_mass_y"] = center_mass[1]  # Normalized Y position

        # 5. Shoulder rotation (shoulder line angle from horizontal)
        shoulder_vec = r_shoulder - l_shoulder
        shoulder_angle = math.degrees(math.atan2(shoulder_vec[1], shoulder_vec[0]))
        features["shoulder_rotation"] = shoulder_angle

        # 6. Hip-shoulder alignment (check if torso is twisted)
        hip_vec = r_hip - l_hip
        hip_angle = math.degrees(math.atan2(hip_vec[1], hip_vec[0]))
        features["hip_shoulder_alignment"] = abs(shoulder_angle - hip_angle)

        return features

    except Exception as e:
        if DEBUG_DETECTION:
            print(f"[WARN] Pose feature extraction failed: {e}")
        return None


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
# ENHANCED TRAJECTORY FEATURES
# -----------------------------------------------------------

def calculate_trajectory_features(trajectory, angles, times):
    """
    Calculate enhanced trajectory features for maneuver classification.

    Returns dict with:
    - turn_radius: approximate radius of the turn (pixels)
    - speed: average speed over trajectory (pixels/second)
    - vertical_displacement: change in vertical position
    - path_smoothness: measure of trajectory smoothness
    """
    if len(trajectory) < 5:
        return None

    try:
        features = {}

        # Calculate turn radius (using curvature approximation)
        positions = np.array(trajectory[-12:])  # Last 12 positions
        if len(positions) >= 3:
            # Simple radius estimation: fit circle to 3 points
            p1, p2, p3 = positions[0], positions[len(positions)//2], positions[-1]

            # Calculate radius using three points
            a = np.linalg.norm(p2 - p1)
            b = np.linalg.norm(p3 - p2)
            c = np.linalg.norm(p3 - p1)

            # Use triangle area formula to get radius
            s = (a + b + c) / 2  # semi-perimeter
            if s > 0 and (s-a) > 0 and (s-b) > 0 and (s-c) > 0:
                area = math.sqrt(s * (s-a) * (s-b) * (s-c))
                if area > 0:
                    radius = (a * b * c) / (4 * area)
                    features["turn_radius"] = radius
                else:
                    features["turn_radius"] = float('inf')
            else:
                features["turn_radius"] = float('inf')
        else:
            features["turn_radius"] = float('inf')

        # Calculate speed
        if len(times) >= 2 and len(trajectory) >= 2:
            total_distance = 0
            for i in range(1, len(trajectory)):
                dx = trajectory[i][0] - trajectory[i-1][0]
                dy = trajectory[i][1] - trajectory[i-1][1]
                total_distance += math.sqrt(dx**2 + dy**2)

            time_span = times[-1] - times[0]
            if time_span > 0:
                features["speed"] = total_distance / time_span
            else:
                features["speed"] = 0
        else:
            features["speed"] = 0

        # Vertical displacement (y increases downward in image coords)
        features["vertical_displacement"] = trajectory[-1][1] - trajectory[0][1]

        # Path smoothness (variance in direction changes)
        if len(angles) >= 3:
            angle_changes = np.abs(np.diff(angles))
            features["path_smoothness"] = np.std(angle_changes)
        else:
            features["path_smoothness"] = 0

        return features

    except Exception as e:
        if DEBUG_DETECTION:
            print(f"[WARN] Trajectory feature calculation failed: {e}")
        return None


# -----------------------------------------------------------
# MANEUVER CLASSIFIER
# -----------------------------------------------------------

def classify_maneuver(pose_features, trajectory_features, turn_metrics):
    """
    Classify specific surf maneuver type based on combined pose and trajectory features.

    Uses rule-based classification for:
    - bottom_turn: Deep lean, high speed, large radius turn at bottom of wave
    - snap: Sharp turn with compressed stance, small radius, high angular speed
    - cutback: Extended carve with moderate lean, larger radius
    - floater: High vertical position, arms extended for balance
    - carve: General turn with moderate characteristics

    Returns: maneuver_type (str) or "turn" if cannot classify specifically
    """
    if not pose_features or not trajectory_features or not turn_metrics:
        return "turn"  # Fallback to generic turn

    try:
        body_lean = pose_features.get("body_lean", 0)
        knee_bend = pose_features.get("knee_bend", 180)
        arm_extension = pose_features.get("arm_extension", 0.5)
        center_mass_y = pose_features.get("center_mass_y", 0.5)

        turn_radius = trajectory_features.get("turn_radius", float('inf'))
        speed = trajectory_features.get("speed", 0)
        vertical_disp = trajectory_features.get("vertical_displacement", 0)

        angle_deg = turn_metrics.get("angle_degrees", 0)
        angular_speed = turn_metrics.get("angular_speed_deg_s", 0)
        direction = turn_metrics.get("direction", "unknown")

        # SNAP: Sharp, aggressive turn with compressed stance
        # - High angular speed (>40°/s)
        # - Small turn radius (<100px)
        # - Deep knee bend (<140°)
        # - Moderate to high lean (>20°)
        if (angular_speed > 40 and
            turn_radius < 100 and
            knee_bend < 140 and
            body_lean > 20):
            return "snap"

        # BOTTOM TURN: Deep carving turn at bottom of wave
        # - Large turn radius (>150px)
        # - High body lean (>25°)
        # - Downward vertical displacement (moving down wave face)
        # - Moderate to high speed
        if (turn_radius > 150 and
            body_lean > 25 and
            vertical_disp > 10 and  # Moving down in frame
            speed > 20):
            return "bottom_turn"

        # CUTBACK: Extended carving turn back toward wave
        # - Large turn radius (>120px)
        # - Moderate lean (15-30°)
        # - Extended arms for balance
        # - Large angle change (>60°)
        if (turn_radius > 120 and
            15 < body_lean < 30 and
            arm_extension > 0.6 and
            angle_deg > 60):
            return "cutback"

        # FLOATER: Riding on top of foam/lip
        # - High vertical position or upward movement
        # - Extended arms for balance
        # - Less aggressive turn
        if (center_mass_y < 0.4 or vertical_disp < -5) and arm_extension > 0.7:
            return "floater"

        # CARVE: General carving turn
        # - Moderate characteristics
        # - Decent lean angle
        # - Smooth path
        if body_lean > 15 and angle_deg > 35:
            return "carve"

        # Default: generic turn
        return "turn"

    except Exception as e:
        if DEBUG_DETECTION:
            print(f"[WARN] Maneuver classification failed: {e}")
        return "turn"


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
                "pose_features_history": deque(maxlen=BUFFER_SIZE),
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
        pose_features_history = state["pose_features_history"]

        # Extract pose from bounding box region
        x1i, y1i, x2i, y2i = map(int, [x1, y1, x2, y2])

        # Ensure bounding box is within frame
        x1i = max(0, x1i)
        y1i = max(0, y1i)
        x2i = min(frame_w, x2i)
        y2i = min(frame_h, y2i)

        # Extract ROI for pose detection
        roi = frame[y1i:y2i, x1i:x2i]

        # Run MediaPipe pose detection on ROI
        pose_features = None
        if roi.size > 0:
            # Convert BGR to RGB for MediaPipe
            roi_rgb = cv2.cvtColor(roi, cv2.COLOR_BGR2RGB)
            pose_results = pose_detector.process(roi_rgb)

            if pose_results.pose_landmarks:
                # Extract pose features
                pose_features = extract_pose_features(pose_results.pose_landmarks, x2i - x1i, y2i - y1i)

        # Store pose features (even if None)
        pose_features_history.append(pose_features)

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

                    # Calculate enhanced trajectory features
                    traj_features = calculate_trajectory_features(
                        list(trajectory),
                        list(angles),
                        list(timestamps)
                    )

                    # Get most recent valid pose features
                    recent_pose_features = None
                    for pf in reversed(pose_features_history):
                        if pf is not None:
                            recent_pose_features = pf
                            break

                    # Classify specific maneuver type
                    specific_maneuver_type = classify_maneuver(
                        recent_pose_features,
                        traj_features,
                        metrics
                    )

                    # Combine all features for event storage
                    event = {
                        "frame": frame_idx,
                        "timestamp": timestamp,
                        "maneuver_type": specific_maneuver_type,
                        "turn_metrics": metrics,
                        "pose_features": recent_pose_features,
                        "trajectory_features": traj_features,
                    }
                    state["events"].append(event)

                    # Save frame capture at the moment of maneuver detection
                    picture_path = os.path.join(state["pictures_dir"], f"{frame_idx}.png")
                    cv2.imwrite(picture_path, frame)

                    # Enhanced logging with maneuver type
                    maneuver_display = specific_maneuver_type.upper().replace("_", " ")
                    print(
                        f"[{maneuver_display}] surfer_id={track_id}, frame={frame_idx}, "
                        f"time={timestamp:.2f}s, total_maneuvers={state['maneuver_count']}, "
                        f"angle={metrics['angle_degrees']:.1f}°, dir={metrics['direction']}"
                    )

                    # Print detailed features if DEBUG enabled
                    if DEBUG_DETECTION and traj_features and recent_pose_features:
                        print(f"  └─ Trajectory: radius={traj_features.get('turn_radius', 0):.1f}px, "
                              f"speed={traj_features.get('speed', 0):.1f}px/s")
                        print(f"  └─ Pose: lean={recent_pose_features.get('body_lean', 0):.1f}°, "
                              f"knee_bend={recent_pose_features.get('knee_bend', 0):.1f}°")

        # ---------------------------------------------------
        # DRAW OVERLAY FOR THIS SURFER (track_id)
        # ---------------------------------------------------

        # bounding box (x1i, y1i, x2i, y2i already set above)
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
    # Note: detected_maneuver_this_frame is just a boolean, we don't track which specific type here
    # (that info is already in the per-surfer state)
    if detected_maneuver_this_frame:
        cv2.putText(
            frame,
            "MANEUVER!",
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
pose_detector.close()

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
        json_path = os.path.join(state["surfer_dir"], "maneuvers.json")
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
