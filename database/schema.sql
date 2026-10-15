-- MySQL 8.0 schema for the Smart Attendance prototype.
-- This does not import data or change the current CSV-based application.

CREATE DATABASE IF NOT EXISTS smart_attendance
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE smart_attendance;

CREATE TABLE IF NOT EXISTS students (
  student_id VARCHAR(64) NOT NULL,
  display_name VARCHAR(120) NULL,
  is_active TINYINT(1) NOT NULL DEFAULT 1,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (student_id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS attendance (
  attendance_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  student_id VARCHAR(64) NOT NULL,
  attendance_date DATE NOT NULL,
  check_in_time TIME NOT NULL,
  recorded_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  detector_score DECIMAL(5,4) NULL,
  match_distance DECIMAL(6,5) NULL,
  source VARCHAR(24) NOT NULL DEFAULT 'face',
  PRIMARY KEY (attendance_id),
  UNIQUE KEY uq_attendance_student_day (student_id, attendance_date),
  KEY ix_attendance_date (attendance_date),
  CONSTRAINT fk_attendance_student
    FOREIGN KEY (student_id) REFERENCES students (student_id)
    ON UPDATE CASCADE
    ON DELETE RESTRICT
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS schema_version (
  version_id TINYINT UNSIGNED NOT NULL,
  applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (version_id)
) ENGINE=InnoDB;

INSERT IGNORE INTO schema_version (version_id) VALUES (1);
