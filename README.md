# Sports Arbitrage Detection API

A FastAPI-based backend system for detecting arbitrage opportunities across multiple sports betting platforms. The system scrapes odds data, matches events across bookmakers, and identifies profitable arbitrage situations in real-time.

## Features

- **Multi-Bookmaker Support**: Scrapes odds from Mostbet, Stake, and extensible to other platforms
- **Real-time Detection**: Identifies arbitrage opportunities with configurable profit thresholds
- **Event Matching**: Advanced fuzzy matching to correlate events across different bookmakers
- **Comprehensive Markets**: Supports moneyline, totals, handicaps, and esports markets
- **REST API**: Full-featured API with filtering, caching, and export capabilities
- **Async Architecture**: High-performance async scraping with configurable concurrency
- **Data Export**: CSV export functionality for analysis and record-keeping
- **Production Ready**: Docker support, comprehensive logging, and health checks

## Installation

### Prerequisites

- Python 3.11+
- Docker (optional, recommended for production)

### Local Development

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd arbitrage-detection-backend
   ```

2. **Create virtual environment**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   playwright install chromium
   ```

4. **Configure environment**
   ```bash
   cp app/env.example app/.env
   # Edit app/.env with your configuration
   ```

5. **Run the application**
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```

## Usage

### API Endpoints

- **Get Arbitrages**: `GET /api/arbs` - Retrieve arbitrage opportunities with filtering
- **Live Arbitrages**: `GET /api/arbs/live` - Real-time arbitrage opportunities
- **System Status**: `GET /api/status` - System health and scraper status
- **Documentation**: `GET /docs` - Interactive API documentation

### Example Request

```bash
curl "http://localhost:8000/api/arbs?sport=football&min_arb_percentage=1.0&bankroll=1000"
```

### Response Format

```json
{
  "arbitrages": [
    {
      "event_name": "Team A vs Team B",
      "sport": "football",
      "market_type": "moneyline",
      "profit_percentage": 2.5,
      "guaranteed_profit": 25.00,
      "outcomes": [...],
      "stakes": [...]
    }
  ],
  "summary": {
    "total_arbitrages": 1,
    "processing_time_seconds": 1.23
  }
}
```

## Folder Structure

```
app/
├── __init__.py              # Package initialization
├── main.py                  # FastAPI application entry point
├── config.py                # Configuration management
├── normalization_map.json   # Team/league name mappings
├── .env                     # Environment variables (not in repo)
├── api/
│   ├── __init__.py
│   └── routes.py            # API endpoints and route handlers
├── books/
│   ├── __init__.py
│   ├── base.py              # Base scraper class
│   ├── mostbet.py           # Mostbet scraper implementation
│   └── stake.py             # Stake scraper implementation
├── engine/
│   ├── __init__.py
│   └── arbitrage.py         # Arbitrage detection algorithms
├── match/
│   ├── __init__.py
│   └── matcher.py           # Event matching logic
├── schema/
│   ├── __init__.py
│   └── models.py            # Pydantic data models
├── service/
│   ├── __init__.py
│   └── orchestrator.py      # Main coordination service
└── utils/
    ├── __init__.py
    ├── logging.py           # Logging configuration
    └── helpers.py           # Utility functions
logs/                        # Application logs (created at runtime)
exports/                     # CSV exports (created at runtime)
requirements.txt             # Python dependencies
Dockerfile                   # Docker container configuration
Procfile                     # Deployment configuration
```

## Deployment

### Docker Deployment

1. **Build the image**
   ```bash
   docker build -t arbitrage-api .
   ```

2. **Run the container**
   ```bash
   docker run -d \
     --name arbitrage-api \
     -p 10000:10000 \
     --env-file app/.env \
     arbitrage-api
   ```

3. **Health check**
   ```bash
   curl http://localhost:10000/health
   ```

### Production Considerations

- Set `HEADLESS=true` for browser automation
- Configure `CONCURRENT_SCRAPERS` based on server capacity
- Set appropriate `LOG_LEVEL` for production monitoring
- Use a reverse proxy (nginx) for SSL termination
- Monitor scraping success rates and adjust timeouts as needed
- Implement rate limiting based on bookmaker requirements

### Environment Variables

Key configuration options in `.env`:

```env
# Server
HOST=0.0.0.0
PORT=8000
DEBUG=false

# Scraping
CONCURRENT_SCRAPERS=6
SCRAPE_TIMEOUT=30
HEADLESS=true

# Arbitrage Detection
MIN_ARB_PERCENTAGE=0.5
MIN_PROFIT_AMOUNT=10
DEFAULT_BANKROLL=1000

# Data Management
SAVE_RAW_DATA=true
EXPORT_CSV=true
```

## License

This project is licensed under the MIT License - see the LICENSE file for details.