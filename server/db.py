import mysql.connector

DB_CONFIG = {
    "host":     "192.168.0.16",
    "user":     "chemibot",
    "password": "1111",
    "database": "sterilebot",
    "charset":  "utf8mb4",
}

def get_db():
    return mysql.connector.connect(**DB_CONFIG)