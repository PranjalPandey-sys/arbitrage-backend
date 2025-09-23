"""Production-ready arbitrage detection and calculation engine with Playwright web scraping."""

import asyncio
import json
import math
import os
import tempfile
import traceback
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple, Any
from decimal import Decimal, ROUND_HALF_UP

import httpx
from playwright.async_api import async_playwright, Browser, BrowserContext, Page, TimeoutError as PlaywrightTimeoutError
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

try:
    from app.schema.models import (
        MatchedEvent, ArbitrageOpportunity, OutcomeData, 
        StakeCalculation, ArbitrageFilters
    )
    from app.config import settings
    from app.utils.logging import get_logger
except ImportError:
    # Fallback for missing modules
    print("Warning: Some app modules not found, using fallbacks")
    
    class MockSettings:
        min_arb_percentage = 2.0
        min_profit_amount = 10.0
        default_bankroll = 1000.0
        odds_tolerance = 0.02
        live_odds_max_age = 30
        prematch_odds_max_age = 300
    
    settings = MockSettings()
    
    import logging
    def get_logger(name):
        logging.basicConfig(level=logging.INFO)
        return logging.getLogger(name)

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

async def retry_with_backoff(func, *args, max_retries=3, base_delay=1.0, **kwargs):
    """Retry function with exponential backoff."""
    for attempt in range(max_retries):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            if attempt == max_retries - 1:
                raise e
            
            delay = base_delay * (2 ** attempt)
            logger.warning(f"Attempt {attempt + 1} failed: {e}. Retrying in {delay}s...")
            await asyncio.sleep(delay)

async def http_request_with_retry(method: str, url: str, **kwargs) -> httpx.Response:
    """Make HTTP request with retry and backoff."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        return await retry_with_backoff(
            getattr(client, method.lower()),
            url,
            **kwargs
        )

async def init_browser() -> Tuple[Browser, BrowserContext]:
    """Initialize production-safe Playwright browser with persistent context."""
    global _browser, _context
    
    if _browser and _context:
        return _browser, _context
    
    try:
        playwright = await async_playwright().start()
        
        # Get configuration from environment variables
        user_data_dir = os.getenv("PLAYWRIGHT_USER_DATA_DIR", "/tmp/chrome-user-data")
        headless = os.getenv("HEADLESS", "true").lower() in ("true", "1", "yes")
        proxy_url = os.getenv("PROXY_URL")
        
        # Production-safe Chromium launch arguments
        launch_args = [
            "--no-sandbox",
            "--disable-dev-shm-usage", 
            "--disable-gpu",
            "--disable-setuid-sandbox",
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
        ]
        
        # Optional: disable site isolation for better performance
        if os.getenv("DISABLE_SITE_ISOLATION", "false").lower() == "true":
            launch_args.append("--disable-features=site-per-process")
        
        # Setup proxy configuration
        proxy_config = None
        if proxy_url:
            logger.info(f"Using proxy: {proxy_url}")
            proxy_config = {"server": proxy_url}
        
        # Use launch_persistent_context for production deployment
        context_options = {
            "user_data_dir": user_data_dir,
            "headless": headless,
            "args": launch_args,
            "viewport": {"width": 1366, "height": 768},
            "locale": "en-US",
            "timezone_id": "UTC",  # Use UTC for consistency
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
            },
            "ignore_https_errors": True,
            "timeout": 60000
        }
        
        if proxy_config:
            context_options["proxy"] = proxy_config
        
        _context = await playwright.chromium.launch_persistent_context(**context_options)
        _browser = _context.browser
        
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
        
        logger.info(f"Browser initialized successfully (headless={headless}, user_data_dir={user_data_dir})")
        return _browser, _context
        
    except Exception as e:
        logger.error(f"Failed to initialize browser: {e}")
        logger.error(traceback.format_exc())
        raise

async def cleanup_browser():
    """Clean up browser resources."""
    global _browser, _context
    
    try:
        if _context:
            await _context.close()
            _context = None
        
        if _browser:
            # Browser is automatically closed when context closes in persistent mode
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
                    await page.wait_for_selector(
                        page_specific_config["accept_cookies_selector"], 
                        timeout=5000,
                        state="visible"
                    )
                    await page.click(page_specific_config["accept_cookies_selector"], timeout=5000)
                    logger.debug("Accepted cookies")
                except PlaywrightTimeoutError:
                    logger.debug("No cookies banner found or already accepted")
            
            # Handle any page-specific actions
            if page_specific_config.get("pre_scrape_actions"):
                for action in page_specific_config["pre_scrape_actions"]:
                    try:
                        if action["type"] == "click":
                            await page.wait_for_selector(action["selector"], timeout=action.get("timeout", 10000))
                            await page.click(action["selector"], timeout=action.get("timeout", 10000))
                        elif action["type"] == "wait":
                            await page.wait_for_timeout(action["duration"])
                        elif action["type"] == "scroll":
                            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    except Exception as action_error:
                        logger.warning(f"Pre-scrape action failed: {action_error}")
        
        # Wait for target selector to be visible with robust retry
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
        
        # Wait for network to be idle (odds fully loaded) with robust timeout
        try:
            await page.wait_for_load_state("networkidle", timeout=30000)
            logger.debug("Network became idle")
        except PlaywrightTimeoutError:
            logger.warning("Network didn't become idle, proceeding anyway")
        
        # Additional wait for dynamic content
        await page.wait_for_timeout(3000)
        
        # Extract odds using provided logic with retry
        logger.debug("Extracting odds data")
        odds_data = await retry_with_backoff(extraction_logic, page, max_retries=2)
        
        # Validate extracted data
        if not odds_data or (isinstance(odds_data, dict) and not odds_data.get("odds")):
            logger.warning("No odds data extracted, debugging page state")
            await debug_page_state(page, "no_odds_data")
            return {"error": "No odds data found", "odds": []}
        
        logger.info(f"Successfully extracted {len(odds_data.get('odds', []))} odds entries")
        return odds_data
        
    except Exception as e:
        logger.error(f"Error scraping odds from {url}: {e}")
        logger.error(traceback.format_exc())
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
        debug_dir = os.getenv("DEBUG_DIR", "/tmp")
        
        # Save page HTML
        content = await page.content()
        html_file = f"{debug_dir}/odds_debug_{debug_reason}_{timestamp}.html"
        
        with open(html_file, 'w', encoding='utf-8') as f:
            f.write(content)
        logger.warning(f"Page HTML saved to: {html_file}")
        
        # Take screenshot
        screenshot_file = f"{debug_dir}/odds_debug_{debug_reason}_{timestamp}.png"
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
            'div[class*="bot-protection"]',
            'div[class*="access-denied"]',
            'div[id*="error"]',
            '[data-testid*="error"]'
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
        self.min_arb_percentage = getattr(settings, 'min_arb_percentage', 2.0)
        self.min_profit_amount = getattr(settings, 'min_profit_amount', 10.0)
        self.default_bankroll = getattr(settings, 'default_bankroll', 1000.0)
        self.odds_tolerance = getattr(settings, 'odds_tolerance', 0.02)
    
    def detect_arbitrages(self, matched_events: List, 
                         filters: Optional[Dict] = None) -> List:
        """Detect arbitrage opportunities from matched events."""
        logger.info(f"Detecting arbitrages from {len(matched_events)} matched events")
        
        arbitrages = []
        
        for event in matched_events:
            try:
                # Apply filters early to skip irrelevant events
                if not self._passes_event_filters(event, filters):
                    continue
                
                # Check each market in the event
                markets = getattr(event, 'markets', {})
                for market_key, market in markets.items():
                    market_arbs = self._detect_market_arbitrages(event, market_key, market, filters)
                    arbitrages.extend(market_arbs)
                
                # Check for cross-market arbitrages
                cross_market_arbs = self._detect_cross_market_arbitrages(event, filters)
                arbitrages.extend(cross_market_arbs)
                
            except Exception as e:
                event_name = getattr(getattr(event, 'event', {}), 'canonical_name', 'unknown')
                logger.error(f"Error processing event {event_name}: {e}")
                continue
        
        # Sort by profit percentage (descending)
        arbitrages.sort(key=lambda x: getattr(x, 'profit_percentage', 0), reverse=True)
        
        logger.info(f"Detected {len(arbitrages)} arbitrage opportunities")
        return arbitrages
    
    def _passes_event_filters(self, event, filters: Optional[Dict]) -> bool:
        """Check if event passes basic filters."""
        if not filters:
            return True
        
        event_obj = getattr(event, 'event', {})
        
        # Sport filter
        sport_filter = filters.get('sport')
        if sport_filter and getattr(event_obj, 'sport', None) != sport_filter:
            return False
        
        # Live/pre-match filter
        live_only = filters.get('live_only')
        if live_only is not None:
            if live_only != getattr(event_obj, 'is_live', False):
                return False
        
        # Time filter for future events
        max_start_hours = filters.get('max_start_hours')
        if max_start_hours and getattr(event_obj, 'start_time', None):
            max_time = datetime.now() + timedelta(hours=max_start_hours)
            if event_obj.start_time > max_time:
                return False
        
        return True
    
    def _detect_market_arbitrages(self, event, market_key: str, 
                                 market, filters: Optional[Dict]) -> List:
        """Detect arbitrages within a single market."""
        arbitrages = []
        
        try:
            # Apply market type filter
            if filters and filters.get('market_type'):
                market_type = getattr(market, 'market_type', None)
                if market_type != filters['market_type']:
                    return arbitrages
            
            # Get fresh outcomes
            outcomes = getattr(market, 'outcomes', {})
            event_obj = getattr(event, 'event', {})
            is_live = getattr(event_obj, 'is_live', False)
            fresh_outcomes = self._get_fresh_outcomes(outcomes, is_live)
            
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
            bankroll = filters.get('bankroll', self.default_bankroll) if filters else self.default_bankroll
            stakes = self._calculate_stakes(best_odds, bankroll)
            guaranteed_profit = bankroll * (profit_percentage / 100)
            
            # Apply minimum profit filter
            min_profit = filters.get('min_profit') if filters else None
            if min_profit and guaranteed_profit < min_profit:
                return arbitrages
            
            # Create arbitrage opportunity (simplified for production)
            arb = {
                'event_name': getattr(event_obj, 'canonical_name', 'Unknown Event'),
                'start_time': getattr(event_obj, 'start_time', None),
                'sport': getattr(event_obj, 'sport', None),
                'league': getattr(event_obj, 'league', None),
                'market_type': getattr(market, 'market_type', 'Unknown'),
                'line': getattr(market, 'line', None),
                'outcomes': list(best_odds.values()),
                'arb_percentage': arb_percentage,
                'profit_percentage': profit_percentage,
                'guaranteed_profit': guaranteed_profit,
                'bankroll': bankroll,
                'stakes': stakes,
                'freshness_score': self._calculate_freshness_score(best_odds.values())
            }
            
            arbitrages.append(arb)
            
        except Exception as e:
            logger.debug(f"Error detecting arbitrage in market {market_key}: {e}")
        
        return arbitrages
    
    def _get_fresh_outcomes(self, outcomes: Dict, is_live: bool) -> Dict:
        """Filter outcomes by data freshness."""
        fresh_outcomes = {}
        
        live_max_age = getattr(settings, 'live_odds_max_age', 30)
        prematch_max_age = getattr(settings, 'prematch_odds_max_age', 300)
        max_age_seconds = live_max_age if is_live else prematch_max_age
        cutoff_time = datetime.now() - timedelta(seconds=max_age_seconds)
        
        for outcome_name, outcome in outcomes.items():
            last_seen = getattr(outcome, 'last_seen', datetime.now())
            if last_seen >= cutoff_time:
                fresh_outcomes[outcome_name] = outcome
        
        return fresh_outcomes
    
    def _get_best_odds_per_outcome(self, outcomes: Dict, 
                                  filters: Optional[Dict]) -> Dict:
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
            if filters and filters.get('bookmakers'):
                outcome_list = [o for o in outcome_list 
                              if getattr(o, 'bookmaker', None) in filters['bookmakers']]
            
            # Sort by odds (descending) and filter by unused bookmakers
            available_outcomes = [o for o in outcome_list 
                                if getattr(o, 'bookmaker', None) not in used_bookmakers]
            
            if available_outcomes:
                best_outcome = max(available_outcomes, key=lambda x: getattr(x, 'odds', 0))
                best_odds[outcome_name] = best_outcome
                used_bookmakers.add(getattr(best_outcome, 'bookmaker', None))
        
        return best_odds
    
    def _calculate_arbitrage(self, best_odds: Dict) -> Optional[Tuple[float, float]]:
        """Calculate arbitrage percentage and profit percentage."""
        if len(best_odds) < 2:
            return None
        
        try:
            # Calculate implied probabilities
            implied_probabilities = []
            for outcome in best_odds.values():
                odds = getattr(outcome, 'odds', 0)
                if odds <= 1.0:
                    return None
                implied_prob = 1.0 / odds
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
                                 filters: Optional[Dict]) -> bool:
        """Check if arbitrage passes filter criteria."""
        if not filters:
            # Use default minimum thresholds
            return (arb_percentage < 100.0 and 
                   profit_percentage >= self.min_arb_percentage)
        
        # Check minimum arbitrage percentage
        min_arb_pct = filters.get('min_arb_percentage')
        if min_arb_pct is not None:
            if profit_percentage < min_arb_pct:
                return False
        else:
            if profit_percentage < self.min_arb_percentage:
                return False
        
        # Must be a profitable arbitrage
        return arb_percentage < 100.0
    
    def _calculate_stakes(self, best_odds: Dict, bankroll: float) -> List[Dict]:
        """Calculate optimal stake distribution for arbitrage."""
        stakes = []
        
        try:
            # Calculate total inverse odds
            total_inverse = sum(1.0 / getattr(outcome, 'odds', 1) for outcome in best_odds.values())
            
            for outcome_name, outcome in best_odds.items():
                # Calculate proportional stake
                odds = getattr(outcome, 'odds', 1)
                stake_proportion = (1.0 / odds) / total_inverse
                stake_amount = bankroll * stake_proportion
                
                # Calculate potential profit for this outcome
                potential_return = stake_amount * odds
                potential_profit = potential_return - bankroll
                
                stake_calc = {
                    'outcome_name': outcome_name,
                    'bookmaker': getattr(outcome, 'bookmaker', 'Unknown'),
                    'stake_amount': round(stake_amount, 2),
                    'potential_profit': round(potential_profit, 2),
                    'url': getattr(outcome, 'url', None)
                }
                
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
            last_seen = getattr(outcome, 'last_seen', now)
            age_seconds = (now - last_seen).total_seconds()
            total_age += age_seconds
            count += 1
        
        avg_age_seconds = total_age / count
        
        # Convert to freshness score (1.0 = fresh, 0.0 = very stale)
        max_acceptable_age = 300
        freshness = max(0.0, 1.0 - (avg_age_seconds / max_acceptable_age))
        
        return round(freshness, 3)
    
    def _detect_cross_market_arbitrages(self, event, 
                                       filters: Optional[Dict]) -> List:
        """Detect cross-market arbitrage opportunities."""
        # Simplified implementation for production
        return []

# Site-specific scraping functions

async def scrape_bet365_odds(url: str) -> Dict[str, Any]:
    """Scrape odds from Bet365."""
    async def extract_bet365_odds(page: Page) -> Dict[str, Any]:
        odds_data = {"bookmaker": "bet365", "odds": []}
        
        try:
            # Wait for odds container to load
            await page.wait_for_selector('.gl-MarketGroup', timeout=30000)
            
            # Extract odds from bet365 structure
            markets = await page.query_selector_all('.gl-MarketGroup')
            
            for market in markets:
                market_name_elem = await market.query_selector('.gl-MarketGroupButton_Text')
                market_name = await market_name_elem.text_content() if market_name_elem else "Unknown"
                
                outcomes = await market.query_selector_all('.gl-Participant')
                
                for outcome in outcomes:
                    name_elem = await outcome.query_selector('.gl-Participant_Name')
                    odds_elem = await outcome.query_selector('.gl-Participant_General')
                    
                    if name_elem and odds_elem:
                        name = await name_elem.text_content()
                        odds_text = await odds_elem.text_content()
                        
                        # Convert odds format
                        try:
                            if '/' in odds_text:
                                odds = fractional_to_decimal(odds_text.strip())
                            else:
                                odds = float(odds_text.strip())
                            
                            odds_data["odds"].append({
                                "market": market_name.strip(),
                                "outcome": name.strip(),
                                "odds": odds,
                                "timestamp": datetime.now().isoformat(),
                                "url": url
                            })
                        except ValueError:
                            continue
        
        except Exception as e:
            logger.error(f"Error extracting bet365 odds: {e}")
            odds_data["error"] = str(e)
        
        return odds_data
    
    page_config = {
        "accept_cookies_selector": ".ccm-CookieConsentPopup_Accept",
        "pre_scrape_actions": [
            {"type": "wait", "duration": 3000}
        ]
    }
    
    return await scrape_odds_from_page(
        url=url,
        target_selector=".gl-MarketGroup",
        extraction_logic=extract_bet365_odds,
        page_specific_config=page_config
    )

async def scrape_fanduel_odds(url: str) -> Dict[str, Any]:
    """Scrape odds from FanDuel."""
    async def extract_fanduel_odds(page: Page) -> Dict[str, Any]:
        odds_data = {"bookmaker": "fanduel", "odds": []}
        
        try:
            # Wait for odds to load
            await page.wait_for_selector('[data-test-id="ArrowButton"]', timeout=30000)
            
            # Extract odds from FanDuel structure
            markets = await page.query_selector_all('[data-test-id="Market"]')
            
            for market in markets:
                market_name_elem = await market.query_selector('[data-test-id="MarketName"]')
                market_name = await market_name_elem.text_content() if market_name_elem else "Unknown"
                
                outcomes = await market.query_selector_all('[data-test-id="OutcomeButton"]')
                
                for outcome in outcomes:
                    name_elem = await outcome.query_selector('[data-test-id="OutcomeName"]')
                    odds_elem = await outcome.query_selector('[data-test-id="OutcomeOdds"]')
                    
                    if name_elem and odds_elem:
                        name = await name_elem.text_content()
                        odds_text = await odds_elem.text_content()
                        
                        try:
                            # FanDuel uses American odds
                            american_odds = float(odds_text.replace('+', '').replace('−', '-'))
                            decimal_odds = american_to_decimal(american_odds)
                            
                            odds_data["odds"].append({
                                "market": market_name.strip(),
                                "outcome": name.strip(),
                                "odds": decimal_odds,
                                "timestamp": datetime.now().isoformat(),
                                "url": url
                            })
                        except ValueError:
                            continue
        
        except Exception as e:
            logger.error(f"Error extracting FanDuel odds: {e}")
            odds_data["error"] = str(e)
        
        return odds_data
    
    page_config = {
        "accept_cookies_selector": "[data-test-id='CookieBanner'] button",
        "pre_scrape_actions": [
            {"type": "wait", "duration": 2000}
        ]
    }
    
    return await scrape_odds_from_page(
        url=url,
        target_selector="[data-test-id='ArrowButton']",
        extraction_logic=extract_fanduel_odds,
        page_specific_config=page_config
    )

async def scrape_generic_odds(url: str, site_config: Dict[str, Any]) -> Dict[str, Any]:
    """Generic odds scraper for configurable sites."""
    async def extract_generic_odds(page: Page) -> Dict[str, Any]:
        odds_data = {"bookmaker": site_config.get("name", "unknown"), "odds": []}
        
        try:
            market_selector = site_config.get("market_selector", ".market")
            outcome_selector = site_config.get("outcome_selector", ".outcome")
            name_selector = site_config.get("name_selector", ".name")
            odds_selector = site_config.get("odds_selector", ".odds")
            
            markets = await page.query_selector_all(market_selector)
            
            for market in markets:
                try:
                    market_name = "Unknown"
                    market_name_selector = site_config.get("market_name_selector")
                    if market_name_selector:
                        market_name_elem = await market.query_selector(market_name_selector)
                        if market_name_elem:
                            market_name = await market_name_elem.text_content()
                    
                    outcomes = await market.query_selector_all(outcome_selector)
                    
                    for outcome in outcomes:
                        name_elem = await outcome.query_selector(name_selector)
                        odds_elem = await outcome.query_selector(odds_selector)
                        
                        if name_elem and odds_elem:
                            name = await name_elem.text_content()
                            odds_text = await odds_elem.text_content()
                            
                            try:
                                # Try to parse different odds formats
                                odds_text = odds_text.strip()
                                if '/' in odds_text:
                                    odds = fractional_to_decimal(odds_text)
                                elif '+' in odds_text or '−' in odds_text or odds_text.startswith('-'):
                                    american_odds = float(odds_text.replace('+', '').replace('−', '-'))
                                    odds = american_to_decimal(american_odds)
                                else:
                                    odds = float(odds_text)
                                
                                odds_data["odds"].append({
                                    "market": market_name.strip(),
                                    "outcome": name.strip(),
                                    "odds": odds,
                                    "timestamp": datetime.now().isoformat(),
                                    "url": url
                                })
                            except ValueError:
                                continue
                
                except Exception as market_error:
                    logger.warning(f"Error processing market: {market_error}")
                    continue
        
        except Exception as e:
            logger.error(f"Error extracting generic odds: {e}")
            odds_data["error"] = str(e)
        
        return odds_data
    
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

@app.get("/scrape")
async def scrape_endpoint(url: str, site: str = "generic"):
    """API endpoint for testing scraping functionality."""
    try:
        if site == "bet365":
            result = await scrape_bet365_odds(url)
        elif site == "fanduel":
            result = await scrape_fanduel_odds(url)
        else:
            # Generic scraper with basic config
            config = {
                "name": site,
                "target_selector": "body",
                "market_selector": ".market,.game,.event",
                "outcome_selector": ".outcome,.bet,.option",
                "name_selector": ".name,.team,.player",
                "odds_selector": ".odds,.price,.decimal"
            }
            result = await scrape_generic_odds(url, config)
        
        return JSONResponse(content=result)
    except Exception as e:
        logger.error(f"Scraping endpoint error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def main():
    """Main application entry point."""
    try:
        # Don't initialize browser on startup to allow API to start
        # Browser will be initialized on-demand when scraping is needed
        logger.info("Starting arbitrage detection service (browser will be initialized on-demand)")
        
        # Start FastAPI server
        port = int(os.getenv("PORT", 5000))
        host = os.getenv("HOST", "0.0.0.0")
        
        config = uvicorn.Config(
            app=app,
            host=host,
            port=port,
            log_level=os.getenv("LOG_LEVEL", "info").lower(),
            access_log=True
        )
        
        server = uvicorn.Server(config)
        
        logger.info(f"Starting arbitrage detection service on {host}:{port}")
        logger.info(f"Headless mode: {os.getenv('HEADLESS', 'true')}")
        logger.info(f"User data dir: {os.getenv('PLAYWRIGHT_USER_DATA_DIR', '/tmp/chrome-user-data')}")
        
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
        logger.error(traceback.format_exc())
        await cleanup_browser()
        raise

if __name__ == "__main__":
    # Run the application
    asyncio.run(main())