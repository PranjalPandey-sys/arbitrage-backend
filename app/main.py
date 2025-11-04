"""
Updated main.py with force-mock support and CLI enhancements.
File: app/main.py (UPDATED)
"""

import asyncio
import uvicorn
import argparse
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from datetime import datetime

from app.api.routes import router
from app.config import settings
from app.utils.logging import get_logger, setup_logging

# Setup logging
setup_logging()
logger = get_logger(__name__)

# Global flag for force mock mode
FORCE_MOCK = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    logger.info("Starting arbitrage detection backend...")
    try:
        logger.info("System startup completed successfully")
        yield
    except Exception as e:
        logger.error(f"Startup failed: {e}")
        raise
    finally:
        logger.info("Shutting down arbitrage detection backend...")


def create_app(force_mock: bool = False) -> FastAPI:
    """Create FastAPI application with optional force mock mode."""
    global FORCE_MOCK
    FORCE_MOCK = force_mock
    
    app = FastAPI(
        title="Arbitrage Detection API",
        version="1.0.0",
        description="Sports arbitrage detection with mock and live data modes",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["*"],
    )

    app.add_middleware(GZipMiddleware, minimum_size=1000)

    # Pass force_mock to router
    app.state.force_mock = force_mock
    app.include_router(router, tags=["arbitrage"])

    @app.get("/")
    async def root():
        """Root endpoint."""
        from app.service.orchestrator import ArbitrageOrchestrator
        
        # Get connector status
        orchestrator = ArbitrageOrchestrator(force_mock=force_mock)
        connector_status = orchestrator.connector_manager.get_connector_status()
        
        return {
            "service": "Arbitrage Detection API",
            "version": "1.0.0",
            "status": "operational",
            "mode": connector_status["system_mode"],
            "force_mock": force_mock,
            "timestamp": datetime.now().isoformat(),
            "endpoints": {
                "health": "/health",
                "docs": "/docs",
                "arbitrages": "/api/arbs",
                "status": "/api/status",
                "connector_status": "/api/connectors/status"
            },
            "connector_summary": {
                "total": connector_status["total_connectors"],
                "live": connector_status["live_count"],
                "mock": connector_status["mock_count"]
            }
        }

    @app.exception_handler(Exception)
    async def global_exception_handler(request, exc):
        """Global exception handler."""
        logger.error(f"Unhandled exception on {request.url}: {exc}")
        import traceback
        logger.error(traceback.format_exc())
        return JSONResponse(
            status_code=500,
            content={
                "detail": "Internal server error",
                "timestamp": datetime.now().isoformat(),
                "path": str(request.url)
            }
        )

    @app.middleware("http")
    async def logging_middleware(request, call_next):
        """Request logging middleware."""
        start_time = datetime.now()
        response = await call_next(request)
        process_time = (datetime.now() - start_time).total_seconds()
        logger.info(
            f"{request.method} {request.url.path} - "
            f"Status: {response.status_code} - "
            f"Time: {process_time:.3f}s"
        )
        return response
    
    return app


def main():
    """Main entry point with CLI argument parsing."""
    parser = argparse.ArgumentParser(
        description="Arbitrage Detection Backend - Mock & Live Modes",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run in automatic mode (mock if no keys, live if keys present)
  python -m app.main
  
  # Force mock mode even if API keys exist
  python -m app.main --force-mock
  
  # Specify custom host and port
  python -m app.main --host 0.0.0.0 --port 8080
  
  # Development mode with auto-reload
  python -m app.main --reload
        """
    )
    
    parser.add_argument(
        '--force-mock',
        action='store_true',
        help='Force mock mode even if API keys are present'
    )
    
    parser.add_argument(
        '--host',
        default=settings.host,
        help=f'Host to bind (default: {settings.host})'
    )
    
    parser.add_argument(
        '--port',
        type=int,
        default=settings.port,
        help=f'Port to bind (default: {settings.port})'
    )
    
    parser.add_argument(
        '--reload',
        action='store_true',
        help='Enable auto-reload (development mode)'
    )
    
    parser.add_argument(
        '--workers',
        type=int,
        default=1,
        help='Number of worker processes (default: 1)'
    )
    
    args = parser.parse_args()
    
    # Log startup configuration
    logger.info("=" * 60)
    logger.info("ARBITRAGE DETECTION BACKEND - STARTING")
    logger.info("=" * 60)
    logger.info(f"Host: {args.host}")
    logger.info(f"Port: {args.port}")
    logger.info(f"Force Mock: {args.force_mock}")
    logger.info(f"Reload: {args.reload}")
    logger.info(f"Workers: {args.workers}")
    logger.info("=" * 60)
    
    # Create app with force_mock setting
    app = create_app(force_mock=args.force_mock)
    
    # Run server
    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        reload=args.reload,
        workers=args.workers if not args.reload else 1,
        log_level=settings.log_level.lower(),
        access_log=True
    )


if __name__ == "__main__":
    main()
