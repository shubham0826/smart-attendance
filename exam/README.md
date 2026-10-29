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

To draw zones instead of editing polygon numbers by hand, prepare the private
assignment CSV and run the visual calibrator with a reference frame from the
intended camera:

```powershell
Copy-Item .\exam\templates\seat_assignments.template.csv .\exam\seat_assignments.local.csv
notepad .\exam\seat_assignments.local.csv
.\.venv\Scripts\python.exe .\exam\calibrate_seat_zones.py `
  --image .\path\to\camera-reference.jpg `
  --assignments .\exam\seat_assignments.local.csv `
  --exam-id EXAM-ID
```

For each seat, click at least three zone corners and press Enter. Backspace
removes the last point; Escape cancels without writing a plan. The calibrator
uses the image only for drawing and does not copy or save it. It refuses to
overwrite an existing output plan.

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

## Compare identity observations with a plan

`compare_observations.py` defines the input contract for a later identity
provider. Start from `templates/observations.template.json` and replace its
example exam ID, frame dimensions, and bounding boxes. Each observation must
set `identity_status` to `recognized`, `unknown`, or `uncertain`. Only a
`recognized` observation may contain `student_id`; the other statuses must use
`null`. The file format does not decide whether a model's match is reliable.

Run the comparison:

```powershell
.\.venv\Scripts\python.exe .\exam\compare_observations.py `
  --plan .\exam\seat_plan.local.json `
  --observations .\exam\identity_observations.local.json `
  --output .\reports\exam\review.json
```

Every seat result requires teacher review. Matching IDs are only candidates for
review; different IDs are possible mismatches for review; missing, unknown,
duplicate, or overlapping observations remain uncertain. The tool does not
write attendance, change a review status, or make a final seating decision.
Observation files and detailed review reports may contain student IDs and must
remain local. This is an input contract and comparison step; no face-recognition
identity provider is connected to Exam Mode yet.
