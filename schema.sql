CREATE DATABASE IF NOT EXISTS cs2_events DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE cs2_events;

CREATE TABLE IF NOT EXISTS events (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    org VARCHAR(100) NOT NULL,
    level VARCHAR(50) NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    location VARCHAR(255) NOT NULL,
    prize BIGINT NOT NULL,
    champion VARCHAR(100),
    runnerup VARCHAR(100),
    mvp VARCHAR(100),
    score VARCHAR(20),
    champion_roster JSON,
    runnerup_roster JSON
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


CREATE TABLE IF NOT EXISTS site_settings (
    setting_key VARCHAR(50) PRIMARY KEY,
    setting_value VARCHAR(255) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

INSERT INTO site_settings (setting_key, setting_value)
VALUES ('last_modified', DATE_FORMAT(NOW(), '%Y-%m-%d %H:%i:%s'))
ON DUPLICATE KEY UPDATE setting_key = setting_key;