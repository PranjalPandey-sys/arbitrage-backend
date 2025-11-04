"""
Updated orchestrator to use the new connector manager.
File: app/service/orchestrator.py (UPDATED SECTION)

Add these imports at the top:
"""
from app.connectors.connector_manager import ConnectorManager

"""
Then modify the ArbitrageOrchestrator class:
"""

class ArbitrageOrchestrator:
    """Main orchestrator for the arbitrage detection system."""
    
    def __init__(self, force_mock: bool = False):
        # Initialize connector manager instead of individual scrapers
        self.connector_manager = ConnectorManager(force_mock=force_mock)
        self.matcher = EventMatcher()
        self.arbitrage_engine = ArbitrageEngine()
        self.last_scrape_time = None
        self.cached_arbitrages = []
        
        logger.info("Orchestrator initialized with connector manager")
    
    async def run_full_arbitrage_detection(self, filters: Optional[ArbitrageFilters] = None) -> ArbitrageResponse:
        """Run complete arbitrage detection process."""
        start_time = time.time()
        logger.info("Starting full arbitrage detection process")
        
        try:
            # Step 1: Fetch odds from all connectors (mock or live)
            logger.info("Fetching odds from all connectors...")
            all_odds = await self.connector_manager.fetch_all_odds()
            
            if not all_odds:
                logger.warning("No odds data fetched from any connector")
                return ArbitrageResponse(
                    arbitrages=[],
                    scraping_results=[],
                    summary={
                        "error": "No odds data available",
                        "connector_status": self.connector_manager.get_connector_status()
                    }
                )
            
            logger.info(f"Fetched {len(all_odds)} total odds entries")
            
            # Create scraping results for API response
            scraping_results = self._create_scraping_results(all_odds)
            
            # Step 2: Match events across bookmakers
            logger.info("Matching events across bookmakers...")
            matched_events = self.matcher.match_events(all_odds)
            
            if not matched_events:
                logger.warning("No events matched across bookmakers")
                return ArbitrageResponse(
                    arbitrages=[],
                    scraping_results=scraping_results,
                    summary={
                        "error": "No matched events found",
                        "connector_status": self.connector_manager.get_connector_status()
                    }
                )
            
            logger.info(f"Matched {len(matched_events)} events")
            
            # Step 3: Detect arbitrage opportunities
            logger.info("Detecting arbitrage opportunities...")
            arbitrages = self.arbitrage_engine.detect_arbitrages(matched_events, filters)
            
            # Step 4: Cache results and export data
            self.cached_arbitrages = arbitrages
            self.last_scrape_time = datetime.now()
            
            if settings.export_csv and arbitrages:
                await self._export_arbitrages_to_csv(arbitrages)
            
            if settings.save_raw_data:
                await self._save_raw_odds_data(all_odds)
            
            # Step 5: Create response
            processing_time = time.time() - start_time
            response = ArbitrageResponse(
                arbitrages=arbitrages,
                scraping_results=scraping_results
            )
            
            # Add summary statistics
            total_events = len(set(odds.event_name for odds in all_odds))
            total_odds = len(all_odds)
            response.add_summary_stats(total_events, total_odds, processing_time)
            
            # Add connector status to summary
            response.summary['connector_status'] = self.connector_manager.get_connector_status()
            
            logger.info(f"Arbitrage detection completed in {processing_time:.2f}s - "
                       f"Found {len(arbitrages)} arbitrages from {total_events} events")
            
            return response
            
        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(f"Error in arbitrage detection process: {e}")
            logger.error(traceback.format_exc())
            
            return ArbitrageResponse(
                arbitrages=[],
                scraping_results=[],
                summary={
                    "error": str(e),
                    "processing_time_seconds": round(processing_time, 2),
                    "connector_status": self.connector_manager.get_connector_status()
                }
            )
    
    def _create_scraping_results(self, all_odds: List[RawOddsData]) -> List[ScrapingResult]:
        """Create scraping results from odds data."""
        # Group odds by bookmaker
        bookmaker_odds = {}
        for odds in all_odds:
            if odds.bookmaker not in bookmaker_odds:
                bookmaker_odds[odds.bookmaker] = []
            bookmaker_odds[odds.bookmaker].append(odds)
        
        scraping_results = []
        for bookmaker, odds_list in bookmaker_odds.items():
            events_count = len(set(odds.event_name for odds in odds_list))
            
            # Check if this is mock or live
            mode = self.connector_manager.config.connector_modes.get(bookmaker, "unknown")
            
            scraping_results.append(ScrapingResult(
                bookmaker=bookmaker,
                success=True,
                odds_count=len(odds_list),
                events_count=events_count,
                error_message=None,
                scrape_duration=0.1,  # Mock duration
                scraped_at=datetime.now()
            ))
        
        return scraping_results
    
    async def get_system_status(self) -> Dict:
        """Get system status information including connector status."""
        connector_status = self.connector_manager.get_connector_status()
        
        status = {
            "service": "Arbitrage Detection API",
            "mode": connector_status["system_mode"],
            "connectors": connector_status,
            "last_scrape_time": self.last_scrape_time.isoformat() if self.last_scrape_time else None,
            "cached_arbitrages_count": len(self.cached_arbitrages),
            "configuration": {
                "fuzzy_threshold": settings.fuzzy_threshold,
                "min_arb_percentage": settings.min_arb_percentage,
                "scrape_timeout": settings.scrape_timeout
            }
        }
        
        return status


# Remove the old _scrape_all_bookmakers and _scrape_single_bookmaker methods
# They are replaced by the connector manager's fetch_all_odds method
