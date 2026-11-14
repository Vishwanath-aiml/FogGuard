"""IoT Telemetry endpoint — receives data from ESP32, direct USB serial, or simulation.
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone
import copy
import logging

from app.database.db import get_db, AsyncSessionLocal
from app.schemas.schemas import TelemetryPayload, SimulationControl
from app.services import data_service
from app.services.data_service import precompute_classifications
from app.services.warning_engine import warning_engine
from app.services.write_queue import write_queue
from app.simulation.engine import simulation_engine, SCENARIOS
from app.hardware.source import hardware_source
from app.core.websocket_manager import manager
from app.core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()

# Shared mutable state for last telemetry
_last_telemetry: dict = {}


def get_last_telemetry() -> dict:
    """Safe accessor for the most recently broadcast telemetry packet."""
    global _last_telemetry
    return copy.deepcopy(_last_telemetry) if _last_telemetry else {}


async def process_telemetry(
    payload: TelemetryPayload, db: AsyncSession, source: str = "hardware"
):
    """
    Core telemetry processing pipeline:
    1. Precompute distance classifications (once per sensor).
    2. Evaluate obstacle warning conditions (once per sensor).
    3. Persist new WarningEvents directly to SQLite to generate real database IDs.
    4. Broadcast state immediately over WebSocket with genuine database IDs.
    5. Persist raw sensor readings, obstacle events, traffic changes, and device status.
    """
    global _last_telemetry

    now = payload.timestamp or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    # 1. Precompute classifications once
    levels = precompute_classifications(payload)

    # 2. Build sensor list for broadcast
    sensor_list = []
    for s, (level, _zone) in zip(payload.sensors, levels):
        sensor_list.append({
            "sensor_id": s.sensor_id,
            "zone": s.zone,
            "distance_cm": s.distance_cm,
            "obstacle_detected": s.obstacle_detected,
            "warning_level": level,
        })

    # 3. Warning evaluation — exactly once per reading
    thresholds = {
        "critical_cm": settings.CRITICAL_THRESHOLD_CM,
        "warning_cm": settings.WARNING_THRESHOLD_CM,
        "caution_cm": settings.CAUTION_THRESHOLD_CM,
        "max_range_cm": settings.MAX_RANGE_CM,
    }
    raw_warnings = []
    for s in payload.sensors:
        w = warning_engine.process_sensor(
            s.sensor_id, s.zone, s.distance_cm,
            thresholds=thresholds, now=now,
        )
        if w:
            raw_warnings.append(w)

    # Persist warning events to SQLite immediately to get true autoincrement primary keys
    persisted_warnings = []
    if raw_warnings:
        persisted_warnings = await data_service.save_warning_events(db, raw_warnings)
        await db.commit()  # Ensure warnings exist in DB so frontend can immediately acknowledge

    warnings_out = [
        {
            "id": w.id,
            "sensor_id": w.sensor_id,
            "zone": w.zone,
            "distance_cm": w.distance_cm,
            "warning_level": w.warning_level,
            "warning_message": w.warning_message,
            "acknowledged": w.acknowledged,
            "timestamp": w.timestamp.isoformat() if hasattr(w.timestamp, "isoformat") else str(w.timestamp),
        }
        for w in persisted_warnings
    ]

    traffic_out = None
    if payload.traffic_signal:
        traffic_out = {
            "state": payload.traffic_signal.state.value,
            "duration_seconds": payload.traffic_signal.duration_seconds,
        }

    is_sim = (source == "simulation")
    broadcast_msg = {
        "type": "telemetry",
        "source": source,
        "timestamp": now.isoformat(),
        "sensors": sensor_list,
        "traffic_signal": traffic_out,
        "new_warnings": warnings_out,
        "simulation_mode": is_sim,
    }

    _last_telemetry = broadcast_msg

    # 4. Immediate WebSocket broadcast (sub-millisecond)
    await manager.broadcast(broadcast_msg)

    # 5. Persist high-frequency raw sensor data, traffic signal, and device status
    if write_queue.is_running:
        write_queue.enqueue({"payload": payload, "levels": levels})
    else:
        # Fallback inline persistence
        await data_service.save_sensor_readings(db, payload, levels)
        await data_service.save_traffic_event(db, payload)
        await data_service.update_device_status(db, payload.device_id)
        await db.commit()


@router.post("/iot/telemetry", summary="Receive telemetry from ESP32 or hardware")
async def receive_telemetry(
    payload: TelemetryPayload,
    db: AsyncSession = Depends(get_db),
):
    """
    Main endpoint for receiving sensor telemetry from physical hardware (ESP32 / Wi-Fi).
    """
    hardware_source.receive(payload)

    # If simulation was running, stop it so physical hardware takes over exclusively
    if simulation_engine.is_running:
        await simulation_engine.stop()
        logger.info("Paused simulation engine: live hardware telemetry received on /iot/telemetry")

    await process_telemetry(payload, db, source="hardware")
    return {"status": "ok", "processed_sensors": len(payload.sensors)}


@router.post("/simulation/control", summary="Control simulation mode")
async def control_simulation(
    control: SimulationControl,
    db: AsyncSession = Depends(get_db),
):
    """Start, stop, or reset the built-in simulation engine."""
    action = control.action.lower()

    if action == "start":
        scenario = control.scenario or "normal"
        if scenario not in SCENARIOS:
            raise HTTPException(400, f"Unknown scenario. Valid: {list(SCENARIOS.keys())}")
        speed = control.speed_multiplier or 1.0

        async def sim_callback(payload: TelemetryPayload):
            async with AsyncSessionLocal() as session:
                await process_telemetry(payload, session, source="simulation")

        simulation_engine.set_data_callback(sim_callback)
        await simulation_engine.start(scenario=scenario, speed=speed)
        return {"status": "simulation_started", "scenario": scenario, "speed": speed}

    elif action == "stop":
        await simulation_engine.stop()
        return {"status": "simulation_stopped"}

    elif action == "reset":
        simulation_engine.reset()
        return {"status": "simulation_reset"}

    else:
        raise HTTPException(400, f"Unknown action '{action}'. Use: start, stop, reset")


@router.get("/simulation/status", summary="Get simulation status")
async def simulation_status():
    return {
        "running": simulation_engine.is_running,
        "scenario": simulation_engine.scenario_name,
        "scenarios": list(SCENARIOS.keys()),
    }


@router.get("/simulation/scenarios", summary="List available scenarios")
async def list_scenarios():
    return {
        "scenarios": [
            {"id": "normal", "name": "Normal / Clear Road"},
            {"id": "single_obstacle", "name": "Single Obstacle Ahead"},
            {"id": "multiple_obstacles", "name": "Multiple Obstacles"},
            {"id": "critical_front", "name": "Critical Front Obstacle"},
            {"id": "side_obstacle", "name": "Side Obstacle"},
            {"id": "dynamic_approaching", "name": "Dynamic Approaching Obstacle"},
            {"id": "dense_fog", "name": "Dense Fog Demonstration"},
        ]
    }
