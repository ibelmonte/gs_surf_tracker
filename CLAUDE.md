# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a surf movement detection and tracking system that processes surfing videos to:
- Detect and track multiple surfers using YOLOv8n + BoTSORT
- Identify surfing maneuvers (drop, bottom turn, snap, cutback)
- Generate per-surfer JSON files with maneuver events
- Produce annotated video with bounding boxes and maneuver counts
- Capture frame snapshots at each detected maneuver

## Development Commands

### Running the tracker
```bash
# Using Docker (recommended)
docker compose up --build

# Direct Python (requires dependencies installed)
python tracker.py
```

### Dependencies
```bash
pip install -r requirements.txt
```

Required packages:
- ultralytics (YOLOv8)
- opencv-python-headless
- torch
- numpy
- lap (for BoTSORT)

## Architecture

### Core Pipeline (`tracker.py`)

The system is implemented as a single-file pipeline with these stages:

1. **Video Input**: Reads from `data/input.mp4` (configurable via `VIDEO_SOURCE` env var)
2. **Detection**: YOLOv8n detects "person" class per frame
3. **Tracking**: BoTSORT maintains stable IDs across occlusions using:
   - Sparse optical flow motion estimation
   - OSNet appearance embeddings (ReID)
   - Extended track buffer (90 frames) for occlusion tolerance
4. **Maneuver Detection**: Per-surfer trajectory analysis
5. **Output Generation**: Annotated video + per-surfer JSON files

### Per-Surfer State Management

Each tracked surfer maintains state including:
- `trajectory`: Deque of (cx, cy) positions (max 70 frames)
- `angles`: Motion angles calculated from trajectory
- `timestamps`: Frame timestamps for velocity calculations
- `maneuver_count`: Total detected maneuvers
- `drop_detected`: Whether initial drop has been seen
- `is_active`: Activity filter to exclude stationary detections
- `events`: List of detected maneuver events with metrics

State is keyed by BoTSORT's `track_id`.

### Maneuver Detection Algorithm

Detection runs in priority order:

**Priority 1: Drop Detection** (executed once per surfer)
- Detects initial wave catch and descent
- Requires: sustained downward movement (4+ frames), minimum vertical distance (15px), minimum velocity (8px/s)
- Sets `drop_detected=True` to prevent re-triggering

**Priority 2: Turn Detection** (bottom turn, snap, cutback)
- Analyzes smoothed motion angles over sliding window
- Requires: sustained turn direction (5 frames), minimum angle change (45°), minimum angular speed (25°/s)
- Classification logic:
  - **Snap**: High angular speed (≥40°/s) + sharp angle (≥55°) + **ascendent movement** (Y decreases - surfer moves up toward wave lip)
  - **Cutback**: Large directional change (≥85°) + **descendent movement** (Y increases - surfer moves down the wave face)
  - **Bottom Turn**: Standard turn meeting minimum thresholds

**Note**: Current implementation (tracker.py:289-316) classifies based on angle and speed only. The vertical movement direction (snap=ascendent, cutback=descendent) is documented here as the physical characteristic but not yet implemented as a classification criterion.

### Activity Filtering

To prevent false detections from stationary surfers or ID swaps:
- Tracks total movement distance and active frame count per surfer
- Requires 100px total movement + 10 active frames before enabling detection
- Detects trajectory jumps (>150px) as potential ID swaps and resets activity tracking

### BoTSORT Configuration (`botsort.yaml`)

Key settings for surf tracking:
- `with_reid: True` - Enables appearance-based ReID with OSNet
- `track_buffer: 90` - Extended occlusion tolerance (3 seconds @ 30fps)
- `max_age: 60` - Allows longer "dead time" before dropping track
- `appearance_thresh: 0.15` - Strong ReID matching to prevent ID swaps
- `gmc_method: sparseOptFlow` - Motion compensation for camera movement

### Output Structure

```
data/output/
  ├── output.mp4                    # Annotated video
  └── elements/
      ├── {track_id}/               # One directory per active surfer
      │   ├── pictures/
      │   │   ├── {frame}.png       # Frame captures at maneuver moments
      │   │   └── ...
      │   └── turns.json            # Maneuver events for this surfer
      └── ...
```

**JSON Schema** (`turns.json`):
```json
{
  "id": 2,
  "total_maneuvers": 5,
  "events": [
    {
      "frame": 136,
      "timestamp": 46.999876260757446,
      "maneuver_type": "snap",
      "metrics": {
        "angle_degrees": 57.89,
        "direction": "left",
        "angular_speed_deg_s": 45.2,
        "position_relative": 0.75
      }
    }
  ]
}
```

### Configuration Parameters

Key tunable parameters in `tracker.py`:

**Detection Thresholds**:
- `CONF_THRESHOLD`: YOLOv8 confidence (0.4)
- `BUFFER_SIZE`: Trajectory history length (70 frames)

**Activity Filtering**:
- `MIN_MOVEMENT_DISTANCE`: 100px total movement required
- `MIN_ACTIVE_FRAMES`: 10 frames with significant movement
- `MAX_POSITION_JUMP`: 150px (trajectory consistency check)

**Drop Detection**:
- `MIN_DROP_DISTANCE_PIXELS`: 15px
- `MIN_DROP_VELOCITY_PX_PER_S`: 8px/s
- `DROP_SUSTAIN_FRAMES`: 4 frames

**Turn Detection**:
- `MIN_TURN_ANGLE_DEG`: 45° minimum
- `TURN_SUSTAIN_FRAMES`: 5 frames
- `MIN_TURN_SPEED_DEG_PER_S`: 25°/s

**Turn Classification**:
- `MIN_SNAP_SPEED_DEG_PER_S`: 40°/s (explosive turn threshold)
- `MIN_SNAP_ANGLE_DEG`: 55° (snap requires sharper angle)
- `MIN_CUTBACK_ANGLE_DEG`: 85° (large directional change)

## Important Notes

### Maneuver Physical Characteristics

Understanding the actual surfing movements helps tune detection:

- **Drop**: Initial descent after catching wave (descendent motion, Y increases)
- **Bottom Turn**: Turn at bottom of wave (foundational maneuver)
- **Snap**: Explosive turn at wave lip - surfer moves ascendently (Y decreases - moving toward top of frame)
- **Cutback**: Large turn back toward wave power - surfer moves descendently (Y increases - moving toward bottom of frame)

**Image Coordinate System**: OpenCV uses standard image coordinates where Y=0 is at the top of the frame and Y increases downward. Therefore:
- Ascendent movement (moving up visually) = Y coordinate decreases (dy < 0)
- Descendent movement (moving down visually) = Y coordinate increases (dy > 0)

### Video Orientation
The system auto-detects portrait/landscape orientation via OpenCV. No manual configuration needed.

### Debugging
Set `DEBUG_DETECTION = True` in `tracker.py` to enable detailed console logging of:
- Drop detection events
- Turn analysis (angle, speed, position)
- Maneuver classification reasoning
- Activity status changes
- ID swap warnings

### Surfer Filtering
Surfers with zero detected maneuvers are automatically removed from output, including:
- Inactive surfers (insufficient movement)
- Surfers with no detected turns/drops
Their directories are deleted and they don't appear in final output.

### ID Stability
BoTSORT's appearance-based ReID helps maintain stable IDs through:
- Brief occlusions (other surfers, waves)
- Frame drops or quality issues
- Camera movement (handled by optical flow GMC)

The activity filter and trajectory consistency checks further prevent false detections from ID swaps.
