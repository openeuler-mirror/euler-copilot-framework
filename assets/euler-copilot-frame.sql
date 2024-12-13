CREATE TABLE `user` (
    `id` bigint unsigned NOT NULL AUTO_INCREMENT,
    `user_sub` varchar(100) NOT NULL,
    `passwd` varchar(100) DEFAULT NULL,
    `organization` varchar(100) DEFAULT NULL,
    `created_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `login_time` datetime DEFAULT NULL,
    `revision_number` varchar(100) DEFAULT NULL,
    `credit` int unsigned NOT NULL DEFAULT 100,
    `is_whitelisted` boolean NOT NULL DEFAULT 0,
    PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

CREATE TABLE `audit_log` (
    `id` bigint unsigned NOT NULL AUTO_INCREMENT,
    `user_sub` varchar(100) DEFAULT NULL,
    `method_type` varchar(100) DEFAULT NULL,
    `source_name` varchar(100) DEFAULT NULL,
    `ip` varchar(100) DEFAULT NULL,
    `result` varchar(100) DEFAULT NULL,
    `reason` varchar(100) DEFAULT NULL,
    `created_time` datetime DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=1 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

CREATE TABLE `comment` (
    `id` bigint unsigned NOT NULL AUTO_INCREMENT,
    `qa_record_id` varchar(100) NOT NULL UNIQUE,
    `is_like` boolean DEFAULT NULL,
    `dislike_reason` varchar(100) DEFAULT NULL,
    `reason_link` varchar(200) DEFAULT NULL,
    `reason_description` varchar(500) DEFAULT NULL,
    `created_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `user_sub` varchar(100) DEFAULT NULL,
    PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=1 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

CREATE TABLE `user_qa_record` (
    `id` bigint unsigned NOT NULL AUTO_INCREMENT,
    `user_qa_record_id` varchar(100) NOT NULL UNIQUE,
    `user_sub` varchar(100) NOT NULL,
    `title` varchar(200) NOT NULL,
    `created_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=1 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

CREATE TABLE `qa_record` (
    `id` bigint unsigned NOT NULL AUTO_INCREMENT,
    `user_qa_record_id` varchar(100) NOT NULL,
    `encrypted_question` text NOT NULL,
    `question_encryption_config` varchar(1000) NOT NULL,
    `encrypted_answer` text NOT NULL,
    `answer_encryption_config` varchar(1000) NOT NULL,
    `created_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `qa_record_id` varchar(100) NOT NULL UNIQUE,
    `group_id` varchar(100) DEFAULT NULL,
    PRIMARY KEY (`id`),
    KEY `idx_user_qa_record_id` (`user_qa_record_id`) USING BTREE
) ENGINE=InnoDB AUTO_INCREMENT=1 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

CREATE TABLE `api_key` (
    `id` bigint unsigned NOT NULL AUTO_INCREMENT,
    `user_sub` varchar(100) NOT NULL,
    `api_key_hash` varchar(16) NOT NULL,
    `created_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=1 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

CREATE TABLE `question_blacklist` (
    `id` bigint unsigned NOT NULL AUTO_INCREMENT,
    `question` text NOT NULL,
    `answer` text NOT NULL,
    `is_audited` boolean NOT NULL DEFAULT FALSE,
    `reason_description` varchar(200) DEFAULT NULL,
    `created_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=1 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
