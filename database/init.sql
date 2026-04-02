CREATE DATABASE IF NOT EXISTS sbb_data;
USE sbb_data;

CREATE TABLE IF NOT EXISTS radar_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    trip_id VARCHAR(100) NOT NULL, -- Eindeutige ID des Zuges/Laufs
    latitude DECIMAL(10, 8) NOT NULL,
    longitude DECIMAL(11, 8) NOT NULL,
    speed INT,                     -- Geschwindigkeit in km/h
    recorded_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX (trip_id),               -- Index für schnelles Suchen nach Zug-Historie
    INDEX (recorded_at)            -- Index für Zeitabfragen (Caching-Check)
);