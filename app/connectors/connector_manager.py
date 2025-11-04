"""
Connector manager that handles both mock and live connectors.
File: app/connectors/connector_manager.py
"""

import os
import logging
import yaml
from pathlib import Path
from typing import Dict, List, Optional, Any
from enum import Enum

from app.schema.models import BookmakerName, RawOddsData
from app.connectors.mock_connector import MockConnector, create_mock_variations

logger = logging.getLogger(__name__)


class ConnectorMode(str, Enum):
    MOCK = "mock"
    LIVE = "live"
    HYBRID = "hybrid"  # Some live, some mock


class ConnectorConfig:
    """Configuration for connector system."""
    
    def __init__(self, force_mock: bool = False):
        self.force_mock = force_mock
        self.credentials = self._load_credentials()
        self.connector_modes = self._determine_modes()
    
    def _load_credentials(self) -> Dict[str, Any]:
        """Load credentials from YAML file or environment variables."""
        credentials = {}
        
        # Try to load from YAML file
        config_file = Path("config/credentials.yaml")
        if config_file.exists():
            try:
                with open(config_file, 'r') as f:
                    yaml_creds = yaml.safe_load(f)
                    if yaml_creds:
                        credentials.update(yaml_creds.get('bookmakers', {}))
                logger.info(f"Loaded credentials from {config_file}")
            except Exception as e:
                logger.warning(f"Failed to load credentials from YAML: {e}")
        
        # Override with environment variables
        env_mappings = {
            'BOOKIE_1XBET_KEY': ('1xbet', 'api_key'),
            'BOOKIE_1XBET_SECRET': ('1xbet', 'api_secret'),
            'BOOKIE_PARIMATCH_KEY': ('parimatch', 'api_key'),
            'BOOKIE_PARIMATCH_SECRET': ('parimatch', 'api_secret'),
            'BOOKIE_MOSTBET_KEY': ('mostbet', 'api_key'),
            'BOOKIE_MOSTBET_SECRET': ('mostbet', 'api_secret'),
            'BOOKIE_STAKE_KEY': ('stake', 'api_key'),
            'BOOKIE_STAKE_SECRET': ('stake', 'api_secret'),
            'BOOKIE_LEON_KEY': ('leon', 'api_key'),
            'BOOKIE_LEON_SECRET': ('leon', 'api_secret'),
            'BOOKIE_1WIN_KEY': ('1win', 'api_key'),
            'BOOKIE_1WIN_SECRET': ('1win', 'api_secret'),
        }
        
        for env_var, (bookmaker, cred_type) in env_mappings.items():
            value = os.getenv(env_var)
            if value:
                if bookmaker not in credentials:
                    credentials[bookmaker] = {}
                credentials[bookmaker][cred_type] = value
        
        return credentials
    
    def _determine_modes(self) -> Dict[BookmakerName, ConnectorMode]:
        """Determine which connectors should run in mock vs live mode."""
        modes = {}
        
        # Map bookmaker names to enum
        bookmaker_mapping = {
            '1xbet': BookmakerName.ONEXBET,
            'parimatch': BookmakerName.PARIMATCH,
            'mostbet': BookmakerName.MOSTBET,
            'stake': BookmakerName.STAKE,
            'leon': BookmakerName.LEON,
            '1win': BookmakerName.ONEWIN,
        }
        
        # Check each bookmaker
        for bookie_name, bookie_enum in bookmaker_mapping.items():
            if self.force_mock:
                modes[bookie_enum] = ConnectorMode.MOCK
            else:
                # Check if credentials exist
                bookie_creds = self.credentials.get(bookie_name, {})
                has_key = 'api_key' in bookie_creds and bookie_creds['api_key']
                
                if has_key:
                    modes[bookie_enum] = ConnectorMode.LIVE
                else:
                    modes[bookie_enum] = ConnectorMode.MOCK
        
        return modes
    
    def get_system_mode(self) -> ConnectorMode:
        """Get overall system mode."""
        if self.force_mock:
            return ConnectorMode.MOCK
        
        live_count = sum(1 for mode in self.connector_modes.values() 
                        if mode == ConnectorMode.LIVE)
        mock_count = sum(1 for mode in self.connector_modes.values() 
                        if mode == ConnectorMode.MOCK)
        
        if live_count == 0:
            return ConnectorMode.MOCK
        elif mock_count == 0:
            return ConnectorMode.LIVE
        else:
            return ConnectorMode.HYBRID
    
    def log_startup_info(self):
        """Log connector configuration at startup."""
        system_mode = self.get_system_mode()
        
        logger.info("=" * 60)
        logger.info(f"ARBITRAGE SCANNER - {system_mode.value.upper()} MODE")
        logger.info("=" * 60)
        
        if self.force_mock:
            logger.info("🔸 Force mock mode enabled via --force-mock flag")
        
        logger.info(f"\nSystem Mode: {system_mode.value.upper()}")
        logger.info("\nConnector Status:")
        
        for bookmaker, mode in self.connector_modes.items():
            icon = "🟢" if mode == ConnectorMode.LIVE else "🔴"
            logger.info(f"  {icon} {bookmaker.value:12s} - {mode.value.upper()}")
        
        live_count = sum(1 for mode in self.connector_modes.values() 
                        if mode == ConnectorMode.LIVE)
        mock_count = sum(1 for mode in self.connector_modes.values() 
                        if mode == ConnectorMode.MOCK)
        
        logger.info(f"\nSummary: {live_count} live, {mock_count} mock")
        
        if mock_count > 0:
            logger.info("\n⚠️  MOCK MODE: Synthetic odds are being generated")
            logger.info("   To enable live mode, add API keys to config/credentials.yaml")
        
        logger.info("=" * 60)


class ConnectorManager:
    """Manages both mock and live connectors."""
    
    def __init__(self, force_mock: bool = False):
        self.config = ConnectorConfig(force_mock=force_mock)
        self.mock_connectors: Dict[BookmakerName, MockConnector] = {}
        self.live_connectors: Dict[BookmakerName, Any] = {}
        
        self._initialize_connectors()
        self.config.log_startup_info()
    
    def _initialize_connectors(self):
        """Initialize all connectors based on configuration."""
        for bookmaker, mode in self.config.connector_modes.items():
            if mode == ConnectorMode.MOCK:
                self.mock_connectors[bookmaker] = MockConnector(bookmaker)
                logger.debug(f"Initialized mock connector for {bookmaker.value}")
            else:
                # Initialize live connector (placeholder - implement as needed)
                logger.info(f"Live connector for {bookmaker.value} would initialize here")
                # For now, fall back to mock
                self.mock_connectors[bookmaker] = MockConnector(bookmaker)
                logger.warning(f"Live API not implemented, using mock for {bookmaker.value}")
    
    async def fetch_all_odds(self) -> List[RawOddsData]:
        """Fetch odds from all connectors (mock or live)."""
        all_odds = []
        
        # Fetch from mock connectors
        if self.mock_connectors:
            # Use variation generator for realistic arbitrage opportunities
            mock_variations = create_mock_variations()
            
            for bookmaker, odds_list in mock_variations.items():
                if bookmaker in self.mock_connectors:
                    all_odds.extend(odds_list)
                    logger.debug(f"[MOCK] {bookmaker.value}: {len(odds_list)} odds")
        
        # Fetch from live connectors (when implemented)
        for bookmaker, connector in self.live_connectors.items():
            try:
                # live_odds = await connector.fetch_odds()
                # all_odds.extend(live_odds)
                logger.debug(f"[LIVE] {bookmaker.value}: Would fetch real odds here")
            except Exception as e:
                logger.error(f"[LIVE] {bookmaker.value}: Failed to fetch odds: {e}")
        
        logger.info(f"Fetched total of {len(all_odds)} odds from {len(self.mock_connectors) + len(self.live_connectors)} connectors")
        return all_odds
    
    def get_connector_status(self) -> Dict[str, Any]:
        """Get status of all connectors."""
        return {
            "system_mode": self.config.get_system_mode().value,
            "force_mock": self.config.force_mock,
            "connectors": {
                bookmaker.value: {
                    "mode": mode.value,
                    "status": "active"
                }
                for bookmaker, mode in self.config.connector_modes.items()
            },
            "total_connectors": len(self.config.connector_modes),
            "live_count": sum(1 for mode in self.config.connector_modes.values() 
                            if mode == ConnectorMode.LIVE),
            "mock_count": sum(1 for mode in self.config.connector_modes.values() 
                            if mode == ConnectorMode.MOCK)
        }
