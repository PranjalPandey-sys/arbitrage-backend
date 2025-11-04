# Sports Arbitrage Detection API

A FastAPI-based backend system for detecting arbitrage opportunities across multiple sports betting platforms. **Features a dual-mode system: mock mode for testing without API keys, and live mode for real betting data.**

## 🚀 Quick Start

### Run in Mock Mode (No API Keys Required)

Perfect for testing and development:

```bash
# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium

# Run in mock mode (generates synthetic odds)
python -m app.main

# Or with custom settings
python -m app.main --host 0.0.0.0 --port 8000
```

**That's it!** The backend will automatically generate realistic synthetic odds data and detect arbitrage opportunities.

### Run in Live Mode (With API Keys)

To use real bookmaker data:

1. **Copy the credentials template:**
   ```bash
   cp config/credentials.template.yaml config/credentials.yaml
   ```

2. **Add your API keys** to `config/credentials.yaml`:
   ```yaml
   bookmakers:
     mostbet:
       api_key: "your-mostbet-api-key"
       api_secret: "your-mostbet-secret"
       enabled: true
     
     stake:
       api_key: "your-stake-api-key"
       enabled: true
   ```

3. **Start the server:**
   ```bash
   python -m app.main
   ```

The system will **automatically detect which bookmakers have API keys** and use live data for those, while falling back to mock data for others.

## 🎯 Features

### Dual-Mode Connector System

- **Mock Mode (Default)**: Generates realistic synthetic odds without API keys
  - Perfect for development and testing
  - Simulates multiple bookmakers with varied odds
  - Creates realistic arbitrage opportunities
  - No external dependencies

- **Live Mode**: Fetches real odds from bookmaker APIs
  - Automatically enabled when API keys are present
  - Supports multiple bookmaker APIs
  - Falls back to mock for unavailable bookmakers

- **Hybrid Mode**: Mix of mock and live data
  - Use real data from some bookmakers
  - Mock data for others
  - Seamless integration

### Multi-Bookmaker Support

Currently supports:
- ✅ **Mostbet** (mock + live ready)
- ✅ **Stake** (mock + live ready)
- ✅ **Leon** (mock mode)
- ✅ **Parimatch** (mock mode)
- ✅ **1xBet** (mock mode)
- ✅ **1Win** (mock mode)

### Sports Coverage

- ⚽ Football (1X2, Over/Under, Handicap)
- 🏀 Basketball (Moneyline, Totals, Spread)
- 🎮 Esports (CS:GO, Dota 2, LoL, Valorant)
- 🎾 Tennis (coming soon)
- 🏏 Cricket (coming soon)

### Core Features

- Real-time arbitrage detection
- Advanced fuzzy event matching
- Configurable profit thresholds
- Stake calculation and optimization
- CSV data export
- RESTful API with filtering
- Comprehensive logging

## 📋 API Endpoints

### Check System Status
```bash
GET http://localhost:8000/api/status
```

**Response:**
```json
{
  "service": "Arbitrage Detection API",
  "mode": "mock",
  "connectors": {
    "system_mode": "mock",
    "total_connectors": 6,
    "live_count": 0,
    "mock_count": 6
  },
  "last_scrape_time": "2025-01-10T12:30:00",
  "cached_arbitrages_count": 15
}
```

### Get Connector Status
```bash
GET http://localhost:8000/api/connectors/status
```

**Response:**
```json
{
  "system_mode": "hybrid",
  "force_mock_enabled": false,
  "connectors": {
    "mostbet": {"mode": "live", "status": "active"},
    "stake": {"mode": "live", "status": "active"},
    "leon": {"mode": "mock", "status": "active"},
    "parimatch": {"mode": "mock", "status": "active"},
    "1xbet": {"mode": "mock", "status": "active"},
    "1win": {"mode": "mock", "status": "active"}
  },
  "summary": {
    "total_connectors": 6,
    "live_connectors": 2,
    "mock_connectors": 4
  }
}
```

### Get Arbitrage Opportunities
```bash
GET http://localhost:8000/api/arbs?min_arb_percentage=0.5&bankroll=1000
```

**Response:**
```json
{
  "arbitrages": [
    {
      "event_name": "Manchester United vs Liverpool",
      "sport": "football",
      "market_type": "1x2",
      "profit_percentage": 2.34,
      "guaranteed_profit": 23.40,
      "outcomes": [
        {
          "name": "Manchester United",
          "odds": 2.10,
          "bookmaker": "mostbet",
          "url": "https://mostbet.com/..."
        },
        {
          "name": "Draw",
          "odds": 3.80,
          "bookmaker": "stake",
          "url": "https://stake.com/..."
        }
      ],
      "stakes": [...],
      "freshness_score": 0.95
    }
  ],
  "summary": {
    "total_arbitrages": 12,
    "processing_time_seconds": 1.23,
    "connector_status": {...}
  }
}
```

### Test Specific Connector
```bash
GET http://localhost:8000/api/connectors/mostbet/test
```

## 🎮 Command-Line Options

```bash
# Standard run (auto-detect mode based on credentials)
python -m app.main

# Force mock mode (ignore all API keys)
python -m app.main --force-mock

# Custom host and port
python -m app.main --host 0.0.0.0 --port 8080

# Development mode with auto-reload
python -m app.main --reload

# Show help
python -m app.main --help
```

## 📊 Example Log Output

### Mock Mode Startup
```
============================================================
ARBITRAGE SCANNER - MOCK MODE
============================================================
🔸 Force mock mode enabled via --force-mock flag

System Mode: MOCK

Connector Status:
  🔴 mostbet       - MOCK
  🔴 stake         - MOCK
  🔴 leon          - MOCK
  🔴 parimatch     - MOCK
  🔴 1xbet         - MOCK
  🔴 1win          - MOCK

Summary: 0 live, 6 mock

⚠️  MOCK MODE: Synthetic odds are being generated
   To enable live mode, add API keys to config/credentials.yaml
============================================================
```

### Hybrid Mode Startup
```
============================================================
ARBITRAGE SCANNER - HYBRID MODE
============================================================

System Mode: HYBRID

Connector Status:
  🟢 mostbet       - LIVE
  🟢 stake         - LIVE
  🔴 leon          - MOCK
  🔴 parimatch     - MOCK
  🔴 1xbet         - MOCK
  🔴 1win          - MOCK

Summary: 2 live, 4 mock
============================================================
```

### Odds Generation (Mock)
```
[MOCK] mostbet: Generated 45 synthetic odds
[MOCK] stake: Generated 43 synthetic odds
[MOCK] leon: Generated 47 synthetic odds
Fetched total of 135 odds from 3 connectors
Matching events across bookmakers...
Matched 18 events
Detecting arbitrage opportunities...
ARBITRAGE FOUND: Real Madrid vs Barcelona | Profit: 1.87% | Amount: $18.70
Found 5 arbitrages from 18 events
```

## 🔑 Environment Variables

You can also configure credentials via environment variables:

```bash
# Export credentials
export BOOKIE_MOSTBET_KEY="your-api-key"
export BOOKIE_MOSTBET_SECRET="your-api-secret"
export BOOKIE_STAKE_KEY="your-stake-key"

# Run server
python -m app.main
```

Environment variables **take precedence** over `credentials.yaml`.

## 🛠️ Configuration

### Main Configuration File
Edit `app/config.py` or use environment variables:

```python
# Arbitrage Detection
MIN_ARB_PERCENTAGE=0.5       # Minimum profit %
MIN_PROFIT_AMOUNT=10         # Minimum profit in currency
DEFAULT_BANKROLL=1000        # Default bankroll

# Matching
FUZZY_THRESHOLD=94           # Event name matching threshold
TIME_TOLERANCE_MINUTES=15    # Time matching tolerance

# Data Management
SAVE_RAW_DATA=true          # Save raw odds to CSV
EXPORT_CSV=true             # Export arbitrages to CSV
```

### Credentials Template
See `config/credentials.template.yaml` for all available options.

## 📁 Project Structure

```
app/
├── __init__.py
├── main.py                  # Application entry point with CLI
├── config.py                # Configuration management
│
├── api/
│   └── routes.py            # API endpoints
│
├── connectors/              # NEW: Connector system
│   ├── __init__.py
│   ├── mock_connector.py    # Mock data generator
│   └── connector_manager.py # Manages mock/live connectors
│
├── books/                   # Legacy scrapers (being phased out)
│   ├── base.py
│   ├── mostbet.py
│   └── stake.py
│
├── engine/
│   └── arbitrage.py         # Arbitrage detection logic
│
├── match/
│   └── matcher.py           # Event matching engine
│
├── schema/
│   └── models.py            # Pydantic data models
│
├── service/
│   └── orchestrator.py      # Main coordination service
│
└── utils/
    ├── logging.py           # Logging configuration
    └── helpers.py           # Utility functions

config/
├── credentials.template.yaml  # Template for API keys
└── credentials.yaml          # Your actual keys (gitignored)
```

## 🔒 Security Notes

- **Never commit `config/credentials.yaml`** to version control
- The `.gitignore` automatically excludes this file
- Store production credentials in environment variables
- Use credential rotation for production deployments
- Monitor API usage and rate limits

## 🐳 Docker Deployment

```bash
# Build image
docker build -t arbitrage-api .

# Run in mock mode
docker run -p 8000:8000 arbitrage-api

# Run with credentials (environment variables)
docker run -p 8000:8000 \
  -e BOOKIE_MOSTBET_KEY="your-key" \
  -e BOOKIE_STAKE_KEY="your-key" \
  arbitrage-api

# Run with credentials file
docker run -p 8000:8000 \
  -v $(pwd)/config/credentials.yaml:/code/config/credentials.yaml \
  arbitrage-api
```

## 📚 Additional Documentation

- **API Documentation**: http://localhost:8000/docs (Swagger UI)
- **ReDoc Documentation**: http://localhost:8000/redoc
- **Health Check**: http://localhost:8000/health

## 🤝 Contributing

This is a prototype system. To add new bookmaker connectors:

1. Create a new live connector in `app/connectors/`
2. Implement the required interface
3. Register it in `connector_manager.py`
4. Add credentials template in `config/credentials.template.yaml`

## 📝 License

MIT License - see LICENSE file for details

## 🆘 Support

- Check logs in `logs/` directory
- Use `--reload` flag for development debugging
- Test individual connectors with `/api/connectors/{bookmaker}/test`
- Monitor system status at `/api/status`

---

**Happy Arbitrage Hunting! 🎯💰**
