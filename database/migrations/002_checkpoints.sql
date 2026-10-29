-- Add review-only periodic presence observations to an existing schema v1 DB.
USE smart_attendance;

CREATE TABLE IF NOT EXISTS class_sessions (
  session_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  session_label VARCHAR(120) NULL,
  started_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  checkpoint_interval_minutes SMALLINT UNSIGNED NOT NULL DEFAULT 20,
  PRIMARY KEY (session_id),
  CONSTRAINT chk_session_checkpoint_interval
    CHECK (checkpoint_interval_minutes > 0)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS class_session_events (
  event_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  session_id BIGINT UNSIGNED NOT NULL,
  event_type ENUM('ended') NOT NULL,
  event_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (event_id),
  KEY ix_session_event (session_id, event_at),
  CONSTRAINT fk_session_event_session
    FOREIGN KEY (session_id) REFERENCES class_sessions (session_id)
    ON DELETE RESTRICT
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS checkpoint_observations (
  observation_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  session_id BIGINT UNSIGNED NOT NULL,
  student_id VARCHAR(64) NOT NULL,
  window_start_at DATETIME NOT NULL,
  checkpoint_at DATETIME NOT NULL,
  observation_status ENUM('observed', 'not_observed') NOT NULL,
  review_status ENUM('pending', 'verified_present', 'confirmed_absent', 'inconclusive')
    NOT NULL DEFAULT 'pending',
  PRIMARY KEY (observation_id),
  UNIQUE KEY uq_checkpoint_student (session_id, student_id, checkpoint_at),
  KEY ix_checkpoint_time (checkpoint_at),
  CONSTRAINT fk_checkpoint_session
    FOREIGN KEY (session_id) REFERENCES class_sessions (session_id)
    ON DELETE RESTRICT,
  CONSTRAINT fk_checkpoint_student
    FOREIGN KEY (student_id) REFERENCES students (student_id)
    ON UPDATE CASCADE
    ON DELETE RESTRICT
) ENGINE=InnoDB;

INSERT IGNORE INTO schema_version (version_id) VALUES (2);
