from fastapi import APIRouter, HTTPException, Query

from app.models.schemas import BehaviorScoringRequest, BehaviorScoringResponse
from app.services.modeling import HybridBehaviorScorer
from app.services.simulator import TransactionSimulator


router = APIRouter(tags=["simulator"])


@router.get("/simulator/health")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/simulator/preview")
def preview_simulation(
    months: int = Query(4, ge=3, le=6),
    seed: int = Query(42, ge=0),
) -> dict[str, object]:
    try:
        simulator = TransactionSimulator(months=months, seed=seed)
        transactions, summary = simulator.generate()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "summary": summary.model_dump(),
        "sample_transactions": transactions.head(10).to_dict(orient="records"),
    }


@router.post("/score-behavior", response_model=BehaviorScoringResponse)
def score_behavior(request: BehaviorScoringRequest) -> BehaviorScoringResponse:
    try:
        scorer = HybridBehaviorScorer(account_id=request.account_id)
        result = scorer.score_realtime_transaction(request.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return BehaviorScoringResponse(
        behavior_score=result["behavior_score"],
        behavior_change=result["behavior_change"],
        reasons=result["reasons"],
    )
