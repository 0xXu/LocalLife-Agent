-- ============================================================
-- DataGrip MySQL Setup Script
-- 在 DataGrip 中新建 MySQL 连接后，复制此文件全部执行
-- 数据库: liquidroute
-- ============================================================

CREATE DATABASE IF NOT EXISTS liquidroute
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE liquidroute;

-- 用户表: 注册用户信息
CREATE TABLE IF NOT EXISTS users (
    id              BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id         VARCHAR(50)  NOT NULL UNIQUE,
    name            VARCHAR(100) NOT NULL,
    password_hash   VARCHAR(255),
    profile_name    VARCHAR(100),
    preferred_city  VARCHAR(50) DEFAULT '北京',
    provider_name   VARCHAR(50) DEFAULT 'deepseek',
    deepseek_api_key VARCHAR(255),
    avatar_idx      INT DEFAULT 0,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- 用户收藏表: 按 userId 隔离
CREATE TABLE IF NOT EXISTS user_favorites (
    id          BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id     VARCHAR(50)  NOT NULL,
    route_json  TEXT         NOT NULL,
    route_name  VARCHAR(200),
    scene       VARCHAR(100),
    poi_count   INT DEFAULT 0,
    total_time  VARCHAR(50),
    total_cost  INT DEFAULT 0,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_fav_user (user_id)
) ENGINE=InnoDB;

-- 用户历史对话表: 按 userId + sessionId 隔离
CREATE TABLE IF NOT EXISTS user_history (
    id          BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id     VARCHAR(50)  NOT NULL,
    session_id  VARCHAR(50)  NOT NULL,
    query_text  TEXT,
    scene       VARCHAR(100),
    routes_json TEXT,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_hist_user (user_id),
    INDEX idx_hist_session (session_id)
) ENGINE=InnoDB;

-- 种子: 3 个 mock 用户
INSERT INTO users (user_id, name, profile_name, preferred_city) VALUES
('user_001', '小林', '约会偏好型', '上海'),
('user_002', '阿航', '效率通勤型', '北京'),
('user_003', 'Mia',   '探店内容型', '上海')
ON DUPLICATE KEY UPDATE name = VALUES(name);
