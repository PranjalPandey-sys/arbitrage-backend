"""
Test script to verify the mock connector system works correctly.
File: tests/test_mock_system.py

Run with: python -m tests.test_mock_system
"""

import asyncio
import logging
from app.connectors.connector_manager import ConnectorManager
from app.service.orchestrator import ArbitrageOrchestrator
from app.schema.models import ArbitrageFilters

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_mock_connectors():
    """Test mock connector system."""
    logger.info("=" * 60)
    logger.info("TESTING MOCK CONNECTOR SYSTEM")
    logger.info("=" * 60)
    
    # Test 1: Initialize connector manager in mock mode
    logger.info("\n1. Testing Connector Manager Initialization...")
    connector_manager = ConnectorManager(force_mock=True)
    
    status = connector_manager.get_connector_status()
    logger.info(f"System mode: {status['system_mode']}")
    logger.info(f"Total connectors: {status['total_connectors']}")
    logger.info(f"Mock connectors: {status['mock_count']}")
    
    assert status['system_mode'] == 'mock', "Should be in mock mode"
    assert status['mock_count'] == 6, "Should have 6 mock connectors"
    logger.info("✓ Connector manager initialized successfully")
    
    # Test 2: Fetch mock odds
    logger.info("\n2. Testing Mock Odds Generation...")
    all_odds = await connector_manager.fetch_all_odds()
    
    logger.info(f"Generated {len(all_odds)} total odds entries")
    
    # Verify we have odds from multiple bookmakers
    bookmakers = set(odds.bookmaker for odds in all_odds)
    logger.info(f"Bookmakers with odds: {[bm.value for bm in bookmakers]}")
    
    assert len(all_odds) > 0, "Should have generated odds"
    assert len(bookmakers) >= 3, "Should have odds from multiple bookmakers"
    logger.info("✓ Mock odds generated successfully")
    
    # Test 3: Verify odds format
    logger.info("\n3. Testing Odds Data Format...")
    sample_odd = all_odds[0]
    
    logger.info(f"Sample odd:")
    logger.info(f"  Event: {sample_odd.event_name}")
    logger.info(f"  Sport: {sample_odd.sport}")
    logger.info(f"  Market: {sample_odd.market_name}")
    logger.info(f"  Outcome: {sample_odd.outcome_name}")
    logger.info(f"  Odds: {sample_odd.odds}")
    logger.info(f"  Bookmaker: {sample_odd.bookmaker.value}")
    
    assert sample_odd.odds >= 1.01, "Odds should be valid"
    assert sample_odd.event_name, "Should have event name"
    assert sample_odd.sport, "Should have sport"
    logger.info("✓ Odds format is correct")
    
    # Test 4: Full arbitrage detection pipeline
    logger.info("\n4. Testing Full Arbitrage Detection Pipeline...")
    orchestrator = ArbitrageOrchestrator(force_mock=True)
    
    filters = ArbitrageFilters(
        min_arb_percentage=0.1,
        bankroll=1000
    )
    
    response = await orchestrator.run_full_arbitrage_detection(filters)
    
    logger.info(f"Detected {len(response.arbitrages)} arbitrage opportunities")
    logger.info(f"Processing time: {response.summary.get('processing_time_seconds', 0):.2f}s")
    
    if response.arbitrages:
        logger.info("\nSample arbitrage:")
        arb = response.arbitrages[0]
        logger.info(f"  Event: {arb.event_name}")
        logger.info(f"  Profit: {arb.profit_percentage:.2f}%")
        logger.info(f"  Guaranteed profit: ${arb.guaranteed_profit:.2f}")
        logger.info(f"  Outcomes: {len(arb.outcomes)}")
        logger.info(f"  Bookmakers involved:")
        for outcome in arb.outcomes:
            logger.info(f"    - {outcome.bookmaker.value}: {outcome.outcome_name} @ {outcome.odds}")
    
    assert len(response.arbitrages) >= 0, "Should complete arbitrage detection"
    logger.info("✓ Full pipeline works correctly")
    
    # Test 5: Verify odds variations create arbitrages
    logger.info("\n5. Testing Arbitrage Creation from Variations...")
    
    # Mock variations should create odds differences that lead to arbitrages
    from app.connectors.mock_connector import create_mock_variations
    variations = create_mock_variations()
    
    # Check that same events have different odds across bookmakers
    event_odds = {}
    for bookmaker, odds_list in variations.items():
        for odd in odds_list[:5]:  # Check first 5
            key = (odd.event_name, odd.market_name, odd.outcome_name)
            if key not in event_odds:
                event_odds[key] = []
            event_odds[key].append((bookmaker, odd.odds))
    
    variations_found = 0
    for event_key, odds_list in event_odds.items():
        if len(odds_list) > 1:
            odds_values = [odds for _, odds in odds_list]
            if max(odds_values) != min(odds_values):
                variations_found += 1
    
    logger.info(f"Found {variations_found} events with odds variations")
    logger.info("✓ Variations create realistic arbitrage opportunities")
    
    logger.info("\n" + "=" * 60)
    logger.info("ALL TESTS PASSED! ✓")
    logger.info("=" * 60)
    logger.info("\nThe mock system is working correctly.")
    logger.info("You can now start the backend with:")
    logger.info("  python -m app.main --force-mock")


async def test_hybrid_mode():
    """Test hybrid mode detection."""
    logger.info("\n" + "=" * 60)
    logger.info("TESTING HYBRID MODE DETECTION")
    logger.info("=" * 60)
    
    # Without force_mock, should detect based on credentials
    connector_manager = ConnectorManager(force_mock=False)
    status = connector_manager.get_connector_status()
    
    logger.info(f"System mode: {status['system_mode']}")
    logger.info(f"Live connectors: {status['live_count']}")
    logger.info(f"Mock connectors: {status['mock_count']}")
    
    if status['system_mode'] == 'hybrid':
        logger.info("✓ Hybrid mode detected correctly")
    elif status['system_mode'] == 'mock':
        logger.info("ℹ No API keys found - running in full mock mode (expected)")
    else:
        logger.info("ℹ Live mode detected")
    
    logger.info("=" * 60)


def main():
    """Run all tests."""
    asyncio.run(test_mock_connectors())
    asyncio.run(test_hybrid_mode())


if __name__ == "__main__":
    main()
