"""Production-ready arbitrage detection and calculation engine with Playwright web scraping."""

import asyncio
import json
import math
import os
import tempfile
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple, Any
from decimal import Decimal, ROUND_HALF_UP

from playwright.async_api import async_playwright, Browser, BrowserContext, Page, TimeoutError as PlaywrightTimeoutError
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from app.schema.models import (
    MatchedEvent, ArbitrageOpportunity, OutcomeData, 
    StakeCalculation, ArbitrageFilters
)
from app.config import settings
from app.utils.logging import get_logger

logger = get_logger(__name__)

# FastAPI app for health check endpoint
app = FastAPI(title="Arbitrage Detection API")

# Global browser instance
_browser: Optional[Browser] = None
_context: Optional[BrowserContext] = None

@app.get("/health")
async def health_check():
    """Lightweight health check endpoint."""
    return JSONResponse(
        content={
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "service": "arbitrage-detection"
        },
        status_code=200
    )

async def init_browser() -> Tuple[Browser, BrowserContext]:
    """Initialize production-safe Playwright browser."""
    global _browser, _context
    
    if _browser and _context:
        return _browser, _context
    
    try:
        playwright = await async_playwright().start()
        
        # Production-safe Chromium launch arguments
        launch_args = [
            "--no-sandbox",
            "--disable-dev-shm-usage", 
            "--disable-gpu",
            "--disable-web-security",
            "--disable-features=VizDisplayCompositor",
            "--disable-extensions",
            "--disable-plugins",
            "--disable-images",  # Faster loading
            "--disable-javascript-harmony-shipping",
            "--disable-background-timer-throttling",
            "--disable-renderer-backgrounding",
            "--disable-backgrounding-occluded-windows",
            "--disable-ipc-flooding-protection",
            "--user-data-dir=/tmp/chrome-user-data",
        ]
        
        # Optional: disable site isolation for better performance
        if os.getenv("DISABLE_SITE_ISOLATION", "false").lower() == "true":
            launch_args.append("--disable-features=site-per-process")
        
        # Check if proxy is configured
        proxy_url = os.getenv("PROXY_URL")
        proxy_config = None
        if proxy_url:
            logger.info(f"Using proxy: {proxy_url}")
            proxy_config = {"server": proxy_url}
        
        _browser = await playwright.chromium.launch(
            headless=True,
            args=launch_args,
            timeout=60000
        )
        
        # Create browser context with production settings
        context_options = {
            "viewport": {"width": 1366, "height": 768},
            "locale": "en-US",
            "timezone_id": "Asia/Kolkata",
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "extra_http_headers": {
                "Accept-Language": "en-US,en;q=0.9",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
                "Accept-Encoding": "gzip, deflate, br",
                "Cache-Control": "no-cache",
                "Pragma": "no-cache",
                "Sec-Ch-Ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
                "Sec-Ch-Ua-Mobile": "?0",
                "Sec-Ch-Ua-Platform": '"Windows"',
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-User": "?1",
                "Upgrade-Insecure-Requests": "1"
            }
        }
        
        if proxy_config:
            context_options["proxy"] = proxy_config
        
        _context = await _browser.new_context(**context_options)
        
        # Enable request/response logging
        async def log_request(request):
            logger.debug(f"Request: {request.method} {request.url}")
        
        async def log_response(response):
            if response.status >= 400:
                logger.warning(f"Response: {response.status} {response.url}")
            else:
                logger.debug(f"Response: {response.status} {response.url}")
        
        _context.on("request", log_request)
        _context.on("response", log_response)
        
        logger.info("Browser initialized successfully")
        return _browser, _context
        
    except Exception as e:
        logger.error(f"Failed to initialize browser: {e}")
        raise


async def cleanup_browser():
    """Clean up browser resources."""
    global _browser, _context
    
    try:
        if _context:
            await _context.close()
            _context = None
        
        if _browser:
            await _browser.close()
            _browser = None
            
        logger.info("Browser cleanup completed")
    except Exception as e:
        logger.error(f"Error during browser cleanup: {e}")


async def scrape_odds_from_page(url: str, target_selector: str, 
                               extraction_logic: callable,
                               page_specific_config: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Production-safe odds scraping with comprehensive error handling and debugging.
    
    Args:
        url: Target URL to scrape
        target_selector: CSS selector to wait for
        extraction_logic: Function to extract data from page
        page_specific_config: Additional page-specific configuration
    
    Returns:
        Dictionary containing scraped odds data
    """
    browser, context = await init_browser()
    page = None
    
    try:
        page = await context.new_page()
        
        # Set up console message logging
        async def log_console_message(msg):
            if msg.type in ['error', 'warning']:
                logger.warning(f"Console {msg.type}: {msg.text}")
            else:
                logger.debug(f"Console {msg.type}: {msg.text}")
        
        page.on("console", log_console_message)
        
        # Navigate to page with production-safe settings
        logger.info(f"Navigating to: {url}")
        
        await page.goto(
            url,
            wait_until="domcontentloaded",
            timeout=45000
        )
        
        # Apply page-specific configuration if provided
        if page_specific_config:
            # Handle cookies consent if needed
            if page_specific_config.get("accept_cookies_selector"):
                try:
                    await page.click(page_specific_config["accept_cookies_selector"], timeout=5000)
                    logger.debug("Accepted cookies")
                except PlaywrightTimeoutError:
                    logger.debug("No cookies banner found or already accepted")
            
            # Handle any page-specific actions
            if page_specific_config.get("pre_scrape_actions"):
                for action in page_specific_config["pre_scrape_actions"]:
                    try:
                        if action["type"] == "click":
                            await page.click(action["selector"], timeout=action.get("timeout", 10000))
                        elif action["type"] == "wait":
                            await page.wait_for_timeout(action["duration"])
                        elif action["type"] == "scroll":
                            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    except Exception as action_error:
                        logger.warning(f"Pre-scrape action failed: {action_error}")
        
        # Wait for target selector to be visible
        logger.debug(f"Waiting for selector: {target_selector}")
        
        try:
            await page.wait_for_selector(
                target_selector,
                state="visible",
                timeout=60000
            )
        except PlaywrightTimeoutError:
            logger.error(f"Target selector not found: {target_selector}")
            await debug_page_state(page, "selector_timeout")
            return {"error": "Target selector not found", "odds": []}
        
        # Wait for network to be idle (odds fully loaded)
        try:
            await page.wait_for_load_state("networkidle", timeout=30000)
        except PlaywrightTimeoutError:
            logger.warning("Network didn't become idle, proceeding anyway")
        
        # Additional wait for dynamic content
        await page.wait_for_timeout(2000)
        
        # Extract odds using provided logic
        logger.debug("Extracting odds data")
        odds_data = await extraction_logic(page)
        
        # Validate extracted data
        if not odds_data or (isinstance(odds_data, dict) and not odds_data.get("odds")):
            logger.warning("No odds data extracted, debugging page state")
            await debug_page_state(page, "no_odds_data")
            return {"error": "No odds data found", "odds": []}
        
        logger.info(f"Successfully extracted {len(odds_data.get('odds', []))} odds entries")
        return odds_data
        
    except Exception as e:
        logger.error(f"Error scraping odds from {url}: {e}")
        if page:
            await debug_page_state(page, "general_error")
        return {"error": str(e), "odds": []}
    
    finally:
        if page:
            try:
                await page.close()
            except:
                pass


async def debug_page_state(page: Page, debug_reason: str):
    """Debug page state when odds extraction fails."""
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Save page HTML
        content = await page.content()
        html_file = f"/tmp/odds_debug_{debug_reason}_{timestamp}.html"
        
        with open(html_file, 'w', encoding='utf-8') as f:
            f.write(content)
        logger.warning(f"Page HTML saved to: {html_file}")
        
        # Take screenshot
        screenshot_file = f"/tmp/odds_debug_{debug_reason}_{timestamp}.png"
        await page.screenshot(path=screenshot_file, full_page=True)
        logger.warning(f"Screenshot saved to: {screenshot_file}")
        
        # Log page title and URL
        title = await page.title()
        url = page.url
        logger.warning(f"Debug info - Title: {title}, URL: {url}")
        
        # Check for common error indicators
        error_selectors = [
            'div[class*="error"]',
            'div[class*="blocked"]', 
            'div[class*="captcha"]',
            'div[class*="bot-protection"]'
        ]
        
        for selector in error_selectors:
            elements = await page.query_selector_all(selector)
            if elements:
                text = await elements[0].text_content()
                logger.warning(f"Found error element: {selector} - {text}")
        
    except Exception as debug_error:
        logger.error(f"Failed to debug page state: {debug_error}")


class ArbitrageEngine:
    """Engine for detecting and calculating arbitrage opportunities."""
    
    def __init__(self):
        self.min_arb_percentage = settings.min_arb_percentage
        self.min_profit_amount = settings.min_profit_amount
        self.default_bankroll = settings.default_bankroll
        self.odds_tolerance = settings.odds_tolerance
    
    def detect_arbitrages(self, matched_events: List[MatchedEvent], 
                         filters: Optional[ArbitrageFilters] = None) -> List[ArbitrageOpportunity]:
        """Detect arbitrage opportunities from matched events."""
        logger.info(f"Detecting arbitrages from {len(matched_events)} matched events")
        
        arbitrages = []
        
        for event in matched_events:
            try:
                # Apply filters early to skip irrelevant events
                if not self._passes_event_filters(event, filters):
                    continue
                
                # Check each market in the event
                for market_key, market in event.markets.items():
                    market_arbs = self._detect_market_arbitrages(event, market_key, market, filters)
                    arbitrages.extend(market_arbs)
                
                # Check for cross-market arbitrages (e.g., combining different lines)
                cross_market_arbs = self._detect_cross_market_arbitrages(event, filters)
                arbitrages.extend(cross_market_arbs)
                
            except Exception as e:
                logger.error(f"Error processing event {event.event.canonical_name}: {e}")
                continue
        
        # Sort by profit percentage (descending)
        arbitrages.sort(key=lambda x: x.profit_percentage, reverse=True)
        
        logger.info(f"Detected {len(arbitrages)} arbitrage opportunities")
        return arbitrages
    
    def _passes_event_filters(self, event: MatchedEvent, filters: Optional[ArbitrageFilters]) -> bool:
        """Check if event passes basic filters."""
        if not filters:
            return True
        
        # Sport filter
        if filters.sport and event.event.sport != filters.sport:
            return False
        
        # Live/pre-match filter
        if filters.live_only is not None:
            if filters.live_only != event.event.is_live:
                return False
        
        # Time filter for future events
        if filters.max_start_hours and event.event.start_time:
            max_time = datetime.now() + timedelta(hours=filters.max_start_hours)
            if event.event.start_time > max_time:
                return False
        
        return True
    
    def _detect_market_arbitrages(self, event: MatchedEvent, market_key: str, 
                                 market, filters: Optional[ArbitrageFilters]) -> List[ArbitrageOpportunity]:
        """Detect arbitrages within a single market."""
        arbitrages = []
        
        try:
            # Apply market type filter
            if filters and filters.market_type and market.market_type != filters.market_type:
                return arbitrages
            
            # Get fresh outcomes (filter stale data)
            fresh_outcomes = self._get_fresh_outcomes(market.outcomes, event.event.is_live)
            
            if len(fresh_outcomes) < 2:
                return arbitrages
            
            # Get best odds per outcome from different bookmakers
            best_odds = self._get_best_odds_per_outcome(fresh_outcomes, filters)
            
            if len(best_odds) < 2:
                return arbitrages
            
            # Calculate arbitrage percentage
            arb_calc = self._calculate_arbitrage(best_odds)
            if not arb_calc:
                return arbitrages
            
            arb_percentage, profit_percentage = arb_calc
            
            # Apply arbitrage filters
            if not self._passes_arbitrage_filters(arb_percentage, profit_percentage, filters):
                return arbitrages
            
            # Calculate stakes and profit
            bankroll = filters.bankroll if filters and filters.bankroll else self.default_bankroll
            stakes = self._calculate_stakes(best_odds, bankroll)
            guaranteed_profit = bankroll * (profit_percentage / 100)
            
            # Apply minimum profit filter
            if filters and filters.min_profit and guaranteed_profit < filters.min_profit:
                return arbitrages
            
            # Create arbitrage opportunity
            arb = ArbitrageOpportunity(
                event_name=event.event.canonical_name,
                start_time=event.event.start_time,
                sport=event.event.sport.value if event.event.sport else None,
                league=event.event.league,
                market_type=market.market_type.value,
                line=market.line,
                outcomes=list(best_odds.values()),
                arb_percentage=arb_percentage,
                profit_percentage=profit_percentage,
                guaranteed_profit=guaranteed_profit,
                bankroll=bankroll,
                stakes=stakes,
                freshness_score=self._calculate_freshness_score(best_odds.values())
            )
            
            arbitrages.append(arb)
            
        except Exception as e:
            logger.debug(f"Error detecting arbitrage in market {market_key}: {e}")
        
        return arbitrages
    
    def _get_fresh_outcomes(self, outcomes: Dict[str, OutcomeData], is_live: bool) -> Dict[str, OutcomeData]:
        """Filter outcomes by data freshness."""
        fresh_outcomes = {}
        
        max_age_seconds = settings.live_odds_max_age if is_live else settings.prematch_odds_max_age
        cutoff_time = datetime.now() - timedelta(seconds=max_age_seconds)
        
        for outcome_name, outcome in outcomes.items():
            if outcome.last_seen >= cutoff_time:
                fresh_outcomes[outcome_name] = outcome
        
        return fresh_outcomes
    
    def _get_best_odds_per_outcome(self, outcomes: Dict[str, OutcomeData], 
                                  filters: Optional[ArbitrageFilters]) -> Dict[str, OutcomeData]:
        """Get best odds for each outcome, ensuring different bookmakers."""
        best_odds = {}
        used_bookmakers = set()
        
        # Group outcomes by name
        outcome_groups = {}
        for outcome_name, outcome in outcomes.items():
            if outcome_name not in outcome_groups:
                outcome_groups[outcome_name] = []
            outcome_groups[outcome_name].append(outcome)
        
        # For each outcome, find the best odds from an unused bookmaker
        for outcome_name, outcome_list in outcome_groups.items():
            # Apply bookmaker filter
            if filters and filters.bookmakers:
                outcome_list = [o for o in outcome_list if o.bookmaker in filters.bookmakers]
            
            # Sort by odds (descending) and filter by unused bookmakers
            available_outcomes = [o for o in outcome_list if o.bookmaker not in used_bookmakers]
            
            if available_outcomes:
                best_outcome = max(available_outcomes, key=lambda x: x.odds)
                best_odds[outcome_name] = best_outcome
                used_bookmakers.add(best_outcome.bookmaker)
        
        return best_odds
    
    def _calculate_arbitrage(self, best_odds: Dict[str, OutcomeData]) -> Optional[Tuple[float, float]]:
        """Calculate arbitrage percentage and profit percentage."""
        if len(best_odds) < 2:
            return None
        
        try:
            # Calculate implied probabilities
            implied_probabilities = []
            for outcome in best_odds.values():
                if outcome.odds <= 1.0:
                    return None
                implied_prob = 1.0 / outcome.odds
                implied_probabilities.append(implied_prob)
            
            # Calculate arbitrage percentage
            total_implied_prob = sum(implied_probabilities)
            arb_percentage = total_implied_prob * 100
            
            # Calculate profit percentage
            if total_implied_prob >= 1.0:
                return None  # No arbitrage opportunity
            
            profit_percentage = ((1.0 / total_implied_prob) - 1.0) * 100
            
            return round(arb_percentage, 4), round(profit_percentage, 4)
            
        except Exception as e:
            logger.debug(f"Error calculating arbitrage: {e}")
            return None
    
    def _passes_arbitrage_filters(self, arb_percentage: float, profit_percentage: float, 
                                 filters: Optional[ArbitrageFilters]) -> bool:
        """Check if arbitrage passes filter criteria."""
        if not filters:
            # Use default minimum thresholds
            return (arb_percentage < 100.0 and 
                   profit_percentage >= self.min_arb_percentage)
        
        # Check minimum arbitrage percentage
        if filters.min_arb_percentage is not None:
            if profit_percentage < filters.min_arb_percentage:
                return False
        else:
            if profit_percentage < self.min_arb_percentage:
                return False
        
        # Must be a profitable arbitrage
        return arb_percentage < 100.0
    
    def _calculate_stakes(self, best_odds: Dict[str, OutcomeData], bankroll: float) -> List[StakeCalculation]:
        """Calculate optimal stake distribution for arbitrage."""
        stakes = []
        
        try:
            # Calculate total inverse odds
            total_inverse = sum(1.0 / outcome.odds for outcome in best_odds.values())
            
            for outcome_name, outcome in best_odds.items():
                # Calculate proportional stake
                stake_proportion = (1.0 / outcome.odds) / total_inverse
                stake_amount = bankroll * stake_proportion
                
                # Calculate potential profit for this outcome
                potential_return = stake_amount * outcome.odds
                potential_profit = potential_return - bankroll
                
                stake_calc = StakeCalculation(
                    outcome_name=outcome_name,
                    bookmaker=outcome.bookmaker,
                    stake_amount=round(stake_amount, 2),
                    potential_profit=round(potential_profit, 2),
                    url=outcome.url
                )
                
                stakes.append(stake_calc)
        
        except Exception as e:
            logger.error(f"Error calculating stakes: {e}")
        
        return stakes
    
    def _calculate_freshness_score(self, outcomes) -> float:
        """Calculate freshness score based on data age."""
        if not outcomes:
            return 0.0
        
        now = datetime.now()
        total_age = 0
        count = 0
        
        for outcome in outcomes:
            age_seconds = (now - outcome.last_seen).total_seconds()
            total_age += age_seconds
            count += 1
        
        avg_age_seconds = total_age / count
        
        # Convert to freshness score (1.0 = fresh, 0.0 = very stale)
        # Assume 300 seconds (5 minutes) is the maximum acceptable age
        max_acceptable_age = 300
        freshness = max(0.0, 1.0 - (avg_age_seconds / max_acceptable_age))
        
        return round(freshness, 3)
    
    def _detect_cross_market_arbitrages(self, event: MatchedEvent, 
                                       filters: Optional[ArbitrageFilters]) -> List[ArbitrageOpportunity]:
        """Detect arbitrages across different markets (advanced feature)."""
        # This is a complex feature that looks for arbitrages by combining
        # outcomes from different but related markets (e.g., different handicap lines)
        
        arbitrages = []
        
        try:
            # Group markets by type
            markets_by_type = {}
            for market_key, market in event.markets.items():
                market_type = market.market_type.value
                if market_type not in markets_by_type:
                    markets_by_type[market_type] = []
                markets_by_type[market_type].append((market_key, market))
            
            # Look for arbitrages in handicap markets with different lines
            if 'handicap' in markets_by_type:
                handicap_arbs = self._detect_handicap_line_arbitrages(
                    markets_by_type['handicap'], event, filters
                )
                arbitrages.extend(handicap_arbs)
            
            # Look for arbitrages in total markets with different lines
            if 'totals' in markets_by_type:
                totals_arbs = self._detect_totals_line_arbitrages(
                    markets_by_type['totals'], event, filters
                )
                arbitrages.extend(totals_arbs)
        
        except Exception as e:
            logger.debug(f"Error detecting cross-market arbitrages: {e}")
        
        return arbitrages
    
    def _detect_handicap_line_arbitrages(self, handicap_markets: List[Tuple], 
                                        event: MatchedEvent, 
                                        filters: Optional[ArbitrageFilters]) -> List[ArbitrageOpportunity]:
        """Detect arbitrages between different handicap lines."""
        arbitrages = []
        
        # For now, this is a placeholder for advanced handicap arbitrage detection
        # This would involve complex calculations considering different handicap lines
        # and finding middle opportunities
        
        return arbitrages
    
    def _detect_totals_line_arbitrages(self, totals_markets: List[Tuple], 
                                      event: MatchedEvent, 
                                      filters: Optional[ArbitrageFilters]) -> List[ArbitrageOpportunity]:
        """Detect arbitrages between different totals lines (middles)."""
        arbitrages = []
        
        try:
            # Look for middle opportunities between different total lines
            # Example: Over 2.5 at one book, Under 3.5 at another
            # If final score is exactly 3, both bets win
            
            if len(totals_markets) < 2:
                return arbitrages
            
            for i, (key1, market1) in enumerate(totals_markets):
                for j, (key2, market2) in enumerate(totals_markets[i+1:], i+1):
                    
                    line1 = market1.line
                    line2 = market2.line
                    
                    if line1 is None or line2 is None:
                        continue
                    
                    # Check if lines are suitable for middle
                    if isinstance(line1, (int, float)) and isinstance(line2, (int, float)):
                        if abs(line1 - line2) == 1.0:  # Lines differ by exactly 1
                            middle_arb = self._calculate_middle_opportunity(
                                market1, market2, line1, line2, event, filters
                            )
                            if middle_arb:
                                arbitrages.append(middle_arb)
        
        except Exception as e:
            logger.debug(f"Error detecting totals line arbitrages: {e}")
        
        return arbitrages
    
    def _calculate_middle_opportunity(self, market1, market2, line1: float, line2: float,
                                     event: MatchedEvent, 
                                     filters: Optional[ArbitrageFilters]) -> Optional[ArbitrageOpportunity]:
        """Calculate middle opportunity between two totals markets."""
        try:
            # This is a simplified middle calculation
            # In practice, this would involve more complex probability calculations
            
            # Get best odds for relevant outcomes
            outcomes = {}
            
            # Find Over for lower line and Under for higher line
            lower_line = min(line1, line2)
            higher_line = max(line1, line2)
            
            lower_market = market1 if line1 == lower_line else market2
            higher_market = market2 if line2 == higher_line else market1
            
            # Get Over odds for lower line
            for outcome_name, outcome in lower_market.outcomes.items():
                if 'over' in outcome_name.lower():
                    outcomes[f"Over {lower_line}"] = outcome
                    break
            
            # Get Under odds for higher line
            for outcome_name, outcome in higher_market.outcomes.items():
                if 'under' in outcome_name.lower():
                    outcomes[f"Under {higher_line}"] = outcome
                    break
            
            if len(outcomes) < 2:
                return None
            
            # Calculate if this creates an arbitrage or middle opportunity
            arb_calc = self._calculate_arbitrage(outcomes)
            if not arb_calc:
                return None
            
            arb_percentage, profit_percentage = arb_calc
            
            if not self._passes_arbitrage_filters(arb_percentage, profit_percentage, filters):
                return None
            
            # Create arbitrage opportunity
            bankroll = filters.bankroll if filters and filters.bankroll else self.default_bankroll
            stakes = self._calculate_stakes(outcomes, bankroll)
            guaranteed_profit = bankroll * (profit_percentage / 100)
            
            return ArbitrageOpportunity(
                event_name=event.event.canonical_name,
                start_time=event.event.start_time,
                sport=event.event.sport.value if event.event.sport else None,
                league=event.event.league,
                market_type=f"Middle {lower_line}-{higher_line}",
                line=f"{lower_line}/{higher_line}",
                outcomes=list(outcomes.values()),
                arb_percentage=arb_percentage,
                profit_percentage=profit_percentage,
                guaranteed_profit=guaranteed_profit,
                bankroll=bankroll,
                stakes=stakes,
                freshness_score=self._calculate_freshness_score(outcomes.values())
            )
        
        except Exception as e:
            logger.debug(f"Error calculating middle opportunity: {e}")
            return None


# Example usage functions for different betting sites
async def scrape_bet365_odds(url: str) -> Dict[str, Any]:
    """Example: Scrape odds from Bet365."""
    
    async def extract_bet365_odds(page: Page) -> Dict[str, Any]:
        """Extract odds from Bet365 page."""
        try:
            # Wait for odds elements to load
            await page.wait_for_selector('.gl-Market_General', timeout=30000)
            
            odds_data = {
                "bookmaker": "bet365",
                "timestamp": datetime.now().isoformat(),
                "odds": []
            }
            
            # Extract match information
            match_name = await page.text_content('.rcl-ParticipantFixtureDetails_TeamNames')
            if match_name:
                odds_data["match"] = match_name.strip()
            
            # Extract odds for main markets
            market_elements = await page.query_selector_all('.gl-Market_General')
            
            for market_element in market_elements:
                try:
                    # Get market name
                    market_header = await market_element.query_selector('.gl-MarketGroupPod_FixtureHeaderLabel')
                    market_name = await market_header.text_content() if market_header else "Unknown Market"
                    
                    # Get outcomes and odds
                    outcome_elements = await market_element.query_selector_all('.gl-Participant_General')
                    
                    for outcome_element in outcome_elements:
                        outcome_name_elem = await outcome_element.query_selector('.gl-Participant_Name')
                        odds_elem = await outcome_element.query_selector('.gl-Participant_Odds')
                        
                        if outcome_name_elem and odds_elem:
                            outcome_name = await outcome_name_elem.text_content()
                            odds_text = await odds_elem.text_content()
                            
                            # Convert odds to decimal format
                            try:
                                if '/' in odds_text:  # Fractional odds
                                    parts = odds_text.split('/')
                                    decimal_odds = (float(parts[0]) / float(parts[1])) + 1.0
                                else:
                                    decimal_odds = float(odds_text)
                                
                                odds_data["odds"].append({
                                    "market": market_name.strip(),
                                    "outcome": outcome_name.strip(),
                                    "odds": round(decimal_odds, 2),
                                    "url": page.url
                                })
                            except ValueError:
                                logger.warning(f"Could not parse odds: {odds_text}")
                
                except Exception as market_error:
                    logger.warning(f"Error processing market: {market_error}")
                    continue
            
            return odds_data
            
        except Exception as e:
            logger.error(f"Error extracting Bet365 odds: {e}")
            return {"bookmaker": "bet365", "odds": [], "error": str(e)}
    
    return await scrape_odds_from_page(
        url=url,
        target_selector='.gl-Market_General',
        extraction_logic=extract_bet365_odds,
        page_specific_config={
            "accept_cookies_selector": ".ccm-CookieConsentPopup_Accept",
            "pre_scrape_actions": [
                {"type": "wait", "duration": 3000},  # Wait for odds to stabilize
            ]
        }
    )


async def scrape_pinnacle_odds(url: str) -> Dict[str, Any]:
    """Example: Scrape odds from Pinnacle."""
    
    async def extract_pinnacle_odds(page: Page) -> Dict[str, Any]:
        """Extract odds from Pinnacle page."""
        try:
            # Wait for odds container
            await page.wait_for_selector('[data-test-id="MarketGrid"]', timeout=30000)
            
            odds_data = {
                "bookmaker": "pinnacle",
                "timestamp": datetime.now().isoformat(),
                "odds": []
            }
            
            # Extract event name
            event_name_elem = await page.query_selector('.event-card-participant-name')
            if event_name_elem:
                event_name = await event_name_elem.text_content()
                odds_data["match"] = event_name.strip()
            
            # Extract markets and odds
            market_grids = await page.query_selector_all('[data-test-id="MarketGrid"]')
            
            for market_grid in market_grids:
                try:
                    # Get market name
                    market_name_elem = await market_grid.query_selector('.market-type-name')
                    market_name = await market_name_elem.text_content() if market_name_elem else "Unknown Market"
                    
                    # Get odds buttons
                    odds_buttons = await market_grid.query_selector_all('[data-test-id="price-button"]')
                    
                    for button in odds_buttons:
                        try:
                            # Get outcome name
                            outcome_elem = await button.query_selector('.participant-name')
                            outcome_name = await outcome_elem.text_content() if outcome_elem else ""
                            
                            # Get odds
                            odds_elem = await button.query_selector('.price')
                            odds_text = await odds_elem.text_content() if odds_elem else ""
                            
                            if outcome_name and odds_text:
                                try:
                                    decimal_odds = float(odds_text)
                                    
                                    odds_data["odds"].append({
                                        "market": market_name.strip(),
                                        "outcome": outcome_name.strip(),
                                        "odds": round(decimal_odds, 2),
                                        "url": page.url
                                    })
                                except ValueError:
                                    logger.warning(f"Could not parse Pinnacle odds: {odds_text}")
                        
                        except Exception as button_error:
                            logger.warning(f"Error processing odds button: {button_error}")
                            continue
                
                except Exception as market_error:
                    logger.warning(f"Error processing Pinnacle market: {market_error}")
                    continue
            
            return odds_data
            
        except Exception as e:
            logger.error(f"Error extracting Pinnacle odds: {e}")
            return {"bookmaker": "pinnacle", "odds": [], "error": str(e)}
    
    return await scrape_odds_from_page(
        url=url,
        target_selector='[data-test-id="MarketGrid"]',
        extraction_logic=extract_pinnacle_odds
    )


async def scrape_generic_sportsbook(url: str, site_config: Dict[str, Any]) -> Dict[str, Any]:
    """Generic sportsbook scraper with configurable selectors."""
    
    async def extract_generic_odds(page: Page) -> Dict[str, Any]:
        """Extract odds using provided configuration."""
        try:
            odds_data = {
                "bookmaker": site_config.get("name", "unknown"),
                "timestamp": datetime.now().isoformat(),
                "odds": []
            }
            
            # Extract match name if configured
            if site_config.get("match_selector"):
                match_elem = await page.query_selector(site_config["match_selector"])
                if match_elem:
                    match_name = await match_elem.text_content()
                    odds_data["match"] = match_name.strip()
            
            # Extract odds using configured selectors
            market_selector = site_config.get("market_selector", "")
            odds_selector = site_config.get("odds_selector", "")
            
            if market_selector and odds_selector:
                market_elements = await page.query_selector_all(market_selector)
                
                for market_element in market_elements:
                    try:
                        # Get market name
                        market_name = "Unknown Market"
                        if site_config.get("market_name_selector"):
                            market_name_elem = await market_element.query_selector(site_config["market_name_selector"])
                            if market_name_elem:
                                market_name = await market_name_elem.text_content()
                        
                        # Get odds within this market
                        odds_elements = await market_element.query_selector_all(odds_selector)
                        
                        for odds_element in odds_elements:
                            try:
                                # Extract outcome name
                                outcome_name = ""
                                if site_config.get("outcome_name_selector"):
                                    outcome_elem = await odds_element.query_selector(site_config["outcome_name_selector"])
                                    if outcome_elem:
                                        outcome_name = await outcome_elem.text_content()
                                
                                # Extract odds value
                                odds_value = ""
                                if site_config.get("odds_value_selector"):
                                    odds_elem = await odds_element.query_selector(site_config["odds_value_selector"])
                                    if odds_elem:
                                        odds_value = await odds_elem.text_content()
                                
                                if outcome_name and odds_value:
                                    try:
                                        # Convert to decimal odds based on format
                                        decimal_odds = float(odds_value)
                                        
                                        # Apply odds conversion if needed
                                        if site_config.get("odds_format") == "american":
                                            decimal_odds = american_to_decimal(float(odds_value))
                                        elif site_config.get("odds_format") == "fractional":
                                            decimal_odds = fractional_to_decimal(odds_value)
                                        
                                        odds_data["odds"].append({
                                            "market": market_name.strip(),
                                            "outcome": outcome_name.strip(),
                                            "odds": round(decimal_odds, 2),
                                            "url": page.url
                                        })
                                    except ValueError:
                                        logger.warning(f"Could not parse odds: {odds_value}")
                            
                            except Exception as odds_error:
                                logger.warning(f"Error processing odds element: {odds_error}")
                                continue
                    
                    except Exception as market_error:
                        logger.warning(f"Error processing market: {market_error}")
                        continue
            
            return odds_data
            
        except Exception as e:
            logger.error(f"Error extracting generic odds: {e}")
            return {"bookmaker": site_config.get("name", "unknown"), "odds": [], "error": str(e)}
    
    return await scrape_odds_from_page(
        url=url,
        target_selector=site_config.get("target_selector", "body"),
        extraction_logic=extract_generic_odds,
        page_specific_config=site_config.get("page_config", {})
    )


def american_to_decimal(american_odds: float) -> float:
    """Convert American odds to decimal odds."""
    if american_odds > 0:
        return (american_odds / 100) + 1
    else:
        return (100 / abs(american_odds)) + 1


def fractional_to_decimal(fractional_odds: str) -> float:
    """Convert fractional odds to decimal odds."""
    try:
        if '/' in fractional_odds:
            numerator, denominator = fractional_odds.split('/')
            return (float(numerator) / float(denominator)) + 1
        else:
            return float(fractional_odds)
    except:
        return 1.0


async def main():
    """Main application entry point."""
    try:
        # Initialize browser on startup
        await init_browser()
        
        # Start FastAPI server
        port = int(os.getenv("PORT", 10000))
        host = os.getenv("HOST", "0.0.0.0")
        
        config = uvicorn.Config(
            app=app,
            host=host,
            port=port,
            log_level="info",
            access_log=True
        )
        
        server = uvicorn.Server(config)
        
        logger.info(f"Starting arbitrage detection service on {host}:{port}")
        
        try:
            await server.serve()
        finally:
            # Clean up browser on shutdown
            await cleanup_browser()
    
    except KeyboardInterrupt:
        logger.info("Received shutdown signal")
        await cleanup_browser()
    except Exception as e:
        logger.error(f"Application error: {e}")
        await cleanup_browser()
        raise


if __name__ == "__main__":
    # Run the application
    asyncio.run(main())
