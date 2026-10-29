# Exam seat-zone prototype

This is a still-image geometry prototype for the Exam Mode roadmap. It uses the
existing YuNet face detector, then assigns each face-box center to a configured
seat-zone polygon. It does not recognize students, detect bodies, or decide
whether anyone violated a seating plan.

## Prepare a local plan

Copy `templates/seat_plan.template.json` to `seat_plan.local.json`. Set the exact
frame width and height from the intended camera and replace the example seats,
student IDs, and polygons. Each polygon uses normalized `[x, y]` coordinates
from `0.0` to `1.0`, measured from the top-left of the camera frame. Local plans
are excluded from Git because they contain student-to-seat assignments.

Validate the plan:

```powershell
.\.venv\Scripts\python.exe .\exam\seat_plan.py .\exam\seat_plan.local.json
```

## Analyze a still image

Use a consented test image captured from the same camera framing and resolution
as the plan:

```powershell
.\.venv\Scripts\python.exe .\exam\analyze_seat_image.py `
  --plan .\exam\seat_plan.local.json `
  --image .\path\to\test-frame.jpg `
  --json-output .\reports\exam\observations.json `
  --annotated-output .\reports\exam\annotated.jpg `
  --no-display
```

Image and frame dimensions must match exactly. The JSON report contains seat
IDs, face counts, and position ambiguity counts; it does not include the
assigned student IDs. No image or report is written unless an output path is
provided.

`no_face_detected` means YuNet did not place a face-box center inside that zone
in this image. It does not mean the seat is empty, the assigned person is
absent, or a rule was violated. A wide classroom camera may not show faces well
enough for this method; a calibrated room image and person-detection approach
are still needed before this can support an exam workflow.
