"""Capture one local reference frame for exam seat-zone calibration."""

import argparse
from pathlib import Path

import cv2


PROJECT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = PROJECT_DIR / "exam" / "reference_frame.local.jpg"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--camera-index", type=int, default=0, help="OpenCV camera index (default: 0)")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="local image output path")
    args = parser.parse_args()
    if args.output.exists():
        parser.error(f"output already exists; choose another path to avoid overwriting it: {args.output}")

    camera = cv2.VideoCapture(args.camera_index)
    if not camera.isOpened():
        raise SystemExit(
            f"Could not open camera {args.camera_index}. Close other camera apps or try --camera-index 1."
        )

    print("Aim the camera at the exam room from its intended position.")
    print("Press Space to save one local reference frame, or Q/Esc to cancel.")
    captured = False
    try:
        while True:
            success, frame = camera.read()
            if not success:
                raise SystemExit("Could not read a frame from the camera.")
            preview = frame.copy()
            cv2.putText(
                preview,
                f"Frame: {frame.shape[1]}x{frame.shape[0]} | Space: save | Q: cancel",
                (12, 28),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 255, 0),
                2,
            )
            cv2.imshow("Exam room reference frame", preview)
            key = cv2.waitKey(1) & 0xFF
            if key == ord("q") or key == 27:
                print("Capture canceled; no image was saved.")
                break
            if key == ord(" "):
                args.output.parent.mkdir(parents=True, exist_ok=True)
                if not cv2.imwrite(str(args.output), frame):
                    raise SystemExit(f"Could not write reference frame: {args.output}")
                print(f"Saved reference frame: {args.output}")
                print(f"Frame dimensions: {frame.shape[1]}x{frame.shape[0]}")
                captured = True
                break
    finally:
        camera.release()
        cv2.destroyAllWindows()
    return 0 if captured else 1


if __name__ == "__main__":
    raise SystemExit(main())
