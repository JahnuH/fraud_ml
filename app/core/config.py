import os
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parents[2]
OUTPUT_DIR = BASE_DIR / "data" / "output"
DEFAULT_CSV_PATH = OUTPUT_DIR / "transactions.csv"
SCHEMA_PATH = BASE_DIR / "db" / "schema.sql"
ENV_PATH = BASE_DIR / ".env"

load_dotenv(ENV_PATH)

DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_HOST = os.getenv("DB_HOST", "")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "behaviour_db")
