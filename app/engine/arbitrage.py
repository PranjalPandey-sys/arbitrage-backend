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
from playwright.async_api import (
    async_playwright,
    Browser,
    BrowserContext,
    Page,
    TimeoutError as PlaywrightTimeoutError
)
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

# Core application imports
try:
    from app.schema.models import (
        MatchedEvent,
        ArbitrageOpportunity,
        OutcomeData,
        StakeCalculation,
        ArbitrageFilters
    )
    from app.config import settings
    from app.utils.logging import get_logger
except ImportError:
    # Fallbacks to allow local testing without full package installed
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

# FastAPI application for health check
app = FastAPI(title="Arbitrage Detection API")

@app.get("/health")
async def health_check():
    """
    Lightweight health check endpoint.
    Used by Docker HEALTHCHECK and uptime monitors.
    """
    return JSONResponse(
        status_code=200,
        content={
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "service": "arbitrage-detection"
        }
    )

async def retry_with_backoff(
    func: callable,
    *args,
    max_retries: int = 3,
    base_delay: float = 1.0,
    **kwargs
) -> Any:
    """Retry an async function with exponential backoff."""
    for attempt in range(1, max_retries + 1):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            if attempt == max_retries:
                logger.error(f"Final retry failed ({attempt}/{max_retries}): {e}")
                raise
            delay = base_delay * (2 ** (attempt - 1))
            logger.warning(f"Attempt {attempt} failed: {e}. Retrying in {delay:.1f}s...")
            await asyncio.sleep(delay)

async def http_request_with_retry(
    method: str,
    url: str,
    **kwargs
) -> httpx.Response:
    """Make an HTTPX request with retry/backoff."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        http_method = getattr(client, method.lower())
        return await retry_with_backoff(http_method, url, **kwargs)

# Globals to reuse browser/context
_browser: Optional[Browser] = None
_context: Optional[BrowserContext] = None

async def init_browser() -> Tuple[Browser, BrowserContext]:
    """
    Initialize Playwright Chromium in a production-safe manner.
    Uses launch_persistent_context with env-controlled options.
    """
    global _browser, _context
    if _browser and _context:
        return _browser, _context

    try:
        playwright = await async_playwright().start()

        # Env-configurable parameters
        user_data_dir = os.getenv("PLAYWRIGHT_USER_DATA_DIR", "/tmp/chrome-user-data")
        headless = os.getenv("HEADLESS", "true").lower() in ("true", "1", "yes")
        proxy_url = os.getenv("PROXY_URL")

        # Mandatory Chromium flags
        launch_args = [
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-gpu",
            "--disable-setuid-sandbox",
        ]

        # Additional performance/security flags
        extra_flags = os.getenv("PLAYWRIGHT_EXTRA_ARGS")
        if extra_flags:
            launch_args += extra_flags.split()

        # Proxy configuration
        proxy_config = {"server": proxy_url} if proxy_url else None

        # Build context options
        context_opts = {
            "user_data_dir": user_data_dir,
            "headless": headless,
            "args": launch_args,
            "viewport": {"width": 1366, "height": 768},
            "locale": "en-US",
            "timezone_id": "UTC",
            "ignore_https_errors": True,
            "timeout": 60000,
        }
        if proxy_config:
            context_opts["proxy"] = proxy_config

        _context = await playwright.chromium.launch_persistent_context(**context_opts)
        _browser = _context.browser

        # Instrument request/response logging
        _context.on("request", lambda req: logger.debug(f"▶ {req.method} {req.url}"))
        _context.on("response", lambda res: (
            logger.warning(f"⚠ {res.status} {res.url}") if res.status >= 400
            else logger.debug(f"✔ {res.status} {res.url}")
        ))

        logger.info(
            f"Chromium initialized (headless={headless}, "
            f"user_data_dir={user_data_dir}, proxy={proxy_url})"
        )
        return _browser, _context

    except Exception as e:
        logger.error("Browser initialization failed", exc_info=e)
        raise

async def cleanup_browser():
    """Close persistent context and reset globals."""
    global _browser, _context
    if _context:
        await _context.close()
        _context = None
    _browser = None
    logger.info("Browser cleanup completed")
    
    # Set up console message logging
        async def log_console_message(msg):
            level = 'warning' if msg.type in ('error', 'warning') else 'debug'
            getattr(logger, level)(f"Console {msg.type}: {msg.text}")

        page.on("console", log_console_message)

        # Navigate to page with production-safe settings
        logger.info(f"Navigating to: {url}")
        await page.goto(url, wait_until="domcontentloaded", timeout=45000)

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
            for action in page_specific_config.get("pre_scrape_actions", []):
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
            await page.wait_for_selector(target_selector, state="visible", timeout=60000)
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
            except Exception:
                pass


async def debug_page_state(page: Page, debug_reason: str):
    """Debug page state when odds extraction fails."""
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        debug_dir = os.getenv("DEBUG_DIR", "/tmp")

        # Save page HTML
        html_file = os.path.join(debug_dir, f"odds_debug_{debug_reason}_{timestamp}.html")
        with open(html_file, 'w', encoding='utf-8') as f:
            f.write(await page.content())
        logger.warning(f"Page HTML saved to: {html_file}")

        # Take screenshot
        screenshot_file = os.path.join(debug_dir, f"odds_debug_{debug_reason}_{timestamp}.png")
        await page.screenshot(path=screenshot_file, full_page=True)
        logger.warning(f"Screenshot saved to: {screenshot_file}")

        # Log page title and URL
        logger.warning(f"Debug info - Title: {await page.title()}, URL: {page.url}")

        # Check for common error indicators
        for selector in [
            'div[class*="error"]',
            'div[class*="blocked"]',
            'div[class*="captcha"]',
            'div[class*="bot-protection"]',
            'div[class*="access-denied"]',
            'div[id*="error"]',
            '[data-testid*="error"]'
        ]:
            elements = await page.query_selector_all(selector)
            if elements:
                text = await elements[0].text_content()
                logger.warning(f"Found error element: {selector} - {text}")

    except Exception as debug_error:
        logger.error(f"Failed to debug page state: {debug_error}")
        
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

    def _get_best_odds_per_outcome(self, outcomes: Dict, filters: Optional[Dict]) -> Dict:
        """Get best odds for each outcome, ensuring different bookmakers."""
        best_odds = {}
        used_bookmakers = set()

        # Group outcomes by name
        outcome_groups: Dict[str, list] = {}
        for outcome_name, outcome in outcomes.items():
            outcome_groups.setdefault(outcome_name, []).append(outcome)

        # For each outcome, find the best odds from an unused bookmaker
        for outcome_name, outcome_list in outcome_groups.items():
            if filters and filters.get('bookmakers'):
                outcome_list = [o for o in outcome_list if getattr(o, 'bookmaker', None) in filters['bookmakers']]

            available_outcomes = [o for o in outcome_list if getattr(o, 'bookmaker', None) not in used_bookmakers]
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
            implied_probabilities = []
            for outcome in best_odds.values():
                odds = getattr(outcome, 'odds', 0)
                if odds <= 1.0:
                    return None
                implied_probabilities.append(1.0 / odds)

            total_implied_prob = sum(implied_probabilities)
            arb_percentage = total_implied_prob * 100
            if total_implied_prob >= 1.0:
                return None  # No arbitrage opportunity

            profit_percentage = ((1.0 / total_implied_prob) - 1.0) * 100
            return round(arb_percentage, 4), round(profit_percentage, 4)
        except Exception as e:
            logger.debug(f"Error calculating arbitrage: {e}")
            return None

    def _passes_arbitrage_filters(self, arb_percentage: float, profit_percentage: float, filters: Optional[Dict]) -> bool:
        """Check if arbitrage passes filter criteria."""
        if not filters:
            return (arb_percentage < 100.0 and profit_percentage >= self.min_arb_percentage)

        min_arb_pct = filters.get('min_arb_percentage')
        if min_arb_pct is not None:
            if profit_percentage < min_arb_pct:
                return False
        else:
            if profit_percentage < self.min_arb_percentage:
                return False

        return arb_percentage < 100.0

    def _calculate_stakes(self, best_odds: Dict, bankroll: float) -> List[Dict]:
        """Calculate optimal stake distribution for arbitrage."""
        stakes = []
        try:
            total_inverse = sum(1.0 / getattr(outcome, 'odds', 1) for outcome in best_odds.values())
            for outcome_name, outcome in best_odds.items():
                odds = getattr(outcome, 'odds', 1)
                stake_proportion = (1.0 / odds) / total_inverse
                stake_amount = bankroll * stake_proportion
                potential_return = stake_amount * odds
                potential_profit = potential_return - bankroll
                stakes.append({
                    'outcome_name': outcome_name,
                    'bookmaker': getattr(outcome, 'bookmaker', 'Unknown'),
                    'stake_amount': round(stake_amount, 2),
                    'potential_profit': round(potential_profit, 2),
                    'url': getattr(outcome, 'url', None)
                })
        except Exception as e:
            logger.error(f"Error calculating stakes: {e}")
        return stakes

    def _calculate_freshness_score(self, outcomes) -> float:
        """Calculate freshness score based on data age."""
        if not outcomes:
            return 0.0
        now = datetime.now()
        total_age = sum((now - getattr(o, 'last_seen', now)).total_seconds() for o in outcomes)
        return round(total_age / len(outcomes), 2)
        
      # Site‐specific scraping functions

async def scrape_bet365_odds(url: str) -> Dict[str, Any]:
    """
    Scrape odds from Bet365 using the generic scrape_odds_from_page helper.
    """
    async def extract_bet365(page: Page) -> Dict[str, Any]:
        odds_list = []
        # wait for the main markets container
        await page.wait_for_selector('.gl-MarketGroup', timeout=30000)
        # gather each participant entry
        items = await page.query_selector_all('.gl-MarketGroup .gl-Participant_General')
        for item in items:
            try:
                name_el = await item.query_selector('.gl-ParticipantName')
                odds_el = await item.query_selector('.gl-ParticipantOdds')
                link_el = await item.query_selector('a')
                name = (await name_el.text_content()).strip() if name_el else 'Unknown'
                raw_odds = (await odds_el.text_content()).replace(',', '').strip() if odds_el else '0'
                odds_value = float(raw_odds)
                link = await link_el.get_attribute('href') if link_el else url
                odds_list.append({
                    'bookmaker': 'bet365',
                    'outcome_name': name,
                    'odds': odds_value,
                    'url': link
                })
            except Exception as e:
                logger.debug(f"Bet365 parse error: {e}")
        return {'bookmaker': 'bet365', 'odds': odds_list}

    return await scrape_odds_from_page(
        url=url,
        target_selector='.gl-MarketGroup',
        extraction_logic=extract_bet365,
        page_specific_config={
            'accept_cookies_selector': '#onetrust-accept-btn-handler'
        }
    )


async def scrape_pinnacle_odds(url: str) -> Dict[str, Any]:
    """
    Scrape odds from Pinnacle using the generic scrape_odds_from_page helper.
    """
    async def extract_pinnacle(page: Page) -> Dict[str, Any]:
        odds_list = []
        # wait for the markets grid
        await page.wait_for_selector('.market-row', timeout=30000)
        rows = await page.query_selector_all('.market-row')
        for row in rows:
            try:
                name = (await row.get_attribute('data-outcome-name')).strip()
                raw_odds = await row.query_selector('.odds-value')
                text_odds = (await raw_odds.text_content()).strip() if raw_odds else '0'
                odds_value = float(text_odds)
                odds_list.append({
                    'bookmaker': 'pinnacle',
                    'outcome_name': name,
                    'odds': odds_value,
                    'url': url
                })
            except Exception as e:
                logger.debug(f"Pinnacle parse error: {e}")
        return {'bookmaker': 'pinnacle', 'odds': odds_list}

    return await scrape_odds_from_page(
        url=url,
        target_selector='.market-row',
        extraction_logic=extract_pinnacle,
        page_specific_config={}
    )
    
    # from typing import List, Dict, Optional
from decimal import Decimal

# Map bookmaker names to scraper functions
BOOKMAKER_SCRAPERS = {
    'stake':     scrape_stake_odds,
    'mpstbet':   scrape_mpstbet_odds,
    'onexbet':   scrape_onexbet_odds,
    'parimatch': scrape_parimatch_odds,
    'leonbet':   scrape_leonbet_odds,
}

@app.get(
    "/arbitrage",
    response_model=List[ArbitrageOpportunity],
    summary="Detect arbitrage opportunities across configured bookmakers"
)
async def get_arbitrage(filters: Optional[ArbitrageFilters] = None):
    """
    Kick off all site-specific scrapers, build MatchedEvent objects,
    and run the ArbitrageEngine to return opportunities.
    """
    bookmaker_urls: Dict[str, str] = getattr(settings, "bookmaker_urls", {})
    if not bookmaker_urls:
        raise HTTPException(status_code=500, detail="No bookmaker_urls configured")

    # Launch scraper tasks in parallel
    tasks = []
    for name, url in bookmaker_urls.items():
        fn = BOOKMAKER_SCRAPERS.get(name)
        if fn:
            tasks.append(fn(url))
        else:
            logger.warning(f"No scraper function for bookmaker '{name}'")

    raw_results = await asyncio.gather(*tasks, return_exceptions=True)

    # Build MatchedEvent list
    matched_events: List[MatchedEvent] = []
    for result in raw_results:
        if isinstance(result, Exception):
            logger.error(f"Scraper exception: {result}")
            continue
        try:
            outcomes = [
                OutcomeData(
                    outcome_name=o["outcome_name"],
                    odds=Decimal(o["odds"]),
                    bookmaker=o["bookmaker"],
                    url=o.get("url")
                )
                for o in result.get("odds", [])
            ]
            matched_events.append(
                MatchedEvent(
                    event=result.get("meta", {}),
                    markets={"default": {"outcomes": outcomes}}
                )
            )
        except Exception as e:
            logger.error(f"Failed to build MatchedEvent: {e}")

    # Detect arbitrage opportunities
    engine = ArbitrageEngine()
    arb_list = engine.detect_arbitrages(
        matched_events,
        filters.dict() if filters else None
    )
    return arb_list


if __name__ == "__main__":
    uvicorn.run(
        "app.engine.arbitrage:app",
        host=settings.host,
        port=settings.port,
        log_level=getattr(settings, "log_level", "INFO").lower()
    )