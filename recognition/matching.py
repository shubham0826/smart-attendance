"""Shared face-embedding matching helper used by class and exam flows."""

import face_recognition
import numpy as np


# Prototype default retained from the original attendance recognizer. It has
# not been validated against independent unknown-person data.
MATCH_THRESHOLD = 0.50


def find_best_candidate(known_encodings, known_ids, encoding, threshold=MATCH_THRESHOLD):
    """Return the nearest ID, its distance, and whether it passes the threshold."""
    distances = face_recognition.face_distance(known_encodings, encoding)
    best_index = int(np.argmin(distances))
    distance = float(distances[best_index])
    return str(known_ids[best_index]), distance, distance <= threshold
