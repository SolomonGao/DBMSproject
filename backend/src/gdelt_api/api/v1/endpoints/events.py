"""Event endpoints."""

from fastapi import APIRouter, Depends, Query, status

from gdelt_api.api.dependencies import get_event_service
from gdelt_api.models.common import APIResponse, PaginatedResponse, PaginationMeta
from gdelt_api.models.event import EventQuery, GDELTEvent
from gdelt_api.services import EventService

router = APIRouter()


@router.get(
    "",
    response_model=APIResponse[PaginatedResponse[GDELTEvent]],
    summary="Search events",
    description="Search GDELT events with various filters.",
)
async def search_events(
    query: EventQuery = Depends(),
    event_service: EventService = Depends(get_event_service),
) -> APIResponse[PaginatedResponse[GDELTEvent]]:
    """Search GDELT events."""
    events, total = await event_service.search_events(query)
    
    total_pages = (total + query.page_size - 1) // query.page_size
    
    paginated = PaginatedResponse(
        items=events,
        pagination=PaginationMeta(
            page=query.page,
            page_size=query.page_size,
            total=total,
            total_pages=total_pages,
            has_next=query.page < total_pages,
            has_prev=query.page > 1,
        ),
    )
    
    return APIResponse(success=True, data=paginated)


@router.get(
    "/{event_id}",
    response_model=APIResponse[GDELTEvent],
    summary="Get event by ID",
)
async def get_event(
    event_id: int,
    event_service: EventService = Depends(get_event_service),
) -> APIResponse[GDELTEvent]:
    """Get a specific event by its ID."""
    event = await event_service.get_event(event_id)
    
    return APIResponse(success=True, data=event)


@router.get(
    "/{event_id}/related",
    response_model=APIResponse[list[GDELTEvent]],
    summary="Get related events",
    description="Get events related to the target event (antecedent analysis).",
)
async def get_related_events(
    event_id: int,
    days_before: int = Query(default=7, ge=1, le=30),
    days_after: int = Query(default=1, ge=0, le=7),
    event_service: EventService = Depends(get_event_service),
) -> APIResponse[list[GDELTEvent]]:
    """Get events related to a target event for narrative analysis."""
    events = await event_service.get_related_events(
        event_id,
        days_before=days_before,
        days_after=days_after,
    )
    
    return APIResponse(
        success=True,
        data=events,
        meta={"count": len(events)},
    )
