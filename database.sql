-- ============================================================
-- Employee Leave Management System - MySQL schema + sample data
-- Usage:  mysql -u root -p < database.sql
-- ============================================================

CREATE DATABASE IF NOT EXISTS leave_management
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE leave_management;

DROP TABLE IF EXISTS leave_requests;
DROP TABLE IF EXISTS leave_balances;
DROP TABLE IF EXISTS users;

-- ------------------------------------------------------------
-- users
-- ------------------------------------------------------------
CREATE TABLE users (
    id          INT            NOT NULL AUTO_INCREMENT,
    name        VARCHAR(100)   NOT NULL,
    email       VARCHAR(120)   NOT NULL,
    password    VARCHAR(255)   NOT NULL,               -- Werkzeug password hash
    role        ENUM('employee', 'manager') NOT NULL DEFAULT 'employee',
    created_at  DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_users_email (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ------------------------------------------------------------
-- leave_balances (one row per user)
-- ------------------------------------------------------------
CREATE TABLE leave_balances (
    id            INT NOT NULL AUTO_INCREMENT,
    user_id       INT NOT NULL,
    casual_leave  INT NOT NULL DEFAULT 12,
    sick_leave    INT NOT NULL DEFAULT 10,
    earned_leave  INT NOT NULL DEFAULT 15,
    PRIMARY KEY (id),
    UNIQUE KEY uq_leave_balances_user (user_id),
    CONSTRAINT fk_leave_balances_user
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ------------------------------------------------------------
-- leave_requests
-- ------------------------------------------------------------
CREATE TABLE leave_requests (
    id                INT  NOT NULL AUTO_INCREMENT,
    user_id           INT  NOT NULL,
    leave_type        ENUM('Casual', 'Sick', 'Earned') NOT NULL,
    start_date        DATE NOT NULL,
    end_date          DATE NOT NULL,
    days              INT  NOT NULL,
    reason            TEXT NOT NULL,
    status            ENUM('Pending', 'Approved', 'Rejected') NOT NULL DEFAULT 'Pending',
    rejection_reason  TEXT NULL,
    applied_at        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY ix_leave_requests_user (user_id),
    CONSTRAINT fk_leave_requests_user
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ------------------------------------------------------------
-- Sample data
--   Manager : manager@company.com   / Manager@123
--   Employee: employee@company.com  / Employee@123
--   Others  : anita@company.com, rahul@company.com / Employee@123
-- Passwords below are Werkzeug hashes (never plain text).
-- ------------------------------------------------------------
INSERT INTO users (id, name, email, password, role) VALUES
(1, 'Priya Sharma', 'manager@company.com',  'scrypt:32768:8:1$z6sEkSi9H2WMZi2v$cd66d3b087b4ce813c05dcbe65ad5b394260c516ab49535d2cb666044139745a38212c0133ad07980713873e4cd2dbe3da23fd6ed0dd91bda310193e512e7dfa',  'manager'),
(2, 'John Doe',     'employee@company.com', 'scrypt:32768:8:1$ytrGRKDg3MGoOSPc$a67f03583f21bb77514c090be0141499623dabad2677c6bad4ab008916cb00a634426108e1a471c73f36eb5042c8380c41e52cbb91d4dbe32ec752cddd111bb5', 'employee'),
(3, 'Anita Rao',    'anita@company.com',    'scrypt:32768:8:1$ytrGRKDg3MGoOSPc$a67f03583f21bb77514c090be0141499623dabad2677c6bad4ab008916cb00a634426108e1a471c73f36eb5042c8380c41e52cbb91d4dbe32ec752cddd111bb5', 'employee'),
(4, 'Rahul Verma',  'rahul@company.com',    'scrypt:32768:8:1$ytrGRKDg3MGoOSPc$a67f03583f21bb77514c090be0141499623dabad2677c6bad4ab008916cb00a634426108e1a471c73f36eb5042c8380c41e52cbb91d4dbe32ec752cddd111bb5', 'employee');

INSERT INTO leave_balances (user_id, casual_leave, sick_leave, earned_leave) VALUES
(2, 10, 10, 15),
(3, 12,  8, 15),
(4, 12, 10, 15);

INSERT INTO leave_requests
    (user_id, leave_type, start_date, end_date, days, reason, status, rejection_reason) VALUES
(2, 'Casual', '2026-08-17', '2026-08-18', 2, 'Family function out of town.',          'Approved', NULL),
(2, 'Sick',   '2026-09-07', '2026-09-07', 1, 'Not feeling well, need rest.',          'Rejected', 'Critical release scheduled that day. Please reapply for another date.'),
(2, 'Earned', '2026-11-10', '2026-11-12', 3, 'Short vacation with family.',           'Pending',  NULL),
(3, 'Sick',   '2026-09-21', '2026-09-22', 2, 'Fever and doctor consultation.',        'Approved', NULL),
(3, 'Casual', '2026-11-16', '2026-11-17', 2, 'Personal work at the bank.',            'Pending',  NULL),
(4, 'Earned', '2026-12-21', '2026-12-24', 4, 'Year-end trip to hometown.',            'Pending',  NULL);
