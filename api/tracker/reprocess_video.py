"""
Video reprocessing script - regenerates output video with only selected surfer IDs.

This script reads the saved tracking_data.json and replays the video,
drawing overlays only for specified surfer IDs. Used after surfer merging
to remove unselected surfers from the output video.
"""
import os
import sys
import json
import subprocess
import cv2
import numpy as np
import mediapipe as mp
from mediapipe.python.solutions import drawing_utils as mp_drawing
from mediapipe.python.solutions import drawing_styles as mp_drawing_styles


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


def reprocess_video(
    input_video_path: str,
    tracking_data_path: str,
    output_video_path: str,
    selected_surfer_ids: list
):
    """
    Reprocess video with only selected surfer IDs.

    Args:
        input_video_path: Path to original video file
        tracking_data_path: Path to tracking_data.json
        output_video_path: Path for new output video
        selected_surfer_ids: List of surfer IDs to include in output
    """
    print(f"[INFO] Reprocessing video with surfer IDs: {selected_surfer_ids}")
    print(f"[INFO] Input video: {input_video_path}")
    print(f"[INFO] Tracking data: {tracking_data_path}")
    print(f"[INFO] Output video: {output_video_path}")

    # Load tracking data
    print("[INFO] Loading tracking data...")
    with open(tracking_data_path, "r") as f:
        tracking_data = json.load(f)

    video_info = tracking_data["video_info"]
    frames_data = tracking_data["frames"]

    fps = video_info["fps"]
    frame_w = video_info["width"]
    frame_h = video_info["height"]
    rotation = video_info.get("rotation", 0)

    print(f"[INFO] Video info: {frame_w}x{frame_h} @ {fps} fps, rotation={rotation}°")
    print(f"[INFO] Total frames with tracking data: {len(frames_data)}")

    # Open input video
    cap = cv2.VideoCapture(input_video_path)
    if not cap.isOpened():
        print(f"[ERROR] Cannot open video: {input_video_path}")
        return False

    # Create output video writer (using mp4v, will re-encode to H.264 with ffmpeg)
    temp_output_path = output_video_path.replace(".mp4", "_temp.mp4")
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(temp_output_path, fourcc, fps, (frame_w, frame_h))

    # Initialize MediaPipe Pose for drawing pose overlays
    mp_pose = mp.solutions.pose

    # Create a mapping of frame_index -> detections for fast lookup
    frame_detections_map = {frame_data["frame"]: frame_data["detections"] for frame_data in frames_data}

    frame_idx = 0
    frames_processed = 0

    print("[INFO] Processing frames...")

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # Apply rotation if needed
        frame = rotate_frame(frame, rotation)

        # Get detections for this frame
        frame_detections = frame_detections_map.get(frame_idx, [])

        # Filter for selected surfer IDs
        selected_detections = [d for d in frame_detections if d["track_id"] in selected_surfer_ids]

        # Draw overlays for selected surfers
        for detection in selected_detections:
            track_id = detection["track_id"]
            box = detection["box"]
            maneuver_count = detection["maneuver_count"]
            pose_landmarks = detection.get("pose_landmarks")

            x1, y1, x2, y2 = box
            x1i, y1i = int(x1), int(y1)
            x2i, y2i = int(x2), int(y2)

            # Draw bounding box
            cv2.rectangle(frame, (x1i, y1i), (x2i, y2i), (0, 255, 0), 2)

            # Draw pose skeleton if available
            if pose_landmarks is not None:
                # Reconstruct MediaPipe landmarks format
                from mediapipe.framework.formats import landmark_pb2

                landmarks_proto = landmark_pb2.NormalizedLandmarkList()
                for lm in pose_landmarks:
                    landmark = landmarks_proto.landmark.add()
                    landmark.x = lm["x"]
                    landmark.y = lm["y"]
                    landmark.z = lm["z"]
                    landmark.visibility = lm["visibility"]

                # Create ROI for pose drawing
                roi_h = y2i - y1i
                roi_w = x2i - x1i

                if roi_h > 0 and roi_w > 0:
                    roi_with_pose = frame[y1i:y2i, x1i:x2i].copy()

                    # Draw pose landmarks on ROI
                    mp_drawing.draw_landmarks(
                        roi_with_pose,
                        landmarks_proto,
                        mp_pose.POSE_CONNECTIONS,
                        landmark_drawing_spec=mp_drawing_styles.get_default_pose_landmarks_style(),
                        connection_drawing_spec=mp_drawing.DrawingSpec(
                            color=(0, 255, 0),  # Green color
                            thickness=2,
                            circle_radius=2
                        )
                    )

                    # Overlay back onto frame
                    frame[y1i:y2i, x1i:x2i] = roi_with_pose

            # Draw label box
            label_id = f"ID: {track_id}"
            label_maneuvers = f"Maneuvers: {maneuver_count}"

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

        # Write frame to output
        out.write(frame)
        frame_idx += 1
        frames_processed += 1

        if frames_processed % 100 == 0:
            print(f"[INFO] Processed {frames_processed} frames...")

    cap.release()
    out.release()

    # Re-encode video to H.264 for browser compatibility
    print("[INFO] Re-encoding video to H.264 for browser compatibility...")
    try:
        ffmpeg_cmd = [
            'ffmpeg', '-y',  # Overwrite output file
            '-i', temp_output_path,  # Input file (mp4v)
            '-c:v', 'libx264',  # H.264 codec
            '-preset', 'medium',  # Encoding speed/quality trade-off
            '-crf', '23',  # Constant Rate Factor (quality, 18-28 is good)
            '-pix_fmt', 'yuv420p',  # Pixel format for compatibility
            '-movflags', '+faststart',  # Enable fast start for web streaming
            output_video_path  # Output file
        ]
        result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)

        if result.returncode == 0:
            # Remove temporary file
            os.remove(temp_output_path)
            print("[INFO] Video successfully re-encoded to H.264")
        else:
            print(f"[ERROR] ffmpeg failed: {result.stderr}")
            # Keep the temp file as fallback
            print(f"[WARN] Using temporary file: {temp_output_path}")
    except Exception as e:
        print(f"[ERROR] Failed to re-encode video: {e}")
        # Keep the temp file as fallback
        print(f"[WARN] Using temporary file: {temp_output_path}")

    print(f"[INFO] Reprocessing complete!")
    print(f"[INFO] Processed {frames_processed} frames")
    print(f"[INFO] Output video: {output_video_path}")

    return True


if __name__ == "__main__":
    # Command-line usage
    if len(sys.argv) < 4:
        print("Usage: python reprocess_video.py <input_video> <tracking_data.json> <output_video> <surfer_ids...>")
        print("Example: python reprocess_video.py input.mp4 tracking_data.json output.mp4 1 3 5")
        sys.exit(1)

    input_video = sys.argv[1]
    tracking_data = sys.argv[2]
    output_video = sys.argv[3]
    surfer_ids = [int(sid) for sid in sys.argv[4:]]

    success = reprocess_video(input_video, tracking_data, output_video, surfer_ids)
    sys.exit(0 if success else 1)
