import uvicorn
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.routes.simulator import router as simulator_router
from app.db.postgres import get_sqlalchemy_engine


app = FastAPI(
    title="Behavioural Anomaly Detection Backend",
    version="0.1.0",
    description="Phase 1 backend scaffold for synthetic transaction generation.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/frms/behaviour/health")
def healthcheck() -> dict[str, object]:
    db_status = "ok"
    counts = {
        "raw_transactions": None,
        "behavioural_profiles": None,
        "scoring_results": None,
        "behavioural_config": None,
    }

    engine = get_sqlalchemy_engine()
    try:
        with engine.begin() as connection:
            connection.execute(text("SELECT 1"))
            counts["raw_transactions"] = int(connection.execute(text("SELECT COUNT(*) FROM raw_transactions")).scalar() or 0)
            counts["behavioural_profiles"] = int(
                connection.execute(text("SELECT COUNT(*) FROM behavioural_profiles")).scalar() or 0
            )
            counts["scoring_results"] = int(connection.execute(text("SELECT COUNT(*) FROM scoring_results")).scalar() or 0)
            counts["behavioural_config"] = int(
                connection.execute(text("SELECT COUNT(*) FROM behavioural_config")).scalar() or 0
            )
    except Exception as exc:
        db_status = f"error: {exc}"
    finally:
        engine.dispose()

    overall_status = "ok" if db_status == "ok" else "degraded"
    return {
        "status": overall_status,
        "service": "frms-behaviour-engine",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "database": {
            "status": db_status,
            "table_counts": counts,
        },
    }


app.include_router(simulator_router)


if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8002)
