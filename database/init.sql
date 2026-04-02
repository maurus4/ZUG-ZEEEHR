CREATE DATABASE IF NOT EXISTS sbb_data;
USE sbb_data;

CREATE TABLE IF NOT EXISTS radar_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    trip_id VARCHAR(50),
    latitude DECIMAL(10, 8),
    longitude DECIMAL(11, 8),
    delay INT DEFAULT 0,
    origin VARCHAR(100),        -- NEU: Aktueller Haltepunkt / Start
    destination VARCHAR(100),   -- Zielort
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);