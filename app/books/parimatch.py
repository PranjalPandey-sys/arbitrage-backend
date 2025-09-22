"""
Parimatch bookmaker scraper.
"""

import asyncio
from typing import List, Optional, Dict, Any
from datetime import datetime

from app.books.base import BaseScraper
from app.schema.models import BookmakerName, RawOddsData, ScrapingResult
from app.utils.logging import get_logger

logger = get_logger(__name__)


class ParimatchScraper(BaseScraper):
    """Scraper for Parimatch bookmaker."""
    
    def __init__(self):
        super().__init__(
            bookmaker_name=BookmakerName.PARIMATCH,
            base_url="https://parimatch.com"
        )
    
    async def scrape_football_odds(self) -> List[RawOddsData]:
        """Scrape football odds from Parimatch."""
        odds_data = []
        
        try:
            if not self.page:
                logger.warning("Parimatch: Browser not initialized, skipping scraping")
                return odds_data
            
            # Navigate to football section
            football_url = f"{self.base_url}/en/football"
            if not await self.navigate_with_retry(football_url):
                logger.error("Parimatch: Failed to navigate to football section")
                return odds_data
            
            await self.random_delay()
            
            # Wait for matches to load
            await self.page.wait_for_selector('.match-row', timeout=10000)
            
            # Extract match data
            match_rows = await self.page.query_selector_all('.match-row')
            
            for row in match_rows:
                try:
                    match_data = await self._extract_match_data(row)
                    if match_data:
                        odds_data.extend(match_data)
                except Exception as e:
                    logger.warning(f"Parimatch: Error processing match row: {e}")
                    continue
            
            logger.info(f"Parimatch: Successfully scraped {len(odds_data)} odds entries")
            
        except Exception as e:
            logger.error(f"Parimatch: Error scraping football odds: {e}")
        
        return odds_data
    
    async def _extract_match_data(self, match_row) -> List[RawOddsData]:
        """Extract odds data from a match row."""
        odds_data = []
        
        try:
            # Extract team names
            teams_element = await match_row.query_selector('.teams')
            if not teams_element:
                return odds_data
            
            teams_text = await teams_element.inner_text()
            if ' - ' in teams_text:
                home_team, away_team = teams_text.split(' - ', 1)
            else:
                return odds_data
            
            event_name = f"{home_team.strip()} vs {away_team.strip()}"
            
            # Extract match time
            time_element = await match_row.query_selector('.time')
            start_time = None
            if time_element:
                time_text = await time_element.inner_text()
                start_time = await self.parse_time_string(time_text)
            
            # Extract league
            league_element = await match_row.query_selector('.league')
            league = await league_element.inner_text() if league_element else "Unknown"
            
            # Extract 1X2 odds
            odds_elements = await match_row.query_selector_all('.odd-cell')
            
            if len(odds_elements) >= 3:
                outcome_names = [home_team.strip(), "Draw", away_team.strip()]
                
                for i, outcome_name in enumerate(outcome_names):
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
            logger.warning(f"Parimatch: Error extracting match data: {e}")
        
        return odds_data
    
    async def scrape_basketball_odds(self) -> List[RawOddsData]:
        """Scrape basketball odds from Parimatch."""
        odds_data = []
        
        try:
            if not self.page:
                logger.warning("Parimatch: Browser not initialized, skipping basketball scraping")
                return odds_data
            
            # Navigate to basketball section
            basketball_url = f"{self.base_url}/en/basketball"
            if not await self.navigate_with_retry(basketball_url):
                logger.error("Parimatch: Failed to navigate to basketball section")
                return odds_data
            
            await self.random_delay()
            
            # Wait for matches to load
            await self.page.wait_for_selector('.match-row', timeout=10000)
            
            # Extract match data
            match_rows = await self.page.query_selector_all('.match-row')
            
            for row in match_rows:
                try:
                    match_data = await self._extract_basketball_match_data(row)
                    if match_data:
                        odds_data.extend(match_data)
                except Exception as e:
                    logger.warning(f"Parimatch: Error processing basketball match: {e}")
                    continue
            
            logger.info(f"Parimatch: Successfully scraped {len(odds_data)} basketball odds")
            
        except Exception as e:
            logger.error(f"Parimatch: Error scraping basketball odds: {e}")
        
        return odds_data
    
    async def _extract_basketball_match_data(self, match_row) -> List[RawOddsData]:
        """Extract basketball odds data from a match row."""
        odds_data = []
        
        try:
            # Extract team names
            teams_element = await match_row.query_selector('.teams')
            if not teams_element:
                return odds_data
            
            teams_text = await teams_element.inner_text()
            if ' - ' in teams_text:
                home_team, away_team = teams_text.split(' - ', 1)
            else:
                return odds_data
            
            event_name = f"{home_team.strip()} vs {away_team.strip()}"
            
            # Extract match time
            time_element = await match_row.query_selector('.time')
            start_time = None
            if time_element:
                time_text = await time_element.inner_text()
                start_time = await self.parse_time_string(time_text)
            
            # Extract league
            league_element = await match_row.query_selector('.league')
            league = await league_element.inner_text() if league_element else "Unknown"
            
            # Extract moneyline odds (W1, W2)
            odds_elements = await match_row.query_selector_all('.odd-cell')
            
            if len(odds_elements) >= 2:
                outcome_names = [home_team.strip(), away_team.strip()]
                
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
            logger.warning(f"Parimatch: Error extracting basketball match data: {e}")
        
        return odds_data
    
    async def scrape_live_odds(self) -> List[RawOddsData]:
        """Scrape live odds from Parimatch."""
        odds_data = []
        
        try:
            if not self.page:
                logger.warning("Parimatch: Browser not initialized, skipping live scraping")
                return odds_data
            
            # Navigate to live section
            live_url = f"{self.base_url}/en/live"
            if not await self.navigate_with_retry(live_url):
                logger.error("Parimatch: Failed to navigate to live section")
                return odds_data
            
            await self.random_delay()
            
            # Wait for live matches to load
            await self.page.wait_for_selector('.live-match', timeout=10000)
            
            # Extract live match data
            live_matches = await self.page.query_selector_all('.live-match')
            
            for match in live_matches:
                try:
                    match_data = await self._extract_live_match_data(match)
                    if match_data:
                        odds_data.extend(match_data)
                except Exception as e:
                    logger.warning(f"Parimatch: Error processing live match: {e}")
                    continue
            
            logger.info(f"Parimatch: Successfully scraped {len(odds_data)} live odds")
            
        except Exception as e:
            logger.error(f"Parimatch: Error scraping live odds: {e}")
        
        return odds_data
    
    async def _extract_live_match_data(self, match_element) -> List[RawOddsData]:
        """Extract live odds data from a match element."""
        odds_data = []
        
        try:
            # Extract team names
            teams_element = await match_element.query_selector('.teams')
            if not teams_element:
                return odds_data
            
            teams_text = await teams_element.inner_text()
            if ' - ' in teams_text:
                home_team, away_team = teams_text.split(' - ', 1)
            else:
                return odds_data
            
            event_name = f"{home_team.strip()} vs {away_team.strip()}"
            
            # Extract sport
            sport_element = await match_element.query_selector('.sport-name')
            sport = "Football"  # Default
            if sport_element:
                sport_text = await sport_element.inner_text()
                if 'Basketball' in sport_text or 'NBA' in sport_text:
                    sport = "Basketball"
                elif 'Tennis' in sport_text:
                    sport = "Tennis"
            
            # Extract league
            league_element = await match_element.query_selector('.league')
            league = await league_element.inner_text() if league_element else "Unknown"
            
            # Extract odds based on sport
            odds_elements = await match_element.query_selector_all('.odd-cell')
            
            if sport == "Football" and len(odds_elements) >= 3:
                outcome_names = [home_team.strip(), "Draw", away_team.strip()]
                market_name = "Match Result"
            elif len(odds_elements) >= 2:
                outcome_names = [home_team.strip(), away_team.strip()]
                market_name = "Moneyline"
            else:
                return odds_data
            
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
                            market_name=market_name,
                            line=None,
                            outcome_name=outcome_name,
                            odds=odds_value,
                            url=self.page.url,
                            scraped_at=datetime.now(),
                            is_live=True
                        ))
            
        except Exception as e:
            logger.warning(f"Parimatch: Error extracting live match data: {e}")
        
        return odds_data