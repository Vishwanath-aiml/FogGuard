"""Device status endpoints (async)."""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from datetime import datetime, timezone

from app.database.db import get_db
from app.models.sensor import DeviceStatus
from app.schemas.schemas import DeviceStatusOut
from app.hardware.source import hardware_source
from app.simulation.engine import simulation_engine
from app.core.config import settings

router = APIRouter()


@router.get("/devices/status", summary="Get all device statuses")
async def get_device_statuses(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(DeviceStatus))
    devices = result.scalars().all()

    # Determine real-time connection status
    out = []
    for d in devices:
        status = d.connection_status
        last_seen = d.last_seen

        # Override with real-time info
        if d.device_name == "fogguard-esp32":
            if simulation_engine.is_running:
                status = "SIMULATED"
                last_seen = datetime.now(timezone.utc)
            elif hardware_source.is_connected:
                status = "CONNECTED"
                last_seen = hardware_source.last_received
            else:
                status = "DISCONNECTED"

        if d.device_name == "fogguard-arduino":
            if simulation_engine.is_running:
                status = "SIMULATED"
            elif hardware_source.is_connected:
                status = "CONNECTED"

        if d.device_name.startswith("fogguard-sensor-"):
            if simulation_engine.is_running:
                status = "SIMULATED"
                last_seen = datetime.now(timezone.utc)
            elif hardware_source.is_connected:
                status = "CONNECTED"
                last_seen = hardware_source.last_received

        out.append({
            "id": d.id,
            "device_name": d.device_name,
            "device_type": d.device_type,
            "connection_status": status,
            "last_seen": last_seen.isoformat() if last_seen else None,
            "timestamp": d.timestamp.isoformat() if d.timestamp else None,
        })

    return out


@router.get("/devices/system-info", summary="Get system-level info")
async def get_system_info():
    from app.services.write_queue import write_queue
    return {
        "mode": "SIMULATION" if (simulation_engine.is_running or settings.SIMULATION_MODE) else "HARDWARE",
        "simulation_running": simulation_engine.is_running,
        "simulation_scenario": simulation_engine.scenario_name,
        "hardware_connected": hardware_source.is_connected,
        "hardware_last_seen": hardware_source.last_received.isoformat() if hardware_source.last_received else None,
        "websocket_clients": 0,  # Updated from manager if needed
        "write_queue_pending": write_queue.pending,
        "thresholds": {
            "critical_cm": settings.CRITICAL_THRESHOLD_CM,
            "warning_cm": settings.WARNING_THRESHOLD_CM,
            "caution_cm": settings.CAUTION_THRESHOLD_CM,
            "max_range_cm": settings.MAX_RANGE_CM,
        }
    }
