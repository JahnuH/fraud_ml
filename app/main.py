from fastapi import FastAPI

from app.api.routes.simulator import router as simulator_router


app = FastAPI(
    title="Behavioural Anomaly Detection Backend",
    version="0.1.0",
    description="Phase 1 backend scaffold for synthetic transaction generation.",
)

app.include_router(simulator_router)


@app.get("/")
def root() -> dict[str, str]:
    return {"message": "Behavioural anomaly detection backend is running."}

