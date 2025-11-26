CREATE DATABASE IF NOT EXISTS NextGenAI;
USE NextGenAI;


CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    full_name VARCHAR(100) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,
    company VARCHAR(100),
    job_title VARCHAR(100),
    phone VARCHAR(20),
    website VARCHAR(255),
    linkedin VARCHAR(255),
    industry VARCHAR(100),
    company_size VARCHAR(50),
    marketing_goals TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS user_linkedin_data (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    keywords JSON,
    tone_of_writing TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE KEY unique_user (user_id)
);



CREATE TABLE IF NOT EXISTS websites (
    id INT AUTO_INCREMENT PRIMARY KEY,
    
    user_id INT NOT NULL,
    domain VARCHAR(255),
    company_name VARCHAR(255),
    industry VARCHAR(255),
    company_mission TEXT,
    
    location VARCHAR(255),
    target_market JSON,

    primary_keywords JSON,
    secondary_keywords JSON,
    trending_topics JSON,
    industry_terms JSON,
    trend_keywords JSON,  

    target_audience TEXT,
    value_propositions JSON,
    content_themes JSON,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE KEY unique_user_domain (user_id, domain)
);
-- NEW: Products table to store products with categories
CREATE TABLE IF NOT EXISTS products (
    id INT AUTO_INCREMENT PRIMARY KEY,
    
    website_id INT NOT NULL,
    category VARCHAR(255),
    name VARCHAR(255),
    description TEXT,
    features JSON,
    pricing VARCHAR(255),
    keywords JSON,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (website_id) REFERENCES websites(id) ON DELETE CASCADE
);


CREATE TABLE IF NOT EXISTS user_json_uploads (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    json_data JSON NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY unique_user (user_id)
);
CREATE TABLE IF NOT EXISTS user_activities (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    activity_type VARCHAR(50) NOT NULL,
    activity_subtype VARCHAR(100),
    metadata JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_user_activity (user_id, activity_type, created_at),
    INDEX idx_created_at (created_at)
);
