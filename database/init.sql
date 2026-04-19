CREATE DATABASE IF NOT EXISTS sbb_data;
USE sbb_data;

-- 1. LIVE-TABELLE (wird bei jedem Sync vollständig neu befüllt)
DROP TABLE IF EXISTS active_trains;
CREATE TABLE active_trains (
    trip_id        VARCHAR(100) PRIMARY KEY,
    origin         VARCHAR(100),
    destination    VARCHAR(100),
    delay          INT DEFAULT 0,
    departure_time DATETIME NULL,
    latitude       DECIMAL(10, 8),
    longitude      DECIMAL(11, 8),
    updated_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- 2. ARCHIV-TABELLE (permanent, nur Züge mit >= 20 Min Verspätung)
DROP TABLE IF EXISTS delay_archive;
CREATE TABLE delay_archive (
    id             INT AUTO_INCREMENT PRIMARY KEY,
    trip_id        VARCHAR(100) UNIQUE,
    origin         VARCHAR(100),
    destination    VARCHAR(100),
    delay          INT,
    departure_time DATETIME NULL,
    recorded_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
