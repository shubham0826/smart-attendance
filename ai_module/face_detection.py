"""Detect faces with YuNet in an image or from the default webcam."""

import argparse
from pathlib import Path

import cv2

try:
    from .camera import draw_bbox, resize_frame
except ImportError:  # Supports running this file directly as a script.
    from camera import draw_bbox, resize_frame


PROJECT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_MODEL = PROJECT_DIR / "models" / "face_detection_yunet_2026may.onnx"
DEFAULT_SCORE_THRESHOLD = 0.85


class YuNetFaceDetector:
    """Small wrapper returning face boxes and detector scores for BGR frames."""

    def __init__(self, model_path=DEFAULT_MODEL, score_threshold=DEFAULT_SCORE_THRESHOLD):
        model_path = Path(model_path)
        if not model_path.is_file():
            raise FileNotFoundError(f"YuNet model not found: {model_path}")
        if not hasattr(cv2, "FaceDetectorYN"):
            raise RuntimeError("This OpenCV build does not provide FaceDetectorYN.")

        self.score_threshold = score_threshold
        self.detector = cv2.FaceDetectorYN.create(
            str(model_path),
            "",
            (320, 320),
            score_threshold,
            0.3,
            5000,
        )

    def detect(self, frame):
        """Return a list of (left, top, right, bottom, score) detections."""
        height, width = frame.shape[:2]
        self.detector.setInputSize((width, height))
        _, results = self.detector.detect(frame)
        if results is None:
            return []

        detections = []
        for result in results:
            x, y, box_width, box_height = result[:4]
            score = float(result[-1])
            left = max(0, int(round(x)))
            top = max(0, int(round(y)))
            right = min(width, int(round(x + box_width)))
            bottom = min(height, int(round(y + box_height)))
            detections.append((left, top, right, bottom, score))
        return detections


def process_image(detector, image_path, output_path=None, display=True):
    image = cv2.imread(str(image_path))
    if image is None:
        raise SystemExit(f"Could not read image: {image_path}")

    detections = detector.detect(image)
    print(f"Detected {len(detections)} face(s) in {image_path}")
    for index, (left, top, right, bottom, score) in enumerate(detections, start=1):
        print(f"  Face {index}: score={score:.3f}, box=({left}, {top}, {right}, {bottom})")
        draw_bbox(image, (left, top, right, bottom), f"Face {index}: {score:.2f}")

    if output_path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if not cv2.imwrite(str(output_path), image):
            raise SystemExit(f"Could not write annotated image: {output_path}")
        print(f"Saved annotated image: {output_path}")

    if display:
        cv2.imshow("YuNet Face Detection", image)
        cv2.waitKey(0)
        cv2.destroyAllWindows()
    return len(detections)


def run_camera(detector, camera_index=0, max_width=960):
    camera = cv2.VideoCapture(camera_index)
    if not camera.isOpened():
        print(f"Camera {camera_index} could not be opened.")
        return 1

    print("YuNet face detection running. Press Q to quit.")
    try:
        while True:
            success, frame = camera.read()
            if not success:
                print("Could not read a camera frame.")
                return 1

            frame = resize_frame(frame, max_width=max_width)
            detections = detector.detect(frame)
            for index, (left, top, right, bottom, score) in enumerate(detections, start=1):
                draw_bbox(frame, (left, top, right, bottom), f"Face {index}: {score:.2f}")
            cv2.putText(
                frame,
                f"Faces: {len(detections)} | YuNet threshold: {detector.score_threshold:.2f}",
                (12, 28),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 255, 0),
                2,
            )
            cv2.imshow("YuNet Face Detection", frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                return 0
    finally:
        camera.release()
        cv2.destroyAllWindows()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", type=Path, help="image to detect instead of opening the webcam")
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL, help="YuNet ONNX model path")
    parser.add_argument("--score-threshold", type=float, default=DEFAULT_SCORE_THRESHOLD)
    parser.add_argument("--output", type=Path, help="optional path for a saved annotated image")
    parser.add_argument("--no-display", action="store_true", help="detect an image without opening a window")
    args = parser.parse_args()

    if not 0.0 <= args.score_threshold <= 1.0:
        parser.error("--score-threshold must be between 0 and 1")

    try:
        detector = YuNetFaceDetector(args.model, args.score_threshold)
    except (FileNotFoundError, RuntimeError, cv2.error) as exc:
        raise SystemExit(f"Could not initialize YuNet: {exc}") from exc

    if args.image:
        process_image(detector, args.image, args.output, display=not args.no_display)
        return 0
    return run_camera(detector)


if __name__ == "__main__":
    raise SystemExit(main())
