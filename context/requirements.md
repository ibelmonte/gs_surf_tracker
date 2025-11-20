
# Surf Multi-Tracker – Project Specification

## 1. Overview
This system processes surfing videos and performs the following:
- Detects multiple surfers.
- Tracks each surfer throughout the wave, even through brief occlusion.
- Detects turns (direction, severity, timestamps).
- Generates per-surfer JSON files and a single overlaid output video.
- Handles vertical and horizontal videos automatically.

---

## 2. Input Files
- **Video file**: `data/input.mp4`
- Orientation is detected automatically using OpenCV (portrait/landscape).

---

## 3. Output Files
All outputs are written into:

```
data/output/
```

### 3.1 Output Video
```
output.mp4
```
Includes:
- Bounding boxes for each surfer.
- Stable logical IDs.
- Turn count displayed inside bounding box.

---

## 4. JSON Output Format

Each surfer receives a file:

```
turns-{logical_id}.json
```

Example filename:
```
turns-3.json
```

### 4.1 JSON Schema

```json
{
  "id": "integer - stable logical ID",
  "total_turns": "integer - number of turns in the video clip",
  "events": [
    {
        "frame": "integer",,
        "timestamp": "float - seconds",
        "direction": "string - 'left' or 'right'",
        "severity": "string - 'mild' or 'medium' or 'strong'",
        "angle_degrees": "float - angle in degrees"
    }
}
```

---

## 4.2 Example JSON File

**turns-3.json**
```json
{
    "id": 2,
    "total_turns": 5,
    "events": [
        {
            "frame": 136,
            "timestamp": 46.999876260757446,
            "direction": "right",
            "severity": "mild",
            "angle_degrees": 57.89830409375186
        },
        {
            "frame": 171,
            "timestamp": 57.780139207839966,
            "direction": "left",
            "severity": "mild",
            "angle_degrees": 48.62631837461168
        },
        {
            "frame": 210,
            "timestamp": 68.59231686592102,
            "direction": "right",
            "severity": "mild",
            "angle_degrees": 47.771882528595924
        },
        {
            "frame": 314,
            "timestamp": 95.95589017868042,
            "direction": "left",
            "severity": "mild",
            "angle_degrees": 47.555916454811204
        },
        {
            "frame": 332,
            "timestamp": 101.24145531654358,
            "direction": "right",
            "severity": "mild",
            "angle_degrees": 51.241250489677675
        }
    ]
}
```

---

## 5. System Architecture

### 5.1 Components
- **YOLOv8n**  
  Detects "person" objects per frame.

- **BoTSORT tracker**  
  Uses:
  - Optical flow (sparse)
  - Appearance embedding (OSNet)
  - Motion smoothing
  - Occlusion-aware ID retention

- **Turn Analysis Module**  
  - Computes angle from the movement vector.
  - Applies smoothing windows.
  - Detects local maxima over threshold.
  - Assigns type based on severity and angle curvature.

- **ID Stabilization Layer**  
  - Uses appearance matching + angle continuity
  - Avoids ID jumps during short occlusions

---

## 6. Directory Structure

```
project/
  ├── tracker.py
  ├── botsort.yaml
  ├── data/
  │     ├── input.mp4
  │     └── output/
  │             ├── output.mp4                         # Annotated video
  │             └── elements/
  │                ├── 1/                              # Surfer ID 1
  │                │   ├── pictures/
  │                │   │   ├── 136.png                 # Frame capture at turn
  │                │   │   ├── 171.png
  │                │   │   └── ...
  │                │   └── turns.json                  # Turn data
  │                ├── 2/                              # Surfer ID 2
  │                │   ├── pictures/
  │                │   └── turns.json
  │                └── ...
  ├── Dockerfile
  └── docker-compose.yml
```

---

## 7. Docker Runtime

`docker compose up --build`  
Runs the entire pipeline:
- Loads model
- Processes video
- Writes JSON + video

---

## 8. Future Improvements
- Wave segmentation (identify wave shape + surfer-to-wave alignment)
- ReID training on real surf footage
- Bottom turn classifier using a neural network
- Speed and acceleration estimation
- Trick classification (snap, cutback, alley-oop, etc.)

---

This document is intended for consumption by AI coding agents, engineering teams, or automated pipeline generators.
