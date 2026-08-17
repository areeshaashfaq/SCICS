from fastapi import APIRouter
from retrain import run_retraining

router = APIRouter(prefix="/retrain", tags=["retrain"])

@router.post("/")
def trigger_retraining():
    result = run_retraining()
    return {
        "message": "Retraining complete",
        "learned": result["learned"],
        "skipped": result["skipped"]
    }