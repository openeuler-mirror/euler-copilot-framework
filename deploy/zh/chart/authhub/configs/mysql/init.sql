CREATE DATABASE IF NOT EXISTS oauth2 DEFAULT CHARACTER SET utf8mb4 DEFAULT COLLATE utf8mb4_bin;
GRANT ALL ON `oauth2`.* TO 'authhub'@'%';
use oauth2;

SET FOREIGN_KEY_CHECKS = 0;

CREATE TABLE IF NOT EXISTS `manage_user` (
    `id` int NOT NULL AUTO_INCREMENT,
    `username` varchar(36) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL,
    `password` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL,
    PRIMARY KEY (`id`),
    UNIQUE KEY `username` (`username`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE IF NOT EXISTS `user` (
    `id` int NOT NULL AUTO_INCREMENT,
    `username` varchar(36) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL,
    `password` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL,
    `email` varchar(40) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin DEFAULT NULL,
    `phone` varchar(11) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin DEFAULT NULL,
    PRIMARY KEY (`id`),
    UNIQUE KEY `username` (`username`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE IF NOT EXISTS `oauth2_client` (
  `id` int  NOT NULL AUTO_INCREMENT,
  `app_name` varchar(48) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL,
  `username` varchar(36) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin DEFAULT NULL,
  `client_id` varchar(48) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin DEFAULT NULL,
  `client_secret` varchar(120) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin DEFAULT NULL,
  `client_id_issued_at` int NOT NULL,
  `client_secret_expires_at` int NOT NULL,
  `client_metadata` text,
  PRIMARY KEY (`id`),
  UNIQUE KEY `app_name` (`app_name`),
  UNIQUE KEY `client_id` (`client_id`),
  KEY `username` (`username`),
  KEY `ix_oauth2_client_client_id` (`client_id`),
  CONSTRAINT `oauth2_client_ibfk_1` FOREIGN KEY (`username`) REFERENCES `manage_user` (`username`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE IF NOT EXISTS `login_records` (
  `id` int  NOT NULL AUTO_INCREMENT,
  `username` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin DEFAULT NULL,
  `login_time` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin DEFAULT NULL,
  `client_id` varchar(48) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin DEFAULT NULL,
  `logout_url` varchar(200) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin DEFAULT NULL,
  PRIMARY KEY (`id`),
  CONSTRAINT `login_records_ibfk_1` FOREIGN KEY (`client_id`) REFERENCES `oauth2_client` (`client_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE IF NOT EXISTS `oauth2_client_scopes` (
  `id` int NOT NULL AUTO_INCREMENT,
  `username` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin  DEFAULT NULL,
  `client_id` int   DEFAULT NULL,
  `scopes` text CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL,
  `grant_at` int NOT NULL,
  `expires_in` int NOT NULL,
  PRIMARY KEY (`id`),
  CONSTRAINT `oauth2_client_scopes_ibfk_1` FOREIGN KEY (`client_id`) REFERENCES `oauth2_client` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE IF NOT EXISTS `oauth2_code` (
  `id` int  NOT NULL AUTO_INCREMENT,
  `username` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin DEFAULT NULL,
  `code` varchar(120) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL,
  `client_id` varchar(48) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin DEFAULT NULL,
  `redirect_uri` text CHARACTER SET utf8mb4 COLLATE utf8mb4_bin,
  `response_type` text CHARACTER SET utf8mb4 COLLATE utf8mb4_bin,
  `scope` text CHARACTER SET utf8mb4 COLLATE utf8mb4_bin,
  `nonce` text CHARACTER SET utf8mb4 COLLATE utf8mb4_bin,
  `auth_time` int  NOT NULL,
  `code_challenge` text CHARACTER SET utf8mb4 COLLATE utf8mb4_bin,
  `code_challenge_method` varchar(48) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE IF NOT EXISTS `oauth2_token` (
  `id` int  NOT NULL AUTO_INCREMENT,
  `user_id` int DEFAULT NULL,
  `username` varchar(36) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL,
  `client_id` varchar(48) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL,
  `token_metadata` text CHARACTER SET utf8mb4 COLLATE utf8mb4_bin,
  `refresh_token_expires_in` int NOT NULL,
  `token_type` varchar(40) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin DEFAULT NULL,
  `access_token` varchar(4096) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL,
  `refresh_token` varchar(4096) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin DEFAULT NULL,
  `scope` text CHARACTER SET utf8mb4 COLLATE utf8mb4_bin,
  `issued_at` int NOT NULL,
  `access_token_revoked_at` int NOT NULL,
  `refresh_token_revoked_at` int NOT NULL,
  `expires_in` int NOT NULL,
  PRIMARY KEY (`id`),
  KEY `user_id` (`user_id`),
  CONSTRAINT `oauth2_token_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`) ON DELETE CASCADE,
  CONSTRAINT `oauth2_token_ibfk_2` FOREIGN KEY (`client_id`) REFERENCES `oauth2_client` (`client_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

SET FOREIGN_KEY_CHECKS = 1;

SET @username := "admin";
SET @password := "pbkdf2:sha256:260000$LEwtriXN8UQ1UIA7$4de6cc1d67263c6579907eab7c1cba7c7e857b32e957f9ff5429592529d7d1b0";
SET @manage_username := "administrator";

INSERT INTO user (username, password)
SELECT @username, @password
FROM DUAL
WHERE NOT EXISTS(SELECT 1 FROM user WHERE username = @username);
INSERT INTO manage_user (username, password)
SELECT @manage_username, @password
FROM DUAL
WHERE NOT EXISTS(SELECT 1 FROM manage_user WHERE username = @username);