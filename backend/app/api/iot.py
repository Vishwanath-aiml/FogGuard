"""IoT Telemetry endpoint — receives data from ESP32 or simulation.

OPTIMIZATIONS applied:
- Phase 2: Single commit at end of process_telemetry (was 4 separate commits)
- Phase 4: classify_distance called once per sensor, reused for DB + broadcast
- Phase 5: DB writes are enqueued to the batch writer; broadcast is immediate
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone

from app.database.db import get_db, AsyncSessionLocal
from app.schemas.schemas import TelemetryPayload, SimulationControl
from app.services import data_service
from app.services.data_service import precompute_classifications
from app.services.write_queue import write_queue
from app.simulation.engine import simulation_engine, SCENARIOS
from app.hardware.source import hardware_source
from app.core.websocket_manager import manager
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

# Shared mutable state for last telemetry
_last_telemetry: dict = {}
_warning_id_seq: int = 1000


async def process_telemetry(
    payload: TelemetryPayload, db: AsyncSession, source: str = "hardware"
):
    """
    Core telemetry processing — classify, broadcast, persist.

    OPTIMIZATION: The hot path (classify + broadcast) runs first with zero
    disk I/O.  DB persistence is either done in-line with a single commit
    or offloaded to the batch write queue.
    """
    global _last_telemetry

    now = datetime.now(timezone.utc)

    # ── Phase 4: classify ONCE, reuse everywhere ──
    levels = precompute_classifications(payload)

    # ── Build WS broadcast message (zero I/O) ──
    sensor_list = []
    for s, (level, _zone) in zip(payload.sensors, levels):
        sensor_list.append({
            "sensor_id": s.sensor_id,
            "zone": s.zone,
            "distance_cm": s.distance_cm,
            "obstacle_detected": s.obstacle_detected,
            "warning_level": level,            # reused — no second classify call
        })

    # Warnings (in-memory only — warning_engine is pure Python)
    thresholds = {
        "critical_cm": settings.CRITICAL_THRESHOLD_CM,
        "warning_cm": settings.WARNING_THRESHOLD_CM,
        "caution_cm": settings.CAUTION_THRESHOLD_CM,
        "max_range_cm": settings.MAX_RANGE_CM,
    }
    warnings_out = []
    for s in payload.sensors:
        w = data_service.warning_engine.process_sensor(
            s.sensor_id, s.zone, s.distance_cm,
            thresholds=thresholds, now=now,
        )
        if w:
            _warning_id_seq += 1
            warnings_out.append({
                "id": _warning_id_seq,  # Deterministic unique ID for WebSocket/React keys
                "sensor_id": w["sensor_id"],
                "zone": w["zone"],
                "distance_cm": w["distance_cm"],
                "warning_level": w["warning_level"],
                "warning_message": w["warning_message"],
                "acknowledged": False,
                "timestamp": now.isoformat(),
            })

    traffic_out = None
    if payload.traffic_signal:
        traffic_out = {
            "state": payload.traffic_signal.state.value,
            "duration_seconds": payload.traffic_signal.duration_seconds,
        }

    broadcast_msg = {
        "type": "telemetry",
        "source": source,
        "timestamp": (payload.timestamp or now).isoformat(),
        "sensors": sensor_list,
        "traffic_signal": traffic_out,
        "new_warnings": warnings_out,
        "simulation_mode": settings.SIMULATION_MODE or source == "simulation",
    }

    _last_telemetry = broadcast_msg

    # ── Broadcast IMMEDIATELY (no disk I/O yet) ──
    await manager.broadcast(broadcast_msg)

    # ── Phase 5: Enqueue DB writes to the batch writer ──
    # The write queue flushes periodically in the background.
    # For endpoints that need synchronous DB confirmation, we fall through
    # to the in-line path below.
    if write_queue._running:
        write_queue.enqueue(payload)
    else:
        # Fallback: write in-line with a single commit (Phase 2)
        await data_service.save_sensor_readings(db, payload, levels)
        await data_service.save_warnings(db, payload, now)
        await data_service.save_traffic_event(db, payload)
        await data_service.update_device_status(db, payload.device_id)
        await db.commit()  # ← ONE commit instead of four


@router.post("/iot/telemetry", summary="Receive telemetry from ESP32 or simulation")
async def receive_telemetry(
    payload: TelemetryPayload,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Main endpoint for receiving sensor telemetry.
    ESP32 sends data here via Wi-Fi.
    Payload is validated, saved, and broadcast to all WebSocket clients.
    """
    hardware_source.receive(payload)
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
