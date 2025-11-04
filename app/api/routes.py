"""
Updated API routes with connector status endpoint.
File: app/api/routes.py (ADD THESE NEW ENDPOINTS)
"""

from fastapi import APIRouter, Request

# Add this new endpoint to the existing router

@router.get("/api/connectors/status")
async def get_connector_status(request: Request):
    """
    Get detailed status of all connectors (mock vs live).
    """
    try:
        force_mock = getattr(request.app.state, 'force_mock', False)
        orchestrator = ArbitrageOrchestrator(force_mock=force_mock)
        
        connector_status = orchestrator.connector_manager.get_connector_status()
        
        return {
            "system_mode": connector_status["system_mode"],
            "force_mock_enabled": force_mock,
            "connectors": connector_status["connectors"],
            "summary": {
                "total_connectors": connector_status["total_connectors"],
                "live_connectors": connector_status["live_count"],
                "mock_connectors": connector_status["mock_count"]
            },
            "instructions": {
                "enable_live_mode": "Add API keys to config/credentials.yaml or set environment variables",
                "force_mock_mode": "Start server with --force-mock flag",
                "environment_variables": [
                    "BOOKIE_1XBET_KEY",
                    "BOOKIE_PARIMATCH_KEY",
                    "BOOKIE_MOSTBET_KEY",
                    "BOOKIE_STAKE_KEY",
                    "BOOKIE_LEON_KEY",
                    "BOOKIE_1WIN_KEY"
                ]
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting connector status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/connectors/refresh")
async def refresh_connectors(request: Request):
    """
    Refresh connector configuration (reload credentials).
    """
    try:
        force_mock = getattr(request.app.state, 'force_mock', False)
        
        # Create new orchestrator to reload config
        orchestrator = ArbitrageOrchestrator(force_mock=force_mock)
        
        connector_status = orchestrator.connector_manager.get_connector_status()
        
        return {
            "message": "Connector configuration refreshed",
            "system_mode": connector_status["system_mode"],
            "connectors": connector_status["connectors"],
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error refreshing connectors: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/connectors/{bookmaker}/test")
async def test_connector(bookmaker: BookmakerName, request: Request):
    """
    Test a specific connector and show sample data.
    """
    try:
        force_mock = getattr(request.app.state, 'force_mock', False)
        orchestrator = ArbitrageOrchestrator(force_mock=force_mock)
        
        # Get connector mode
        mode = orchestrator.connector_manager.config.connector_modes.get(bookmaker)
        
        if bookmaker in orchestrator.connector_manager.mock_connectors:
            # Get sample mock data
            connector = orchestrator.connector_manager.mock_connectors[bookmaker]
            sample_odds = connector.generate_all_odds()[:5]  # First 5 odds
            
            return {
                "bookmaker": bookmaker.value,
                "mode": mode.value if mode else "unknown",
                "status": "active",
                "sample_data": [
                    {
                        "event": odds.event_name,
                        "sport": odds.sport,
                        "market": odds.market_name,
                        "outcome": odds.outcome_name,
                        "odds": odds.odds,
                        "is_mock": True
                    }
                    for odds in sample_odds
                ],
                "message": "Mock connector is generating synthetic odds"
            }
        else:
            return {
                "bookmaker": bookmaker.value,
                "mode": "live" if mode == "live" else "unknown",
                "status": "not_configured",
                "message": "Live connector not available. Add API credentials to enable."
            }
        
    except Exception as e:
        logger.error(f"Error testing connector {bookmaker}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Update the existing /api/status endpoint to include connector info
@router.get("/api/status")
async def get_system_status(request: Request):
    """
    Get comprehensive system status including connector information.
    """
    try:
        force_mock = getattr(request.app.state, 'force_mock', False)
        orchestrator = ArbitrageOrchestrator(force_mock=force_mock)
        
        status = await orchestrator.get_system_status()
        
        # Add additional info
        status["force_mock_enabled"] = force_mock
        status["api_version"] = "1.0.0"
        
        return status
        
    except Exception as e:
        logger.error(f"Error getting system status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Modify the existing get_arbitrages endpoint to pass force_mock
@router.get("/api/arbs", response_model=ArbitrageResponse)
async def get_arbitrages(
    request: Request,
    sport: Optional[SportType] = Query(None, description="Filter by sport type"),
    market_type: Optional[MarketType] = Query(None, description="Filter by market type"),
    min_arb_percentage: Optional[float] = Query(None, ge=0, description="Minimum arbitrage profit percentage"),
    min_profit: Optional[float] = Query(None, ge=0, description="Minimum profit amount"),
    bookmakers: Optional[List[BookmakerName]] = Query(None, description="Filter by bookmakers"),
    live_only: Optional[bool] = Query(None, description="Only live events"),
    max_start_hours: Optional[int] = Query(None, ge=0, le=168, description="Maximum hours until event start"),
    bankroll: Optional[float] = Query(None, gt=0, description="Bankroll for stake calculations"),
    use_cache: bool = Query(True, description="Use cached results if available"),
    background_tasks: BackgroundTasks = None
):
    """
    Get arbitrage opportunities (mock or live data based on configuration).
    """
    try:
        # Get force_mock from app state
        force_mock = getattr(request.app.state, 'force_mock', False)
        
        # Create orchestrator with force_mock setting
        orchestrator = ArbitrageOrchestrator(force_mock=force_mock)
        
        # Create filters object
        filters = ArbitrageFilters(
            sport=sport,
            market_type=market_type,
            min_arb_percentage=min_arb_percentage,
            min_profit=min_profit,
            bookmakers=bookmakers,
            live_only=live_only,
            max_start_hours=max_start_hours,
            bankroll=bankroll
        )
        
        # Get arbitrages (cached or fresh)
        if use_cache:
            response = await orchestrator.get_cached_arbitrages(filters)
        else:
            response = await orchestrator.run_full_arbitrage_detection(filters)
        
        logger.info(f"Returned {len(response.arbitrages)} arbitrages")
        return response
        
    except Exception as e:
        logger.error(f"Error in get_arbitrages: {e}")
        raise HTTPException(status_code=500, detail=str(e))
