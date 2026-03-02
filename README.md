# SOS Services — Portugal Real-Time Hazard Monitor

A real-time geospatial hazard correlation platform for Portugal. Aggregates live data from weather, fire, civil protection, traffic, and event sources — then uses an analytics engine to correlate overlapping hazards and surface risk alerts on an interactive map.

## Architecture

```
┌──────────────┐     ┌───────────────────┐     ┌──────────────┐
│   Frontend   │◄────│   Backend API     │◄────│   PostgreSQL │
│  React +     │ WS  │   FastAPI +       │     │   + PostGIS  │
│  Leaflet Map │     │   Analytics       │     └──────────────┘
└──────────────┘     │   Engine          │     ┌──────────────┐
                     │                   │◄────│    Redis      │
                     └───────┬───────────┘     │  Cache/PubSub│
                             │                 └──────────────┘
                    ┌────────┴────────┐
                    │  Data Adapters  │
                    ├─────────────────┤
                    │ IPMA Weather    │
                    │ NASA FIRMS Fire │
                    │ Proteção Civil  │
                    │ Traffic (TomTom + OSM) │
                    │ Events (Ticketmaster + PT holidays)│
                    └─────────────────┘
```

## Data Sources

| Source | Type | Update Frequency |
|--------|------|-----------------|
| IPMA (api.ipma.pt) | Weather warnings & forecasts | ~15 min |
| NASA FIRMS | Satellite fire detection | ~3 hours |
| Proteção Civil (prociv.pt) | Active emergencies | ~5 min |
| OpenWeatherMap / Open-Meteo | Current weather + forecast | ~10 min |
| TomTom + OSM Overpass | Traffic flow / incidents / roadworks | ~5 min |
| Ticketmaster + Nager.Date | Events + public holidays | ~1 hour |
| OpenStreetMap + Leaflet | Base map | Real-time tiles |

## Hazard Correlation Examples

The analytics engine detects combined risk scenarios:

- 🔥 **Fire + Wind + Dry conditions** → Elevated wildfire risk alert
- 🌊 **Heavy rain + Coastal area + High tide** → Flood risk alert
- 🚗 **Traffic incident + Emergency occurrence** → Route disruption alert
- 🎪 **Large event + Severe weather warning** → Crowd safety alert

## Quick Start

```bash
# 1. Clone
git clone https://github.com/<your-user>/sosservices.git
cd sosservices

# 2. Configure
cp .env.example .env
# Edit .env with your API keys

# 3. Run
docker-compose up --build
```

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

## Tech Stack (100% Open Source)

- **Frontend**: React 18 + Leaflet + OpenStreetMap
- **Backend**: Python FastAPI (async)
- **Analytics**: Custom correlation engine (Python)
- **Database**: PostgreSQL + PostGIS
- **Cache/PubSub**: Redis
- **Deployment**: Docker + Docker Compose
- **Maps**: OpenStreetMap (no proprietary dependencies)

## Project Structure

```
sosservices/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app entry
│   │   ├── config.py            # Settings & env vars
│   │   ├── models/              # Data models
│   │   ├── api/                 # REST + WebSocket routes
│   │   ├── services/            # Data source adapters
│   │   ├── analytics/           # Correlation engine
│   │   └── ingestion/           # Scheduler for polling
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.js
│   │   ├── components/          # Map, controls, alerts
│   │   ├── hooks/               # WebSocket hook
│   │   └── services/            # API client
│   ├── Dockerfile
│   └── package.json
├── docker-compose.yml
└── .env.example
```

## License

MIT
