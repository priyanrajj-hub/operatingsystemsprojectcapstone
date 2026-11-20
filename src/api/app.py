"""
Main FastAPI application factory, middleware configuration, and WebSocket streaming.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from api.middleware.rate_limit import RateLimitMiddleware
from api.middleware.security_headers import SecurityHeadersMiddleware
from api.routes.experiments import router as experiments_router
from api.routes.hardware import router as hardware_router
from api.routes.health import router as health_router
from api.routes.scheduler import router as scheduler_router
from api.routes.telemetry import router as telemetry_router
from api.websocket.manager import ConnectionManager
from hardware.detection import detect_cpu_topology
from persistence.database import DatabaseManager
from telemetry.collector import TelemetryCollector
from telemetry.schemas import LiveWebSocketMessage

logger = logging.getLogger("aidax.api.app")
ws_manager = ConnectionManager()
db_manager = DatabaseManager()


async def telemetry_broadcast_worker(manager: ConnectionManager, interval: float = 1.0) -> None:
    """Background task streaming hardware telemetry over WebSocket."""
    topology = detect_cpu_topology()
    collector = TelemetryCollector(topology=topology)

    while True:
        try:
            if manager.active_connections:
                health = collector.sample_system_health()
                msg = LiveWebSocketMessage(
                    message_type="TELEMETRY",
                    data=health.model_dump(),
                )
                await manager.broadcast(msg)
        except Exception as e:
            logger.debug("Telemetry broadcast tick error: %s", e)
        await asyncio.sleep(interval)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifecycle context manager."""
    logger.info("Initializing AI-DAX API backend...")
    await db_manager.initialize()

    # Start background WebSocket broadcaster
    broadcaster_task = asyncio.create_task(telemetry_broadcast_worker(ws_manager))
    yield
    logger.info("Shutting down AI-DAX API backend...")
    broadcaster_task.cancel()
    try:
        await broadcaster_task
    except asyncio.CancelledError:
        pass


def create_app() -> FastAPI:
    """Create and configure the production FastAPI application."""
    app = FastAPI(
        title="AI-DAX Lite Telemetry and Scheduling Platform",
        description="Heterogeneous CPU scheduling research framework using Contextual Bandits (LinUCB/LinTS)",
        version="1.0.0",
        lifespan=lifespan,
    )

    # Security & Protection Middlewares
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RateLimitMiddleware, max_requests=300, window_seconds=60.0)

    # CORS configuration restricted to local development origins
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:8000", "http://localhost:8000", "http://127.0.0.1:3000"],
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )

    # Include API Routers
    app.include_router(health_router)
    app.include_router(hardware_router)
    app.include_router(telemetry_router)
    app.include_router(scheduler_router)
    app.include_router(experiments_router)

    # Mount static assets
    static_dir = Path("static")
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory="static"), name="static")

    @app.websocket("/ws/live")
    async def websocket_live_telemetry(websocket: WebSocket) -> None:
        """WebSocket endpoint for real-time telemetry streaming."""
        await ws_manager.connect(websocket)
        try:
            while True:
                # Keep connection alive and receive incoming client commands
                data = await websocket.receive_text()
                if data == "ping":
                    await websocket.send_text("pong")
        except WebSocketDisconnect:
            ws_manager.disconnect(websocket)

    return app


app = create_app()
