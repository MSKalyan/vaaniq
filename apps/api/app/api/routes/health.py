from fastapi import APIRouter

router = APIRouter()


@router.get("/readyz", tags=["health"], summary="Readiness probe")
async def readiness() -> dict[str, str]:
    """Kubernetes-style readiness probe."""
    return {"status": "ready"}
