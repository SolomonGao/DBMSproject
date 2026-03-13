"""GDELT Event models."""

from datetime import date as Date
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field


class GeoPoint(BaseModel):
    """Geographic point model."""
    
    lat: Decimal = Field(..., description="Latitude")
    lon: Decimal = Field(..., description="Longitude")
    name: str | None = Field(None, description="Location name")
    country_code: str | None = Field(None, description="Country code")


class Actor(BaseModel):
    """Event actor model."""
    
    name: str | None = Field(None, description="Actor name")
    country_code: str | None = Field(None, description="Country code")
    type_code: str | None = Field(None, description="Actor type code")


class GDELTEvent(BaseModel):
    """GDELT Event model."""
    
    id: int = Field(..., alias="GlobalEventID", description="Unique event ID")
    event_date: Date = Field(..., alias="SQLDATE", description="Event date")
    month_year: int | None = Field(None, alias="MonthYear", description="Month-year")
    date_added: datetime | None = Field(None, alias="DATEADDED", description="Date added")
    
    # Actors
    actor1: Actor | None = Field(None, description="Primary actor")
    actor2: Actor | None = Field(None, description="Secondary actor")
    
    # Event details
    event_code: str | None = Field(None, alias="EventCode", description="CAMEO event code")
    event_root_code: str | None = Field(None, alias="EventRootCode", description="Root event category")
    quad_class: int | None = Field(None, alias="QuadClass", description="Quad class (1-4)")
    
    # Metrics
    goldstein_scale: float | None = Field(None, alias="GoldsteinScale", description="Conflict/cooperation scale")
    avg_tone: float | None = Field(None, alias="AvgTone", description="News tone sentiment")
    num_articles: int | None = Field(None, alias="NumArticles", description="Number of articles")
    num_mentions: int | None = Field(None, alias="NumMentions", description="Number of mentions")
    num_sources: int | None = Field(None, alias="NumSources", description="Number of sources")
    
    # Location
    location: GeoPoint | None = Field(None, description="Event location")
    location_full_name: str | None = Field(None, alias="ActionGeo_FullName", description="Full location name")
    location_country_code: str | None = Field(None, alias="ActionGeo_CountryCode", description="Location country code")
    
    # Source
    source_url: str | None = Field(None, alias="SOURCEURL", description="Source URL")
    
    model_config = {
        "populate_by_name": True,
        "from_attributes": True,
    }


class EventQuery(BaseModel):
    """Event query parameters."""
    
    # Date range
    start_date: Date | None = Field(None, description="Start date (YYYY-MM-DD)")
    end_date: Date | None = Field(None, description="End date (YYYY-MM-DD)")
    
    # Actors
    actor1_name: str | None = Field(None, description="Primary actor name")
    actor2_name: str | None = Field(None, description="Secondary actor name")
    
    # Location
    country_code: str | None = Field(None, description="Country code")
    lat_min: Decimal | None = Field(None, description="Minimum latitude")
    lat_max: Decimal | None = Field(None, description="Maximum latitude")
    lon_min: Decimal | None = Field(None, description="Minimum longitude")
    lon_max: Decimal | None = Field(None, description="Maximum longitude")
    
    # Event filters
    event_code: str | None = Field(None, description="CAMEO event code")
    event_root_code: str | None = Field(None, description="Root event category")
    quad_class: int | None = Field(None, ge=1, le=4, description="Quad class")
    
    # Sentiment
    min_tone: float | None = Field(None, ge=-100, le=100, description="Minimum tone")
    max_tone: float | None = Field(None, ge=-100, le=100, description="Maximum tone")
    
    # Pagination
    page: int = Field(1, ge=1, description="Page number")
    page_size: int = Field(20, ge=1, le=100, description="Items per page")
    
    # Sorting
    sort_by: str = Field("date", description="Sort field")
    sort_order: str = Field("desc", pattern="^(asc|desc)$", description="Sort order")


class EventNarrative(BaseModel):
    """Generated narrative for events."""
    
    title: str = Field(..., description="Narrative title")
    summary: str = Field(..., description="Narrative summary")
    timeline: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Chronological event timeline"
    )
    key_actors: list[str] = Field(
        default_factory=list,
        description="Key actors in the narrative"
    )
    key_locations: list[str] = Field(
        default_factory=list,
        description="Key locations in the narrative"
    )
    sentiment_analysis: dict[str, Any] | None = Field(
        None,
        description="Sentiment analysis results"
    )
    sources: list[str] = Field(
        default_factory=list,
        description="Source URLs"
    )
    confidence_score: float = Field(
        ..., 
        ge=0.0, 
        le=1.0,
        description="Confidence score of the narrative"
    )
