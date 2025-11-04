"""
Mock connector system for generating synthetic odds data.
File: app/connectors/mock_connector.py
"""

import time
import random
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any
from app.schema.models import RawOddsData, BookmakerName

logger = logging.getLogger(__name__)


class MockConnector:
    """Base mock connector that generates realistic synthetic odds."""
    
    def __init__(self, bookmaker: BookmakerName):
        self.bookmaker = bookmaker
        self.is_running = False
        
        # Sample teams for different sports
        self.football_teams = [
            ("Manchester United", "Liverpool"),
            ("Real Madrid", "Barcelona"),
            ("Bayern München", "Borussia Dortmund"),
            ("PSG", "Marseille"),
            ("Juventus", "AC Milan"),
            ("Arsenal", "Chelsea"),
            ("Atletico Madrid", "Valencia"),
            ("Inter", "Napoli"),
        ]
        
        self.basketball_teams = [
            ("Lakers", "Warriors"),
            ("Celtics", "Heat"),
            ("Bucks", "76ers"),
            ("Nuggets", "Suns"),
            ("Mavericks", "Clippers"),
        ]
        
        self.esports_teams = [
            ("NAVI", "FaZe"),
            ("Liquid", "G2"),
            ("Astralis", "Vitality"),
            ("Cloud9", "NiP"),
        ]
        
        self.leagues = {
            "football": ["Premier League", "La Liga", "Bundesliga", "Serie A", "Ligue 1"],
            "basketball": ["NBA", "EuroLeague"],
            "esports": ["CS:GO Major", "IEM", "BLAST Premier"]
        }
    
    def generate_football_odds(self) -> List[RawOddsData]:
        """Generate realistic football odds."""
        odds_data = []
        
        for home_team, away_team in random.sample(self.football_teams, k=random.randint(3, 6)):
            event_name = f"{home_team} vs {away_team}"
            league = random.choice(self.leagues["football"])
            
            # Generate realistic start time (1-48 hours in future)
            hours_ahead = random.randint(1, 48)
            start_time = datetime.now() + timedelta(hours=hours_ahead)
            
            # Generate 1X2 odds (must sum to > 100% for bookmaker margin)
            home_odds = round(random.uniform(1.50, 4.50), 2)
            draw_odds = round(random.uniform(2.80, 4.20), 2)
            away_odds = round(random.uniform(1.50, 4.50), 2)
            
            # Adjust to ensure bookmaker margin (around 105-110%)
            total_implied = (1/home_odds + 1/draw_odds + 1/away_odds)
            if total_implied < 1.05:
                margin_factor = 1.07 / total_implied
                home_odds = round(home_odds / margin_factor, 2)
                draw_odds = round(draw_odds / margin_factor, 2)
                away_odds = round(away_odds / margin_factor, 2)
            
            # Add 1X2 market
            outcomes = [
                (home_team, home_odds),
                ("Draw", draw_odds),
                (away_team, away_odds)
            ]
            
            for outcome_name, odds in outcomes:
                odds_data.append(RawOddsData(
                    event_name=event_name,
                    start_time=start_time,
                    sport="football",
                    league=league,
                    market_name="Match Result",
                    line=None,
                    outcome_name=outcome_name,
                    odds=odds,
                    bookmaker=self.bookmaker,
                    url=f"https://{self.bookmaker.value}.com/mock/{event_name.replace(' ', '-')}",
                    scraped_at=datetime.now(),
                    is_live=False
                ))
            
            # Add Over/Under market
            line = random.choice([2.5, 3.5])
            over_odds = round(random.uniform(1.70, 2.30), 2)
            under_odds = round(random.uniform(1.70, 2.30), 2)
            
            for outcome_name, odds in [("Over", over_odds), ("Under", under_odds)]:
                odds_data.append(RawOddsData(
                    event_name=event_name,
                    start_time=start_time,
                    sport="football",
                    league=league,
                    market_name="Total Goals",
                    line=line,
                    outcome_name=outcome_name,
                    odds=odds,
                    bookmaker=self.bookmaker,
                    url=f"https://{self.bookmaker.value}.com/mock/{event_name.replace(' ', '-')}",
                    scraped_at=datetime.now(),
                    is_live=False
                ))
        
        return odds_data
    
    def generate_basketball_odds(self) -> List[RawOddsData]:
        """Generate realistic basketball odds."""
        odds_data = []
        
        for home_team, away_team in random.sample(self.basketball_teams, k=random.randint(2, 4)):
            event_name = f"{home_team} vs {away_team}"
            league = random.choice(self.leagues["basketball"])
            
            hours_ahead = random.randint(1, 24)
            start_time = datetime.now() + timedelta(hours=hours_ahead)
            
            # Generate moneyline odds
            home_odds = round(random.uniform(1.50, 3.00), 2)
            away_odds = round(random.uniform(1.50, 3.00), 2)
            
            # Adjust for margin
            total_implied = (1/home_odds + 1/away_odds)
            if total_implied < 1.04:
                margin_factor = 1.05 / total_implied
                home_odds = round(home_odds / margin_factor, 2)
                away_odds = round(away_odds / margin_factor, 2)
            
            for outcome_name, odds in [(home_team, home_odds), (away_team, away_odds)]:
                odds_data.append(RawOddsData(
                    event_name=event_name,
                    start_time=start_time,
                    sport="basketball",
                    league=league,
                    market_name="Moneyline",
                    line=None,
                    outcome_name=outcome_name,
                    odds=odds,
                    bookmaker=self.bookmaker,
                    url=f"https://{self.bookmaker.value}.com/mock/{event_name.replace(' ', '-')}",
                    scraped_at=datetime.now(),
                    is_live=False
                ))
            
            # Add totals market
            line = random.choice([205.5, 215.5, 225.5])
            over_odds = round(random.uniform(1.85, 2.05), 2)
            under_odds = round(random.uniform(1.85, 2.05), 2)
            
            for outcome_name, odds in [("Over", over_odds), ("Under", under_odds)]:
                odds_data.append(RawOddsData(
                    event_name=event_name,
                    start_time=start_time,
                    sport="basketball",
                    league=league,
                    market_name="Total Points",
                    line=line,
                    outcome_name=outcome_name,
                    odds=odds,
                    bookmaker=self.bookmaker,
                    url=f"https://{self.bookmaker.value}.com/mock/{event_name.replace(' ', '-')}",
                    scraped_at=datetime.now(),
                    is_live=False
                ))
        
        return odds_data
    
    def generate_esports_odds(self) -> List[RawOddsData]:
        """Generate realistic esports odds."""
        odds_data = []
        
        for team1, team2 in random.sample(self.esports_teams, k=random.randint(2, 3)):
            event_name = f"{team1} vs {team2}"
            league = random.choice(self.leagues["esports"])
            
            hours_ahead = random.randint(1, 12)
            start_time = datetime.now() + timedelta(hours=hours_ahead)
            
            # Generate match winner odds
            team1_odds = round(random.uniform(1.40, 3.50), 2)
            team2_odds = round(random.uniform(1.40, 3.50), 2)
            
            # Adjust for margin
            total_implied = (1/team1_odds + 1/team2_odds)
            if total_implied < 1.04:
                margin_factor = 1.05 / total_implied
                team1_odds = round(team1_odds / margin_factor, 2)
                team2_odds = round(team2_odds / margin_factor, 2)
            
            for outcome_name, odds in [(team1, team1_odds), (team2, team2_odds)]:
                odds_data.append(RawOddsData(
                    event_name=event_name,
                    start_time=start_time,
                    sport="csgo",
                    league=league,
                    market_name="Match Winner",
                    line=None,
                    outcome_name=outcome_name,
                    odds=odds,
                    bookmaker=self.bookmaker,
                    url=f"https://{self.bookmaker.value}.com/mock/{event_name.replace(' ', '-')}",
                    scraped_at=datetime.now(),
                    is_live=False
                ))
            
            # Add map handicap
            line = random.choice([-1.5, 1.5])
            over_odds = round(random.uniform(1.75, 2.20), 2)
            under_odds = round(random.uniform(1.75, 2.20), 2)
            
            for outcome_name, odds in [(f"{team1} {line:+.1f}", over_odds), 
                                       (f"{team2} {-line:+.1f}", under_odds)]:
                odds_data.append(RawOddsData(
                    event_name=event_name,
                    start_time=start_time,
                    sport="csgo",
                    league=league,
                    market_name="Map Handicap",
                    line=line,
                    outcome_name=outcome_name,
                    odds=odds,
                    bookmaker=self.bookmaker,
                    url=f"https://{self.bookmaker.value}.com/mock/{event_name.replace(' ', '-')}",
                    scraped_at=datetime.now(),
                    is_live=False
                ))
        
        return odds_data
    
    def generate_all_odds(self) -> List[RawOddsData]:
        """Generate odds for all sports."""
        all_odds = []
        
        all_odds.extend(self.generate_football_odds())
        all_odds.extend(self.generate_basketball_odds())
        all_odds.extend(self.generate_esports_odds())
        
        logger.info(f"[MOCK] {self.bookmaker.value}: Generated {len(all_odds)} synthetic odds")
        return all_odds


def create_mock_variations() -> Dict[BookmakerName, List[RawOddsData]]:
    """
    Create slightly varied odds across different mock bookmakers 
    to simulate real arbitrage opportunities.
    """
    base_connector = MockConnector(BookmakerName.MOSTBET)
    base_odds = base_connector.generate_all_odds()
    
    variations = {}
    bookmakers = [BookmakerName.MOSTBET, BookmakerName.STAKE, BookmakerName.LEON, 
                  BookmakerName.PARIMATCH, BookmakerName.ONEXBET]
    
    for bookmaker in bookmakers:
        connector = MockConnector(bookmaker)
        bookmaker_odds = []
        
        # Use same events but vary odds slightly
        for base_odd in base_odds:
            # Vary odds by ±3-8% randomly
            variation_factor = random.uniform(0.95, 1.08)
            varied_odds = round(base_odd.odds * variation_factor, 2)
            
            # Ensure odds stay within valid range
            varied_odds = max(1.01, min(50.0, varied_odds))
            
            bookmaker_odds.append(RawOddsData(
                event_name=base_odd.event_name,
                start_time=base_odd.start_time,
                sport=base_odd.sport,
                league=base_odd.league,
                market_name=base_odd.market_name,
                line=base_odd.line,
                outcome_name=base_odd.outcome_name,
                odds=varied_odds,
                bookmaker=bookmaker,
                url=f"https://{bookmaker.value}.com/mock/{base_odd.event_name.replace(' ', '-')}",
                scraped_at=datetime.now(),
                is_live=base_odd.is_live
            ))
        
        variations[bookmaker] = bookmaker_odds
    
    return variations
