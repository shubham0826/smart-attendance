"""Camera and frame-processing helpers for the AI module."""

import time

import cv2


def resize_frame(frame, max_width=960):
    """Resize a frame to at most max_width while preserving its aspect ratio."""
    height, width = frame.shape[:2]
    if width <= max_width:
        return frame
    scale = max_width / width
    return cv2.resize(frame, (max_width, int(height * scale)), interpolation=cv2.INTER_AREA)


def bgr_to_rgb(frame):
    """Convert OpenCV's BGR frame to RGB for face-recognition libraries."""
    return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)


def draw_bbox(frame, bbox, label=None, color=(0, 200, 0)):
    """Draw a (left, top, right, bottom) box and optional label on a BGR frame."""
    left, top, right, bottom = (int(value) for value in bbox)
    cv2.rectangle(frame, (left, top), (right, bottom), color, 2)
    if label:
        text_y = max(top - 8, 20)
        cv2.putText(frame, label, (left, text_y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
    return frame


def run_camera_preview(camera_index=0, max_width=960):
    """Show a resized live preview with frame size and measured FPS."""
    camera = cv2.VideoCapture(camera_index)
    if not camera.isOpened():
        print(f"Camera {camera_index} could not be opened. Check permissions or connection.")
        return 1

    print("Camera started. Press Q in the preview window to quit.")
    frames = 0
    fps = 0.0
    interval_start = time.perf_counter()
    try:
        while True:
            success, frame = camera.read()
            if not success:
                print("Could not read a camera frame.")
                return 1

            frame = resize_frame(frame, max_width=max_width)
            height, width = frame.shape[:2]
            frames += 1
            elapsed = time.perf_counter() - interval_start
            if elapsed >= 1.0:
                fps = frames / elapsed
                frames = 0
                interval_start = time.perf_counter()

            cv2.putText(
                frame,
                f"Frame: {width}x{height}  FPS: {fps:.1f}  Color: BGR",
                (12, 28),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.65,
                (0, 255, 0),
                2,
            )
            cv2.imshow("Smart Attendance - Camera Preview", frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                return 0
    finally:
        camera.release()
        cv2.destroyAllWindows()
