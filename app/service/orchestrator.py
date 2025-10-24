"""Main orchestrator service for coordinating scraping, matching, and arbitrage detection."""

import asyncio
import os
import time
import csv
import traceback
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from pathlib import Path
from playwright.async_api import async_playwright, Playwright

from app.books.mostbet import MostbetScraper
from app.books.stake import StakeScraper
from app.match.matcher import EventMatcher
from app.engine.arbitrage import ArbitrageEngine
from app.schema.models import (
    RawOddsData, ArbitrageOpportunity, ArbitrageFilters, 
    ArbitrageResponse, ScrapingResult, BookmakerName
)
from app.config import settings
from app.utils.logging import get_logger

logger = get_logger(__name__)

# Global Playwright instance
_playwright_instance: Optional[Playwright] = None


async def get_playwright_instance() -> Playwright:
    """Get or create global Playwright instance."""
    global _playwright_instance
    
    if _playwright_instance is None:
        _playwright_instance = await async_playwright().start()
        logger.info("Global Playwright instance initialized")
    
    return _playwright_instance


async def cleanup_playwright_instance():
    """Clean up global Playwright instance."""
    global _playwright_instance
    
    if _playwright_instance:
        try:
            await _playwright_instance.stop()
            _playwright_instance = None
            logger.info("Global Playwright instance cleaned up")
        except Exception as e:
            logger.error(f"Error cleaning up Playwright: {e}")


class ArbitrageOrchestrator:
    """Main orchestrator for the arbitrage detection system."""
    
    def __init__(self):
        self.scrapers = self._initialize_scrapers()
        self.matcher = EventMatcher()
        self.arbitrage_engine = ArbitrageEngine()
        self.last_scrape_time = None
        self.cached_arbitrages = []
        
    def _initialize_scrapers(self):
        """Initialize all bookmaker scrapers."""
        scrapers = {}
        
        # Initialize available scrapers
        try:
            scrapers[BookmakerName.MOSTBET] = MostbetScraper()
            logger.info("Initialized Mostbet scraper")
        except Exception as e:
            logger.error(f"Failed to initialize Mostbet scraper: {e}")
            logger.error(traceback.format_exc())
        
        try:
            scrapers[BookmakerName.STAKE] = StakeScraper()
            logger.info("Initialized Stake scraper")
        except Exception as e:
            logger.error(f"Failed to initialize Stake scraper: {e}")
            logger.error(traceback.format_exc())
        
        logger.info(f"Initialized {len(scrapers)} scrapers: {list(scrapers.keys())}")
        return scrapers
    
    async def run_full_arbitrage_detection(self, filters: Optional[ArbitrageFilters] = None) -> ArbitrageResponse:
        """Run complete arbitrage detection process."""
        start_time = time.time()
        logger.info("Starting full arbitrage detection process")
        
        try:
            # Ensure Playwright is initialized
            await get_playwright_instance()
            
            # Step 1: Scrape all bookmakers
            scraping_results, all_odds = await self._scrape_all_bookmakers(filters)
            
            if not all_odds:
                logger.warning("No odds data scraped from any bookmaker")
                return ArbitrageResponse(
                    arbitrages=[],
                    scraping_results=scraping_results,
                    summary={"error": "No odds data available"}
                )
            
            # Step 2: Match events across bookmakers
            matched_events = self.matcher.match_events(all_odds)
            
            if not matched_events:
                logger.warning("No events matched across bookmakers")
                return ArbitrageResponse(
                    arbitrages=[],
                    scraping_results=scraping_results,
                    summary={"error": "No matched events found"}
                )
            
            # Step 3: Detect arbitrage opportunities
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
            total_events = sum(r.events_count for r in scraping_results if r.success)
            total_odds = sum(r.odds_count for r in scraping_results if r.success)
            response.add_summary_stats(total_events, total_odds, processing_time)
            
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
                    "processing_time_seconds": round(processing_time, 2)
                }
            )
    
    async def _scrape_all_bookmakers(self, filters: Optional[ArbitrageFilters] = None) -> tuple[List[ScrapingResult], List[RawOddsData]]:
        """Scrape all bookmakers in parallel."""
        scraping_results = []
        all_odds = []
        
        # Filter scrapers based on filters
        active_scrapers = self.scrapers.copy()
        if filters and filters.bookmakers:
            active_scrapers = {k: v for k, v in active_scrapers.items() if k in filters.bookmakers}
        
        if not active_scrapers:
            logger.warning("No active scrapers available")
            return scraping_results, all_odds
        
        logger.info(f"Scraping {len(active_scrapers)} bookmakers: {list(active_scrapers.keys())}")
        
        # Create semaphore to limit concurrent scraping
        semaphore = asyncio.Semaphore(settings.concurrent_scrapers)
        
        async def scrape_bookmaker(bookmaker_name, scraper):
            async with semaphore:
                return await self._scrape_single_bookmaker(bookmaker_name, scraper)
        
        # Run all scrapers concurrently
        scraping_tasks = [
            scrape_bookmaker(bookmaker_name, scraper) 
            for bookmaker_name, scraper in active_scrapers.items()
        ]
        results = await asyncio.gather(*scraping_tasks, return_exceptions=True)
        
        # Process results
        for i, result in enumerate(results):
            scraper_name = list(active_scrapers.keys())[i]
            
            if isinstance(result, Exception):
                logger.error(f"Scraper {scraper_name} failed with exception: {result}")
                logger.error(traceback.format_exc())
                scraping_results.append(ScrapingResult(
                    bookmaker=scraper_name,
                    success=False,
                    error_message=str(result)
                ))
            else:
                scraping_result, odds_data = result
                scraping_results.append(scraping_result)
                if scraping_result.success and odds_data:
                    all_odds.extend(odds_data)
                    logger.info(f"Successfully scraped {scraper_name}: {len(odds_data)} odds")
        
        return scraping_results, all_odds
    
    async def _scrape_single_bookmaker(self, bookmaker_name: BookmakerName, scraper) -> tuple[ScrapingResult, List[RawOddsData]]:
        """Scrape a single bookmaker with proper error handling."""
        start_time = time.time()
        browser = None
        context = None
        
        try:
            # Get global Playwright instance
            playwright = await get_playwright_instance()
            
            # Check headless mode
            headless = os.getenv("HEADLESS", "true").lower() == "true"
            
            # Launch args optimized for Render
            launch_args = [
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-web-security",
                "--disable-features=VizDisplayCompositor",
                "--disable-extensions",
                "--disable-plugins",
                "--disable-images",
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
            ]
            
            # Check if proxy is configured
            proxy_config = None
            proxy_url = os.getenv("PROXY_URL")
            if proxy_url:
                logger.info(f"{bookmaker_name}: Using proxy: {proxy_url}")
                proxy_config = {"server": proxy_url}
            
            # Launch browser (simple launch, not persistent)
            browser = await playwright.chromium.launch(
                headless=headless,
                args=launch_args
            )
            
            logger.info(f"{bookmaker_name}: Browser launched successfully")
            
            # Create context
            context_options = {
                "viewport": {"width": 1366, "height": 768},
                "locale": "en-US",
                "timezone_id": "Asia/Kolkata",
                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "extra_http_headers": {
                    "Accept-Language": "en-US,en;q=0.9",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                },
            }
            
            if proxy_config:
                context_options["proxy"] = proxy_config
            
            context = await browser.new_context(**context_options)
            scraper.context = context
            
            # Create page
            scraper.page = await context.new_page()
            scraper.browser = browser
            
            logger.info(f"{bookmaker_name}: Browser context and page initialized")
            
            # Scrape odds
            logger.info(f"{bookmaker_name}: Starting odds scraping...")
            odds_data = await scraper.scrape_all_odds()
            logger.info(f"{bookmaker_name}: Scraping completed, collected {len(odds_data)} odds")
            
            # Calculate metrics
            duration = time.time() - start_time
            events_count = len(set(odds.event_name for odds in odds_data))
            
            # Cleanup
            try:
                if scraper.page and not scraper.page.is_closed():
                    await scraper.page.close()
                if context:
                    await context.close()
                if browser:
                    await browser.close()
                logger.info(f"{bookmaker_name}: Browser cleanup completed")
            except Exception as cleanup_error:
                logger.warning(f"{bookmaker_name}: Error during cleanup: {cleanup_error}")
            
            return ScrapingResult(
                bookmaker=bookmaker_name,
                success=True,
                odds_count=len(odds_data),
                events_count=events_count,
                scrape_duration=duration
            ), odds_data
                
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"Error scraping {bookmaker_name}: {e}")
            logger.error(traceback.format_exc())
            
            # Cleanup on error
            try:
                if scraper.page and not scraper.page.is_closed():
                    await scraper.page.close()
                if context:
                    await context.close()
                if browser:
                    await browser.close()
            except Exception:
                pass
            
            return ScrapingResult(
                bookmaker=bookmaker_name,
                success=False,
                error_message=str(e),
                scrape_duration=duration
            ), []
    
    async def get_cached_arbitrages(self, filters: Optional[ArbitrageFilters] = None) -> ArbitrageResponse:
        """Get cached arbitrage results with optional filtering."""
        if not self.cached_arbitrages or not self.last_scrape_time:
            logger.info("No cached data available, running fresh detection")
            return await self.run_full_arbitrage_detection(filters)
        
        # Check if cache is too old
        cache_age = datetime.now() - self.last_scrape_time
        max_cache_age_seconds = settings.live_refresh_interval if any(a.event_name for a in self.cached_arbitrages) else settings.prematch_refresh_interval
        
        if cache_age.total_seconds() > max_cache_age_seconds:
            logger.info("Cache is stale, running fresh detection")
            return await self.run_full_arbitrage_detection(filters)
        
        # Apply filters to cached results
        filtered_arbitrages = self._apply_filters_to_cached_results(self.cached_arbitrages, filters)
        
        response = ArbitrageResponse(
            arbitrages=filtered_arbitrages,
            scraping_results=[],
            summary={
                "cached_result": True,
                "cache_age_seconds": int(cache_age.total_seconds()),
                "total_cached_arbitrages": len(self.cached_arbitrages),
                "filtered_arbitrages": len(filtered_arbitrages)
            }
        )
        
        return response
    
    def _apply_filters_to_cached_results(self, arbitrages: List[ArbitrageOpportunity], 
                                        filters: Optional[ArbitrageFilters]) -> List[ArbitrageOpportunity]:
        """Apply filters to cached arbitrage results."""
        if not filters:
            return arbitrages
        
        filtered = []
        
        for arb in arbitrages:
            # Apply sport filter
            if filters.sport and arb.sport != filters.sport.value:
                continue
            
            # Apply market type filter
            if filters.market_type and arb.market_type != filters.market_type.value:
                continue
            
            # Apply minimum arbitrage percentage filter
            if filters.min_arb_percentage and arb.profit_percentage < filters.min_arb_percentage:
                continue
            
            # Apply minimum profit filter
            bankroll = filters.bankroll or settings.default_bankroll
            if filters.min_profit:
                expected_profit = bankroll * (arb.profit_percentage / 100)
                if expected_profit < filters.min_profit:
                    continue
            
            # Apply bookmaker filter
            if filters.bookmakers:
                arb_bookmakers = set(outcome.bookmaker for outcome in arb.outcomes)
                if not any(bm in filters.bookmakers for bm in arb_bookmakers):
                    continue
            
            # Apply live filter
            if filters.live_only is not None:
                is_live = arb.freshness_score > 0.8
                if filters.live_only != is_live:
                    continue
            
            # Apply time filter
            if filters.max_start_hours and arb.start_time:
                max_time = datetime.now() + timedelta(hours=filters.max_start_hours)
                if arb.start_time > max_time:
                    continue
            
            # Recalculate stakes if different bankroll requested
            if filters.bankroll and filters.bankroll != arb.bankroll:
                arb.bankroll = filters.bankroll
                arb.guaranteed_profit = filters.bankroll * (arb.profit_percentage / 100)
                total_inverse = sum(1.0 / outcome.odds for outcome in arb.outcomes)
                for i, outcome in enumerate(arb.outcomes):
                    if i < len(arb.stakes):
                        stake_proportion = (1.0 / outcome.odds) / total_inverse
                        arb.stakes[i].stake_amount = round(filters.bankroll * stake_proportion, 2)
            
            filtered.append(arb)
        
        return filtered
    
    async def _export_arbitrages_to_csv(self, arbitrages: List[ArbitrageOpportunity]) -> None:
        """Export arbitrage opportunities to CSV file."""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"arbitrages_{timestamp}.csv"
            filepath = Path("exports") / filename
            filepath.parent.mkdir(exist_ok=True)
            
            with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
                fieldnames = [
                    'detected_at', 'event_name', 'sport', 'league', 'start_time',
                    'market_type', 'line', 'arb_percentage', 'profit_percentage',
                    'guaranteed_profit', 'bankroll', 'freshness_score',
                    'outcome_1_name', 'outcome_1_odds', 'outcome_1_bookmaker', 'outcome_1_stake',
                    'outcome_2_name', 'outcome_2_odds', 'outcome_2_bookmaker', 'outcome_2_stake',
                    'outcome_3_name', 'outcome_3_odds', 'outcome_3_bookmaker', 'outcome_3_stake'
                ]
                
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                
                for arb in arbitrages:
                    row = {
                        'detected_at': arb.detected_at.isoformat(),
                        'event_name': arb.event_name,
                        'sport': arb.sport,
                        'league': arb.league,
                        'start_time': arb.start_time.isoformat() if arb.start_time else '',
                        'market_type': arb.market_type,
                        'line': arb.line,
                        'arb_percentage': arb.arb_percentage,
                        'profit_percentage': arb.profit_percentage,
                        'guaranteed_profit': arb.guaranteed_profit,
                        'bankroll': arb.bankroll,
                        'freshness_score': arb.freshness_score
                    }
                    
                    # Add outcome details
                    for i, (outcome, stake) in enumerate(zip(arb.outcomes, arb.stakes), 1):
                        if i <= 3:
                            row[f'outcome_{i}_name'] = outcome.name
                            row[f'outcome_{i}_odds'] = outcome.odds
                            row[f'outcome_{i}_bookmaker'] = outcome.bookmaker.value
                            row[f'outcome_{i}_stake'] = stake.stake_amount
                    
                    writer.writerow(row)
            
            logger.info(f"Exported {len(arbitrages)} arbitrages to {filepath}")
            
        except Exception as e:
            logger.error(f"Failed to export arbitrages to CSV: {e}")
            logger.error(traceback.format_exc())
    
    async def _save_raw_odds_data(self, odds_data: List[RawOddsData]) -> None:
        """Save raw odds data for auditing."""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"raw_odds_{timestamp}.csv"
            filepath = Path("exports") / filename
            filepath.parent.mkdir(exist_ok=True)
            
            with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
                fieldnames = [
                    'scraped_at', 'bookmaker', 'event_name', 'sport', 'league',
                    'start_time', 'market_name', 'line', 'outcome_name', 'odds',
                    'url', 'is_live'
                ]
                
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                
                for odds in odds_data:
                    row = {
                        'scraped_at': odds.scraped_at.isoformat(),
                        'bookmaker': odds.bookmaker.value,
                        'event_name': odds.event_name,
                        'sport': odds.sport,
                        'league': odds.league,
                        'start_time': odds.start_time.isoformat() if odds.start_time else '',
                        'market_name': odds.market_name,
                        'line': odds.line,
                        'outcome_name': odds.outcome_name,
                        'odds': odds.odds,
                        'url': odds.url,
                        'is_live': odds.is_live
                    }
                    writer.writerow(row)
            
            logger.info(f"Saved {len(odds_data)} raw odds entries to {filepath}")
            
        except Exception as e:
            logger.error(f"Failed to save raw odds data: {e}")
            logger.error(traceback.format_exc())
    
    async def get_system_status(self) -> Dict:
        """Get system status information."""
        status = {
            "scrapers": {},
            "last_scrape_time": self.last_scrape_time.isoformat() if self.last_scrape_time else None,
            "cached_arbitrages_count": len(self.cached_arbitrages),
            "system_uptime": time.time(),
            "configuration": {
                "fuzzy_threshold": settings.fuzzy_threshold,
                "min_arb_percentage": settings.min_arb_percentage,
                "concurrent_scrapers": settings.concurrent_scrapers,
                "scrape_timeout": settings.scrape_timeout
            }
        }
        
        # Check scraper availability
        for bookmaker, scraper in self.scrapers.items():
            try:
                status["scrapers"][bookmaker.value] = {
                    "available": True,
                    "base_url": scraper.base_url,
                    "last_error": None
                }
            except Exception as e:
                status["scrapers"][bookmaker.value] = {
                    "available": False,
                    "error": str(e)
                }
        
        return status
    
    async def test_bookmaker_connection(self, bookmaker: BookmakerName) -> Dict:
        """Test connection to a specific bookmaker."""
        if bookmaker not in self.scrapers:
            return {
                "bookmaker": bookmaker.value,
                "available": False,
                "error": "Scraper not initialized"
            }
        
        scraper = self.scrapers[bookmaker]
        start_time = time.time()
        browser = None
        context = None
        
        try:
            playwright = await get_playwright_instance()
            
            browser = await playwright.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage"]
            )
            
            context = await browser.new_context()
            page = await context.new_page()
            
            await page.goto(scraper.base_url, timeout=30000)
            
            response_time = time.time() - start_time
            
            await page.close()
            await context.close()
            await browser.close()
            
            return {
                "bookmaker": bookmaker.value,
                "available": True,
                "response_time_seconds": round(response_time, 2),
                "base_url": scraper.base_url
            }
        
        except Exception as e:
            if browser:
                await browser.close()
            return {
                "bookmaker": bookmaker.value,
                "available": False,
                "error": str(e),
                "response_time_seconds": time.time() - start_time
        }
