"""Traffic signal REST API endpoints (async)."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from typing import Optional, List
from datetime import datetime

from app.database.db import get_db
from app.models.sensor import TrafficSignalEvent
from app.schemas.schemas import TrafficSignalEventOut
from app.api.iot import _last_telemetry

router = APIRouter()


@router.get("/traffic/status", summary="Get current traffic signal status")
async def get_traffic_status():
    if _last_telemetry and _last_telemetry.get("traffic_signal"):
        return _last_telemetry["traffic_signal"]
    return {"state": "UNKNOWN", "duration_seconds": None}


@router.get("/traffic/history", response_model=List[TrafficSignalEventOut], summary="Traffic signal history")
async def get_traffic_history(
    signal_state: Optional[str] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    limit: int = Query(100, le=1000),
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(TrafficSignalEvent).order_by(desc(TrafficSignalEvent.timestamp))
    if signal_state:
        stmt = stmt.where(TrafficSignalEvent.signal_state == signal_state.upper())
    if start_time:
        stmt = stmt.where(TrafficSignalEvent.timestamp >= start_time)
    if end_time:
        stmt = stmt.where(TrafficSignalEvent.timestamp <= end_time)
    stmt = stmt.offset(offset).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()
