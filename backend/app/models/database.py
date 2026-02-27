"""SQLAlchemy database models for persistent storage."""

from sqlalchemy import Column, String, Float, DateTime, Boolean, JSON, Enum, func
from sqlalchemy.orm import DeclarativeBase
from geoalchemy2 import Geometry
import enum


class Base(DeclarativeBase):
    pass


class EventTypeDB(str, enum.Enum):
    weather = "weather"
    fire = "fire"
    emergency = "emergency"
    traffic = "traffic"
    event = "event"


class SeverityDB(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class GeoEventDB(Base):
    __tablename__ = "geo_events"

    id = Column(String, primary_key=True)
    type = Column(String, nullable=False, index=True)
    category = Column(String, nullable=False)
    title = Column(String, nullable=False)
    description = Column(String, nullable=True)
    location = Column(Geometry("POINT", srid=4326), nullable=False)
    radius_km = Column(Float, nullable=True)
    severity = Column(String, nullable=False, default="low")
    source = Column(String, nullable=False, index=True)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=True)
    last_updated = Column(DateTime, server_default=func.now(), onupdate=func.now())
    metadata_ = Column("metadata", JSON, default={})
    active = Column(Boolean, default=True, index=True)


class HazardAlertDB(Base):
    __tablename__ = "hazard_alerts"

    id = Column(String, primary_key=True)
    level = Column(String, nullable=False)
    title = Column(String, nullable=False)
    description = Column(String, nullable=False)
    location = Column(Geometry("POINT", srid=4326), nullable=False)
    radius_km = Column(Float, nullable=False)
    contributing_events = Column(JSON, default=[])
    recommended_action = Column(String, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    expires_at = Column(DateTime, nullable=True)
    metadata_ = Column("metadata", JSON, default={})
