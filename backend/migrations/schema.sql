-- ============================================================================
-- BloodLink - MySQL schema
-- This mirrors backend/app/models.py exactly. In development, FastAPI's
-- startup event (Base.metadata.create_all) will create these tables for you
-- automatically the first time you run the server against an empty database
-- named in DATABASE_URL. This file is provided so the schema is also
-- reviewable/runnable independently, and as the basis for future migrations.
-- ============================================================================

CREATE DATABASE IF NOT EXISTS bloodlink CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE bloodlink;

-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    full_name VARCHAR(120) NOT NULL,
    email VARCHAR(150) NOT NULL UNIQUE,
    phone VARCHAR(20) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role ENUM('donor','recipient','admin') NOT NULL DEFAULT 'recipient',
    is_phone_verified BOOLEAN NOT NULL DEFAULT FALSE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NULL ON UPDATE CURRENT_TIMESTAMP,
    INDEX ix_users_email (email),
    INDEX ix_users_phone (phone)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS otp_codes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    code_hash VARCHAR(255) NOT NULL,
    purpose VARCHAR(30) NOT NULL DEFAULT 'phone_verification',
    expires_at DATETIME NOT NULL,
    consumed BOOLEAN NOT NULL DEFAULT FALSE,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX ix_otp_user (user_id)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS revoked_tokens (
    id INT AUTO_INCREMENT PRIMARY KEY,
    jti VARCHAR(64) NOT NULL UNIQUE,
    revoked_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX ix_revoked_jti (jti)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS donors (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL UNIQUE,
    blood_group ENUM('A+','A-','B+','B-','AB+','AB-','O+','O-') NOT NULL,
    age INT NOT NULL,
    city VARCHAR(100) NOT NULL,
    latitude DOUBLE NOT NULL,
    longitude DOUBLE NOT NULL,
    last_donation_date DATE NULL,
    is_available BOOLEAN NOT NULL DEFAULT TRUE,
    total_donations INT NOT NULL DEFAULT 0,
    previous_requests INT NOT NULL DEFAULT 0,
    previous_accepts INT NOT NULL DEFAULT 0,
    historical_response_rate DOUBLE NOT NULL DEFAULT 0,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NULL ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX ix_donor_group_avail_city (blood_group, is_available, city)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS hospitals (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(150) NOT NULL,
    address VARCHAR(255) NOT NULL,
    city VARCHAR(100) NOT NULL,
    latitude DOUBLE NOT NULL,
    longitude DOUBLE NOT NULL,
    is_verified BOOLEAN NOT NULL DEFAULT FALSE,
    contact VARCHAR(20) NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX ix_hospital_city (city),
    INDEX ix_hospital_verified (is_verified)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS blood_requests (
    id INT AUTO_INCREMENT PRIMARY KEY,
    requester_id INT NOT NULL,
    hospital_id INT NOT NULL,
    blood_group ENUM('A+','A-','B+','B-','AB+','AB-','O+','O-') NOT NULL,
    units_required INT NOT NULL DEFAULT 1,
    urgency ENUM('low','medium','high','critical') NOT NULL DEFAULT 'medium',
    status ENUM('created','hospital_selected','compatibility_checked','donors_found',
                'donors_ranked','request_sent','donor_accepted','fulfilled','closed','expired')
           NOT NULL DEFAULT 'created',
    notes TEXT NULL,
    patient_name VARCHAR(120) NULL,
    contact_name VARCHAR(120) NULL,
    contact_phone VARCHAR(20) NULL,
    ward_info VARCHAR(150) NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    fulfilled_at DATETIME NULL,
    FOREIGN KEY (requester_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (hospital_id) REFERENCES hospitals(id),
    INDEX ix_request_status_group (status, blood_group)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS donor_responses (
    id INT AUTO_INCREMENT PRIMARY KEY,
    request_id INT NOT NULL,
    donor_id INT NOT NULL,
    match_score DOUBLE NULL,
    distance_km DOUBLE NULL,
    response ENUM('pending','accepted','declined') NOT NULL DEFAULT 'pending',
    notified_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    responded_at DATETIME NULL,
    FOREIGN KEY (request_id) REFERENCES blood_requests(id) ON DELETE CASCADE,
    FOREIGN KEY (donor_id) REFERENCES donors(id) ON DELETE CASCADE,
    UNIQUE KEY uq_request_donor (request_id, donor_id)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS notifications (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    title VARCHAR(150) NOT NULL,
    message TEXT NOT NULL,
    type VARCHAR(40) NOT NULL DEFAULT 'general',
    related_request_id INT NULL,
    is_read BOOLEAN NOT NULL DEFAULT FALSE,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (related_request_id) REFERENCES blood_requests(id),
    INDEX ix_notif_user_read (user_id, is_read)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS reports (
    id INT AUTO_INCREMENT PRIMARY KEY,
    reporter_id INT NOT NULL,
    request_id INT NULL,
    reason VARCHAR(120) NOT NULL,
    description TEXT NULL,
    status ENUM('open','reviewing','resolved','dismissed') NOT NULL DEFAULT 'open',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (reporter_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (request_id) REFERENCES blood_requests(id) ON DELETE SET NULL
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS donation_history (
    id INT AUTO_INCREMENT PRIMARY KEY,
    donor_id INT NOT NULL,
    request_id INT NULL,
    hospital_id INT NULL,
    donation_date DATE NOT NULL,
    units_donated INT NOT NULL DEFAULT 1,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (donor_id) REFERENCES donors(id) ON DELETE CASCADE,
    FOREIGN KEY (request_id) REFERENCES blood_requests(id),
    FOREIGN KEY (hospital_id) REFERENCES hospitals(id)
) ENGINE=InnoDB;
