import cv2
import os

student_id = input("Enter Student ID: ")

folder = f"dataset/{student_id}"

os.makedirs(folder, exist_ok=True)

face_detector = cv2.CascadeClassifier(
    cv2.data.haarcascades +
    "haarcascade_frontalface_default.xml"
)

cap = cv2.VideoCapture(0)

count = 0

while True:

    ret, frame = cap.read()

    if not ret:
        print("Could not access camera")
        break

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    faces = face_detector.detectMultiScale(
        gray,
        scaleFactor=1.1,
        minNeighbors=5
    )

    for (x, y, w, h) in faces:

        if len(faces) == 1:

            face = frame[y:y+h, x:x+w]

            face = cv2.resize(face, (200, 200))

            count += 1

            filename = f"{folder}/face_{count}.jpg"

            cv2.imwrite(filename, face)

            cv2.rectangle(
                frame,
                (x, y),
                (x+w, y+h),
                (255, 0, 0),
                2
            )

            cv2.putText(
                frame,
                f"Captured: {count}/20",
                (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                1,
                (0, 255, 0),
                2
            )

    cv2.imshow("Face Capture", frame)

    if cv2.waitKey(100) & 0xFF == ord("q"):
        break

    if count >= 20:
        break

cap.release()
cv2.destroyAllWindows()

print("Face data collection completed.")