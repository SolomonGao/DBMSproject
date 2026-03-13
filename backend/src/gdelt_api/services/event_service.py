"""Event service for GDELT event operations."""

from datetime import timedelta
from typing import Any

from sqlalchemy import and_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from gdelt_api.core.exceptions import NotFoundError, ValidationError
from gdelt_api.core.logging import get_logger
from gdelt_api.models.event import EventQuery, GDELTEvent

logger = get_logger(__name__)


class EventService:
    """Service for GDELT event operations."""
    
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
    
    async def search_events(
        self,
        query: EventQuery,
    ) -> tuple[list[GDELTEvent], int]:
        """Search events with filters."""
        
        # Build base query
        sql = select(GDELTEvent)
        conditions = []
        
        # Date range
        if query.start_date:
            conditions.append(GDELTEvent.date >= query.start_date)
        if query.end_date:
            conditions.append(GDELTEvent.date <= query.end_date)
        
        # Actors
        if query.actor1_name:
            conditions.append(
                GDELTEvent.actor1_name.ilike(f"%{query.actor1_name}%")
            )
        if query.actor2_name:
            conditions.append(
                GDELTEvent.actor2_name.ilike(f"%{query.actor2_name}%")
            )
        
        # Country
        if query.country_code:
            conditions.append(GDELTEvent.location_country_code == query.country_code)
        
        # Event filters
        if query.event_code:
            conditions.append(GDELTEvent.event_code == query.event_code)
        if query.event_root_code:
            conditions.append(GDELTEvent.event_root_code == query.event_root_code)
        if query.quad_class:
            conditions.append(GDELTEvent.quad_class == query.quad_class)
        
        # Tone
        if query.min_tone is not None:
            conditions.append(GDELTEvent.avg_tone >= query.min_tone)
        if query.max_tone is not None:
            conditions.append(GDELTEvent.avg_tone <= query.max_tone)
        
        # Location bounds
        if query.lat_min is not None:
            conditions.append(GDELTEvent.location.lat >= query.lat_min)
        if query.lat_max is not None:
            conditions.append(GDELTEvent.location.lat <= query.lat_max)
        if query.lon_min is not None:
            conditions.append(GDELTEvent.location.lon >= query.lon_min)
        if query.lon_max is not None:
            conditions.append(GDELTEvent.location.lon <= query.lon_max)
        
        if conditions:
            sql = sql.where(and_(*conditions))
        
        # Count total
        count_sql = select(text("COUNT(*)")).select_from(sql.subquery())
        total_result = await self.session.execute(count_sql)
        total = total_result.scalar() or 0
        
        # Sorting
        sort_column = getattr(GDELTEvent, query.sort_by, GDELTEvent.date)
        if query.sort_order == "desc":
            sql = sql.order_by(sort_column.desc())
        else:
            sql = sql.order_by(sort_column.asc())
        
        # Pagination
        offset = (query.page - 1) * query.page_size
        sql = sql.offset(offset).limit(query.page_size)
        
        # Execute
        result = await self.session.execute(sql)
        events = result.scalars().all()
        
        logger.debug(
            "events_searched",
            filters=len(conditions),
            results=len(events),
            total=total,
        )
        
        return list(events), total
    
    async def get_event(self, event_id: int) -> GDELTEvent:
        """Get a single event by ID."""
        result = await self.session.execute(
            select(GDELTEvent).where(GDELTEvent.id == event_id)
        )
        event = result.scalar_one_or_none()
        
        if not event:
            raise NotFoundError(f"Event with ID {event_id} not found")
        
        return event
    
    async def get_events_by_date_range(
        self,
        start_date: str,
        end_date: str,
        country_code: str | None = None,
    ) -> list[GDELTEvent]:
        """Get events in a date range."""
        from datetime import datetime
        
        try:
            start = datetime.strptime(start_date, "%Y-%m-%d").date()
            end = datetime.strptime(end_date, "%Y-%m-%d").date()
        except ValueError:
            raise ValidationError("Invalid date format. Use YYYY-MM-DD")
        
        if start > end:
            raise ValidationError("Start date must be before end date")
        
        query = EventQuery(start_date=start, end_date=end, country_code=country_code)
        events, _ = await self.search_events(query)
        
        return events
    
    async def get_related_events(
        self,
        event_id: int,
        days_before: int = 7,
        days_after: int = 1,
    ) -> list[GDELTEvent]:
        """Get events related to a target event (antecedent search)."""
        # Get the target event
        target = await self.get_event(event_id)
        
        # Define time range
        start_date = target.date - timedelta(days=days_before)
        end_date = target.date + timedelta(days=days_after)
        
        # Search in same geographic area and with same actors
        query = EventQuery(
            start_date=start_date,
            end_date=end_date,
            country_code=target.location_country_code,
        )
        
        events, _ = await self.search_events(query)
        
        # Filter out the target itself and sort by date
        related = [e for e in events if e.id != event_id]
        related.sort(key=lambda e: e.date)
        
        logger.info(
            "related_events_found",
            target_id=event_id,
            time_range=f"{start_date} to {end_date}",
            related_count=len(related),
        )
        
        return related
