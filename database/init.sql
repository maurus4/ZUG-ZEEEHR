CREATE DATABASE IF NOT EXISTS sbb_data;
USE sbb_data;

-- 1. LIVE-TABELLE (Schlank, wird ständig aktualisiert)
DROP TABLE IF EXISTS active_trains;
CREATE TABLE active_trains (
    trip_id VARCHAR(50) PRIMARY KEY, -- Überschreibt den Zug, wenn er schon da ist
    origin VARCHAR(100),
    destination VARCHAR(100),
    delay INT DEFAULT 0,
    latitude DECIMAL(10, 8),
    longitude DECIMAL(11, 8),
    route_data JSON,                 -- Die PassList für die Karte
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- 2. ARCHIV-TABELLE (Permanent für Verspätungen > 20 Min)
DROP TABLE IF EXISTS delay_archive;
CREATE TABLE delay_archive (
    id INT AUTO_INCREMENT PRIMARY KEY,
    trip_id VARCHAR(50),
    origin VARCHAR(100),
    destination VARCHAR(100),
    delay INT,
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, -- Wann wurde der Fehler geloggt?
    route_data JSON                  -- Damit man die Strecke auch später noch sieht
);