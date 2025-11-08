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