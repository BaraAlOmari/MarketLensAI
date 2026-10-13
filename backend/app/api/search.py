import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request

from app.models.search import SearchRequest, SearchResponse
from app.providers.retry import QuotaExhaustedError
from app.retrieval.service import SearchService, SearchUnavailableError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")


def get_search_service(request: Request) -> SearchService:
    return request.app.state.search_service


@router.post("/search", response_model=SearchResponse)
async def search(
    body: SearchRequest, service: Annotated[SearchService, Depends(get_search_service)]
) -> SearchResponse:
    try:
        return await service.search(body)
    except SearchUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except QuotaExhaustedError as exc:
        raise HTTPException(
            status_code=429, detail="embedding quota exhausted for today; try again later"
        ) from exc
    except Exception as exc:
        logger.exception("search failed")
        raise HTTPException(status_code=502, detail="search failed upstream") from exc
