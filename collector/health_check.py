
import os
import time
import logging
from datetime import datetime, timezone

import psutil
import psycopg2

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

DB_HOST = os.environ["DB_HOST"]
DB_NAME = os.environ["DB_NAME"]
DB_USER = os.environ["DB_USER"]
DB_PASSWORD = os.environ["DB_PASSWORD"]
DB_PORT = os.getenv("DB_PORT", "5432")


def connect_database():
    while True:
        try:
            conn = psycopg2.connect(
                host=DB_HOST,
                database=DB_NAME,
                user=DB_USER,
                password=DB_PASSWORD,
                port=DB_PORT,
                connect_timeout=5
            )

            logging.info("Connected to PostgreSQL successfully.")
            return conn

        except psycopg2.OperationalError as error:
            logging.error("Database not ready: %s", error)
            logging.info("Retrying in 5 seconds...")
            time.sleep(5)


def create_table(conn):
    with conn.cursor() as cursor:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS health_metrics (
                id SERIAL PRIMARY KEY,
                collected_at TIMESTAMPTZ NOT NULL,
                cpu_percent REAL NOT NULL,
                memory_percent REAL NOT NULL,
                disk_percent REAL NOT NULL,
                uptime_seconds DOUBLE PRECISION NOT NULL
            );
        """)

    conn.commit()
    logging.info("Health metrics table is ready.")


def collect_metrics():
    cpu = psutil.cpu_percent(interval=1)
    memory = psutil.virtual_memory().percent
    disk = psutil.disk_usage("/").percent
    uptime = time.time() - psutil.boot_time()

    return {
        "collected_at": datetime.now(timezone.utc),
        "cpu_percent": cpu,
        "memory_percent": memory,
        "disk_percent": disk,
        "uptime_seconds": uptime
    }


def save_metrics(conn, metrics):
    with conn.cursor() as cursor:
        cursor.execute("""
            INSERT INTO health_metrics (
                collected_at,
                cpu_percent,
                memory_percent,
                disk_percent,
                uptime_seconds
            )
            VALUES (%s, %s, %s, %s, %s)
        """, (
            metrics["collected_at"],
            metrics["cpu_percent"],
            metrics["memory_percent"],
            metrics["disk_percent"],
            metrics["uptime_seconds"]
        ))

    conn.commit()


def main():
    conn = connect_database()
    create_table(conn)

    logging.info("Health collector started.")

    while True:
        try:
            metrics = collect_metrics()
            save_metrics(conn, metrics)

            logging.info(
                "CPU: %.2f%% | Memory: %.2f%% | Disk: %.2f%% | Uptime: %.2f seconds",
                metrics["cpu_percent"],
                metrics["memory_percent"],
                metrics["disk_percent"],
                metrics["uptime_seconds"]
            )

            time.sleep(30)

        except (psycopg2.OperationalError, psycopg2.InterfaceError) as error:
            logging.error("Database connection lost: %s", error)

            try:
                conn.close()
            except Exception:
                pass

            conn = connect_database()
            create_table(conn)

        except Exception:
            logging.exception("Unexpected collector error.")
            time.sleep(5)


if __name__ == "__main__":
    main()

