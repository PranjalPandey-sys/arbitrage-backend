"""
Leon bookmaker scraper.
"""

import asyncio
from typing import List, Optional, Dict, Any
from datetime import datetime

from app.books.base import BaseScraper
from app.schema.models import BookmakerName, RawOddsData, ScrapingResult
from app.utils.logging import get_logger

logger = get_logger(__name__)


class LeonScraper(BaseScraper):
    """Scraper for Leon bookmaker."""
    
    def __init__(self):
        super().__init__(
            bookmaker_name=BookmakerName.LEON,
            base_url="https://leon.bet"
        )
    
    async def scrape_football_odds(self) -> List[RawOddsData]:
        """Scrape football odds from Leon."""
        odds_data = []
        
        try:
            if not self.page:
                logger.warning("Leon: Browser not initialized, skipping scraping")
                return odds_data
            
            # Navigate to football section
            football_url = f"{self.base_url}/en/betting/football"
            if not await self.navigate_with_retry(football_url):
                logger.error("Leon: Failed to navigate to football section")
                return odds_data
            
            await self.random_delay()
            
            # Wait for matches to load
            await self.page.wait_for_selector('[data-testid="match-card"]', timeout=10000)
            
            # Extract match data
            match_cards = await self.page.query_selector_all('[data-testid="match-card"]')
            
            for card in match_cards:
                try:
                    match_data = await self._extract_match_data(card)
                    if match_data:
                        odds_data.extend(match_data)
                except Exception as e:
                    logger.warning(f"Leon: Error processing match card: {e}")
                    continue
            
            logger.info(f"Leon: Successfully scraped {len(odds_data)} odds entries")
            
        except Exception as e:
            logger.error(f"Leon: Error scraping football odds: {e}")
        
        return odds_data
    
    async def _extract_match_data(self, match_card) -> List[RawOddsData]:
        """Extract odds data from a match card."""
        odds_data = []
        
        try:
            # Extract team names
            teams = await match_card.query_selector_all('.team-name')
            if len(teams) < 2:
                return odds_data
            
            home_team = await teams[0].inner_text()
            away_team = await teams[1].inner_text()
            event_name = f"{home_team} vs {away_team}"
            
            # Extract match time
            time_element = await match_card.query_selector('.match-time')
            start_time = None
            if time_element:
                time_text = await time_element.inner_text()
                start_time = await self.parse_time_string(time_text)
            
            # Extract league
            league_element = await match_card.query_selector('.league-name')
            league = await league_element.inner_text() if league_element else "Unknown"
            
            # Extract 1X2 odds
            odds_elements = await match_card.query_selector_all('.odds-button')
            
            if len(odds_elements) >= 3:
                outcomes = ["1", "X", "2"]
                outcome_names = [home_team, "Draw", away_team]
                
                for i, (outcome, outcome_name) in enumerate(zip(outcomes, outcome_names)):
                    if i < len(odds_elements):
                        odds_text = await odds_elements[i].inner_text()
                        odds_value = self.extract_odds_value(odds_text)
                        
                        if odds_value and self.is_valid_odds(odds_value):
                            odds_data.append(RawOddsData(
                                bookmaker=self.bookmaker_name,
                                event_name=event_name,
                                sport="Football",
                                league=league,
                                start_time=start_time,
                                market_name="Match Result",
                                line=None,
                                outcome_name=outcome_name,
                                odds=odds_value,
                                url=self.page.url,
                                scraped_at=datetime.now(),
                                is_live=False
                            ))
            
        except Exception as e:
            logger.warning(f"Leon: Error extracting match data: {e}")
        
        return odds_data
    
    async def scrape_basketball_odds(self) -> List[RawOddsData]:
        """Scrape basketball odds from Leon."""
        odds_data = []
        
        try:
            if not self.page:
                logger.warning("Leon: Browser not initialized, skipping basketball scraping")
                return odds_data
            
            # Navigate to basketball section
            basketball_url = f"{self.base_url}/en/betting/basketball"
            if not await self.navigate_with_retry(basketball_url):
                logger.error("Leon: Failed to navigate to basketball section")
                return odds_data
            
            await self.random_delay()
            
            # Wait for matches to load
            await self.page.wait_for_selector('[data-testid="match-card"]', timeout=10000)
            
            # Extract match data (similar logic to football)
            match_cards = await self.page.query_selector_all('[data-testid="match-card"]')
            
            for card in match_cards:
                try:
                    match_data = await self._extract_basketball_match_data(card)
                    if match_data:
                        odds_data.extend(match_data)
                except Exception as e:
                    logger.warning(f"Leon: Error processing basketball match: {e}")
                    continue
            
            logger.info(f"Leon: Successfully scraped {len(odds_data)} basketball odds")
            
        except Exception as e:
            logger.error(f"Leon: Error scraping basketball odds: {e}")
        
        return odds_data
    
    async def _extract_basketball_match_data(self, match_card) -> List[RawOddsData]:
        """Extract basketball odds data from a match card."""
        odds_data = []
        
        try:
            # Extract team names
            teams = await match_card.query_selector_all('.team-name')
            if len(teams) < 2:
                return odds_data
            
            home_team = await teams[0].inner_text()
            away_team = await teams[1].inner_text()
            event_name = f"{home_team} vs {away_team}"
            
            # Extract match time
            time_element = await match_card.query_selector('.match-time')
            start_time = None
            if time_element:
                time_text = await time_element.inner_text()
                start_time = await self.parse_time_string(time_text)
            
            # Extract league
            league_element = await match_card.query_selector('.league-name')
            league = await league_element.inner_text() if league_element else "Unknown"
            
            # Extract moneyline odds
            odds_elements = await match_card.query_selector_all('.odds-button')
            
            if len(odds_elements) >= 2:
                outcome_names = [home_team, away_team]
                
                for i, outcome_name in enumerate(outcome_names):
                    if i < len(odds_elements):
                        odds_text = await odds_elements[i].inner_text()
                        odds_value = self.extract_odds_value(odds_text)
                        
                        if odds_value and self.is_valid_odds(odds_value):
                            odds_data.append(RawOddsData(
                                bookmaker=self.bookmaker_name,
                                event_name=event_name,
                                sport="Basketball",
                                league=league,
                                start_time=start_time,
                                market_name="Moneyline",
                                line=None,
                                outcome_name=outcome_name,
                                odds=odds_value,
                                url=self.page.url,
                                scraped_at=datetime.now(),
                                is_live=False
                            ))
            
        except Exception as e:
            logger.warning(f"Leon: Error extracting basketball match data: {e}")
        
        return odds_data
    
    async def scrape_live_odds(self) -> List[RawOddsData]:
        """Scrape live odds from Leon."""
        odds_data = []
        
        try:
            if not self.page:
                logger.warning("Leon: Browser not initialized, skipping live scraping")
                return odds_data
            
            # Navigate to live section
            live_url = f"{self.base_url}/en/live"
            if not await self.navigate_with_retry(live_url):
                logger.error("Leon: Failed to navigate to live section")
                return odds_data
            
            await self.random_delay()
            
            # Wait for live matches to load
            await self.page.wait_for_selector('[data-testid="live-match"]', timeout=10000)
            
            # Extract live match data
            live_matches = await self.page.query_selector_all('[data-testid="live-match"]')
            
            for match in live_matches:
                try:
                    match_data = await self._extract_live_match_data(match)
                    if match_data:
                        odds_data.extend(match_data)
                except Exception as e:
                    logger.warning(f"Leon: Error processing live match: {e}")
                    continue
            
            logger.info(f"Leon: Successfully scraped {len(odds_data)} live odds")
            
        except Exception as e:
            logger.error(f"Leon: Error scraping live odds: {e}")
        
        return odds_data
    
    async def _extract_live_match_data(self, match_card) -> List[RawOddsData]:
        """Extract live odds data from a match card."""
        odds_data = []
        
        try:
            # Extract team names
            teams = await match_card.query_selector_all('.team-name')
            if len(teams) < 2:
                return odds_data
            
            home_team = await teams[0].inner_text()
            away_team = await teams[1].inner_text()
            event_name = f"{home_team} vs {away_team}"
            
            # Extract sport
            sport_element = await match_card.query_selector('.sport-icon')
            sport = "Football"  # Default
            if sport_element:
                sport_class = await sport_element.get_attribute('class')
                if 'basketball' in sport_class:
                    sport = "Basketball"
                elif 'tennis' in sport_class:
                    sport = "Tennis"
            
            # Extract league
            league_element = await match_card.query_selector('.league-name')
            league = await league_element.inner_text() if league_element else "Unknown"
            
            # Extract odds based on sport
            if sport == "Football":
                odds_elements = await match_card.query_selector_all('.odds-button')
                if len(odds_elements) >= 3:
                    outcome_names = [home_team, "Draw", away_team]
                    
                    for i, outcome_name in enumerate(outcome_names):
                        if i < len(odds_elements):
                            odds_text = await odds_elements[i].inner_text()
                            odds_value = self.extract_odds_value(odds_text)
                            
                            if odds_value and self.is_valid_odds(odds_value):
                                odds_data.append(RawOddsData(
                                    bookmaker=self.bookmaker_name,
                                    event_name=event_name,
                                    sport=sport,
                                    league=league,
                                    start_time=None,  # Live events
                                    market_name="Match Result",
                                    line=None,
                                    outcome_name=outcome_name,
                                    odds=odds_value,
                                    url=self.page.url,
                                    scraped_at=datetime.now(),
                                    is_live=True
                                ))
            else:
                # For other sports, extract moneyline
                odds_elements = await match_card.query_selector_all('.odds-button')
                if len(odds_elements) >= 2:
                    outcome_names = [home_team, away_team]
                    
                    for i, outcome_name in enumerate(outcome_names):
                        if i < len(odds_elements):
                            odds_text = await odds_elements[i].inner_text()
                            odds_value = self.extract_odds_value(odds_text)
                            
                            if odds_value and self.is_valid_odds(odds_value):
                                odds_data.append(RawOddsData(
                                    bookmaker=self.bookmaker_name,
                                    event_name=event_name,
                                    sport=sport,
                                    league=league,
                                    start_time=None,
                                    market_name="Moneyline",
                                    line=None,
                                    outcome_name=outcome_name,
                                    odds=odds_value,
                                    url=self.page.url,
                                    scraped_at=datetime.now(),
                                    is_live=True
                                ))
            
        except Exception as e:
            logger.warning(f"Leon: Error extracting live match data: {e}")
        
        return odds_data
