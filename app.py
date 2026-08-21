import os
import time

import psycopg2
from fastapi import FastAPI

app = FastAPI()

# settings come from the ENVIRONMENT - never hardcoded.
# DB_HOST will be the container NAME ("db") - Docker DNS resolves it.
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASS = os.getenv("DB_PASS", "secret123")


def get_conn():
    return psycopg2.connect(host=DB_HOST, user=DB_USER, password=DB_PASS, dbname="postgres")


@app.on_event("startup")
def init_db():
    # retry a few times - the db container may still be starting
    for attempt in range(10):
        try:
            conn = get_conn()
            with conn, conn.cursor() as cur:
                cur.execute("""CREATE TABLE IF NOT EXISTS predictions (
                    id SERIAL PRIMARY KEY,
                    x FLOAT NOT NULL,
                    result FLOAT NOT NULL,
                    created_at TIMESTAMP DEFAULT NOW())""")
            conn.close()
            print(f"connected to db at host '{DB_HOST}' - table ready")
            return
        except psycopg2.OperationalError as e:
            print(f"db not ready (attempt {attempt + 1}/10): {e}")
            time.sleep(2)
    raise RuntimeError(f"could not reach the database at host '{DB_HOST}'")


@app.get("/predict")
def predict(x: float):
    result = x * 2
    conn = get_conn()
    with conn, conn.cursor() as cur:
        cur.execute("INSERT INTO predictions (x, result) VALUES (%s, %s)", (x, result))
    conn.close()
    return {"prediction": result, "saved": True}


@app.get("/history")
def history():
    conn = get_conn()
    with conn, conn.cursor() as cur:
        cur.execute("SELECT x, result, created_at FROM predictions ORDER BY id DESC LIMIT 10")
        rows = [{"x": r[0], "result": r[1], "at": str(r[2])} for r in cur.fetchall()]
    conn.close()
    return {"count": len(rows), "recent": rows}


@app.get("/health")
def health():
    return {"status": "ok"}