import os
import sqlite3

DATABASE = os.path.join(os.path.dirname(__file__), "patients.db")


def get_connection():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    return connection


def create_table():
    connection = get_connection()

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS patients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            abha_id TEXT,
            age INTEGER,
            gender TEXT,
            complaint TEXT,
            history TEXT,
            symptoms TEXT,
            medications TEXT,
            allergies TEXT,
            medical_history TEXT,
            summary TEXT
        )
        """
    )

    connection.commit()
    connection.close()
