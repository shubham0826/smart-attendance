# Exam seat-zone prototype

These still-image tools use the existing YuNet face detector and local face
embeddings to prepare exam-seat observations. They do not detect bodies or
decide whether anyone violated a seating plan. Every identity and seat result
is a candidate for teacher review.

## Prepare a local plan

Copy `templates/seat_plan.template.json` to `seat_plan.local.json`. Set the exact
frame width and height from the intended camera and replace the example seats,
student IDs, and polygons. Each polygon uses normalized `[x, y]` coordinates
from `0.0` to `1.0`, measured from the top-left of the camera frame. Local plans
are excluded from Git because they contain student-to-seat assignments.

To draw zones instead of editing polygon numbers by hand, prepare the private
assignment CSV and first capture a reference frame from the intended camera:

```powershell
.\.venv\Scripts\python.exe .\exam\capture_reference_frame.py
```

Aim the camera at the exam room, then press Space to save the frame. The default
image path is `exam/reference_frame.local.jpg`; it is ignored by Git. Press Q
or Esc to cancel without saving. Use the exact saved frame for calibration:

```powershell
Copy-Item .\exam\templates\seat_assignments.template.csv .\exam\seat_assignments.local.csv
notepad .\exam\seat_assignments.local.csv
.\.venv\Scripts\python.exe .\exam\calibrate_seat_zones.py `
  --image .\exam\reference_frame.local.jpg `
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

## Analyze identities and seat positions together

Once the local seat plan and face embeddings are ready, run the integrated
still-image command:

```powershell
.\.venv\Scripts\python.exe .\exam\analyze_exam_image.py `
  --plan .\exam\seat_plan.local.json `
  --image .\path\to\camera-reference.jpg `
  --json-output .\reports\exam\review.json
```

The default match distance threshold is inherited from the attendance
recognizer (`0.50`) and is **not independently validated**. Results use
`candidate_match_for_review`, `possible_assignment_mismatch_for_review`, and
`uncertain`; none are final decisions. A candidate or possible mismatch still
requires a teacher to inspect the evidence. Unknown faces are not assigned to a
nearest student. A low-distance candidate can still be wrong.

No image or detailed JSON is written unless an output path is supplied. A
detailed report includes student IDs and should stay in the ignored `reports/`
folder. `--annotated-output` explicitly saves a copy of the image; without it,
the input image is not modified.

## Compare observations from another identity provider

`compare_observations.py` can also compare a JSON observation payload from
another identity provider. Start from `templates/observations.template.json`
and replace its example exam ID, frame dimensions, and bounding boxes. Each
observation must set `identity_status` to `candidate`, `unknown`, or `uncertain`.
Only a `candidate` observation may contain `candidate_student_id`; the other
statuses must use `null`. The file format does not decide whether a model's
match is reliable.

Run the comparison:

```powershell
.\.venv\Scripts\python.exe .\exam\compare_observations.py `
  --plan .\exam\seat_plan.local.json `
  --observations .\exam\identity_observations.local.json `
  --output .\reports\exam\review.json
```

Every seat result requires teacher review. Matching IDs are only candidates for
review; different IDs are possible mismatches for review; missing, unknown,
duplicate, or overlapping observations remain uncertain. This tool does not
write attendance, change a review status, or make a final seating decision.
Observation files and detailed review reports may contain student IDs and must
remain local.
