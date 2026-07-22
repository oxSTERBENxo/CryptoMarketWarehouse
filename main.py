from fastapi import FastAPI, HTTPException

from analytics_routes import router as analytics_router
from database import get_connection

app = FastAPI(title="CryptoMarketWarehouse")
app.include_router(analytics_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "healthy"}


@app.get("/health/database")
def health_database() -> dict[str, str]:
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
    except Exception:
        raise HTTPException(status_code=503, detail="database unavailable")
    return {"status": "healthy"}
