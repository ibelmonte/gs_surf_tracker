# Surf Motion Tracking System --- Functional & Architectural Specification

## 1. Project Goal

Build an AI-based video processing pipeline that: - Detects surfers. -
Tracks each surfer with stable logical IDs. - Detects turning
maneuvers. - Produces overlayed video and JSON logs. - Runs headless
inside Docker.

## 2. Input / Output Requirements

### Input

-   `input.mp4` (any orientation).

### Output

-   `output/output.mp4`
-   `output/turns-<ID>.json`

## 3. Architecture

1.  YOLOv8 detection
2.  BoT-SORT tracking
3.  Logical-ID merging
4.  Motion/angle analysis
5.  Overlay & JSON export

## 4. Detection (YOLOv8)

-   Model: yolov8n.pt
-   Class: person

## 5. Tracking (BoT-SORT)

-   Configurable with botsort.yaml

## 6. Logical-ID Stabilization

-   Maps short-lived tracker IDs to stable IDs.

## 7. Motion Analysis

-   Tracks center positions
-   Computes angle deltas
-   Detects turns

## 8. Output Subsystem

-   Draws overlays
-   Writes MP4 + JSON
