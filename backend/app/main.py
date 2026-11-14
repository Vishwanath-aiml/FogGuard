"""
FogGuard FastAPI Backend
IoT-based fog-resistant obstacle detection & smart traffic management system.

OPTIMIZATIONS applied:
- Async DB initialization
- Batch write queue started on lifespan
- Simulation callback uses AsyncSession
"""
import logging
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.websocket_manager import manager
from app.database.db import init_db, get_db, AsyncSessionLocal
from app.api import iot, sensors, warnings, traffic, analytics, devices, config_api
from app.services.data_service import init_devices, flush_write_batch

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle."""
    logger.info("FogGuard backend starting up...")

    # Initialize database (async)
    await init_db()
    logger.info("Database initialized")

    # Initialize default device records and load persisted settings
    async with AsyncSessionLocal() as db:
        await init_devices(db)
        from app.services.data_service import load_persistent_settings
        await load_persistent_settings(db)

    # Start the batch write queue (Phase 5)
    from app.services.write_queue import write_queue
    write_queue.set_flush_callback(flush_write_batch)
    await write_queue.start()
    logger.info("Batch write queue started")

    # Auto-start simulation if configured
    if settings.SIMULATION_MODE:
        from app.simulation.engine import simulation_engine
        from app.api.iot import process_telemetry

        async def sim_callback(payload):
            async with AsyncSessionLocal() as session:
                await process_telemetry(payload, session, source="simulation")

        simulation_engine.set_data_callback(sim_callback)
        await simulation_engine.start(scenario="normal", speed=1.0)
        logger.info("Simulation auto-started in SIMULATION_MODE")

    logger.info("FogGuard backend ready on http://0.0.0.0:8000")
    yield

    # Shutdown
    logger.info("Shutting down...")
    from app.simulation.engine import simulation_engine
    await simulation_engine.stop()
    from app.services.write_queue import write_queue
    await write_queue.stop()
    logger.info("FogGuard backend stopped")


app = FastAPI(
    title="FogGuard API",
    description="IoT-based fog-resistant obstacle detection and smart traffic management system.",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list + ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Routes
PREFIX = "/api/v1"
app.include_router(iot.router, prefix=PREFIX, tags=["IoT / Simulation"])
app.include_router(sensors.router, prefix=PREFIX, tags=["Sensors"])
app.include_router(warnings.router, prefix=PREFIX, tags=["Warnings"])
app.include_router(traffic.router, prefix=PREFIX, tags=["Traffic"])
app.include_router(analytics.router, prefix=PREFIX, tags=["Analytics"])
app.include_router(devices.router, prefix=PREFIX, tags=["Devices"])
app.include_router(config_api.router, prefix=PREFIX, tags=["Settings"])


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Real-time WebSocket endpoint for dashboard updates."""
    await manager.connect(websocket)
    try:
        # Send initial state immediately
        from app.api.iot import _last_telemetry
        if _last_telemetry:
            await manager.send_personal_message(_last_telemetry, websocket)
        # Keep connection alive
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
            except asyncio.TimeoutError:
                # Send ping
                await websocket.send_text('{"type":"ping"}')
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.warning(f"WebSocket error: {e}")
        manager.disconnect(websocket)


@app.get("/health", tags=["Health"])
async def health_check():
    from app.simulation.engine import simulation_engine
    from app.services.write_queue import write_queue
    return {
        "status": "healthy",
        "service": "FogGuard Backend",
        "version": "1.0.0",
        "simulation_running": simulation_engine.is_running,
        "websocket_clients": manager.connection_count,
        "write_queue_pending": write_queue.pending,
    }


@app.get("/", tags=["Health"])
async def root():
    return {
        "message": "FogGuard IoT Backend",
        "docs": "/docs",
        "websocket": "ws://localhost:8000/ws",
    }
