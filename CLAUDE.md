# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a surf movement detection and tracking system that processes surfing videos to:
- Detect and track multiple surfers using YOLOv8n + BoTSORT
- Identify turning movements
- Generate per-surfer JSON files with turn events
- Produce annotated video with bounding boxes and turn counts
- Capture frame snapshots at each detected turn

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
2. **Rotation Detection**: Uses ffprobe to detect video rotation metadata and applies rotation to maintain correct orientation
3. **Detection**: YOLOv8n detects "person" class per frame
4. **Tracking**: BoTSORT maintains stable IDs across occlusions using:
   - Sparse optical flow motion estimation
   - OSNet appearance embeddings (ReID)
   - Extended track buffer (90 frames) for occlusion tolerance
5. **Turn Detection**: Per-surfer trajectory analysis to identify turning movements
6. **Output Generation**: Annotated video + per-surfer JSON files

### Per-Surfer State Management

Each tracked surfer maintains state including:
- `trajectory`: Deque of (cx, cy) positions (max 70 frames)
- `angles`: Motion angles calculated from trajectory
- `timestamps`: Frame timestamps for velocity calculations
- `maneuver_count`: Total detected turns
- `is_active`: Activity filter to exclude stationary detections
- `events`: List of detected turn events with metrics

State is keyed by BoTSORT's `track_id`.

### Turn Detection Algorithm

The system detects generic turning movements based on trajectory analysis:

**Turn Detection**
- Analyzes smoothed motion angles over sliding window
- Requires: sustained turn direction (5 frames), minimum angle change (45°), minimum angular speed (25°/s)
- Records turn direction (left/right) and metrics (angle, angular speed)

### Bounding Box Size Filtering

To exclude people who are too close to the camera (e.g., walkers on beach when filming a distant surfer):
- **Max width ratio**: 0.4 (40% of frame width) - boxes larger than this are filtered out
- **Max height ratio**: 0.6 (60% of frame height) - boxes larger than this are filtered out
- **Min area**: 400 pixels - boxes smaller than this are filtered as noise

This ensures only appropriately-sized detections (surfers at correct distance) are tracked, not foreground walkers or background noise.

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
      │   │   ├── {frame}.png       # Frame captures at turn moments
      │   │   └── ...
      │   └── turns.json            # Turn events for this surfer
      └── ...
```

**JSON Schema** (`turns.json`):
```json
{
  "id": 2,
  "total_turns": 5,
  "events": [
    {
      "frame": 136,
      "timestamp": 46.999876260757446,
      "maneuver_type": "turn",
      "metrics": {
        "angle_degrees": 57.89,
        "direction": "left",
        "angular_speed_deg_s": 45.2
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

**Bounding Box Filtering**:
- `MAX_BOX_WIDTH_RATIO`: 0.4 (max 40% of frame width)
- `MAX_BOX_HEIGHT_RATIO`: 0.6 (max 60% of frame height)
- `MIN_BOX_AREA_PIXELS`: 400px (minimum detection size)

**Activity Filtering**:
- `MIN_MOVEMENT_DISTANCE`: 100px total movement required
- `MIN_ACTIVE_FRAMES`: 10 frames with significant movement
- `MAX_POSITION_JUMP`: 150px (trajectory consistency check)

**Turn Detection**:
- `MIN_TURN_ANGLE_DEG`: 45° minimum angle change
- `TURN_SUSTAIN_FRAMES`: 5 frames of consistent turning
- `MIN_TURN_SPEED_DEG_PER_S`: 25°/s minimum angular speed

## Important Notes

### Video Orientation & Rotation Handling
The system automatically detects and corrects video rotation metadata using ffprobe. Many vertical videos (especially from smartphones) are stored as horizontal videos with rotation metadata. The system:
1. Detects rotation metadata (0°, 90°, 180°, 270°) using ffprobe (checks both rotate tag and side_data)
2. Applies the rotation to each frame before processing
3. Adjusts output video dimensions accordingly

This ensures vertical videos stay vertical in the output. Requires ffmpeg/ffprobe to be installed (already included in the Docker image).

**Manual Override**: If auto-detection fails, you can manually specify rotation:
```bash
# Docker
ROTATION=90 docker compose up --build

# Direct Python
ROTATION=90 python tracker.py
```

Rotation values: 0, 90, 180, 270, or negative values like -90 (clockwise degrees to correct orientation).

### Debugging
Set `DEBUG_DETECTION = True` in `tracker.py` to enable detailed console logging of:
- Turn detection events
- Turn analysis (angle, speed, direction)
- Activity status changes
- ID swap warnings

### Surfer Filtering
Surfers with zero detected turns are automatically removed from output, including:
- Inactive surfers (insufficient movement)
- Surfers with no detected turns
Their directories are deleted and they don't appear in final output.

### ID Stability
BoTSORT's appearance-based ReID helps maintain stable IDs through:
- Brief occlusions (other surfers, waves)
- Frame drops or quality issues
- Camera movement (handled by optical flow GMC)

The activity filter and trajectory consistency checks further prevent false detections from ID swaps.
