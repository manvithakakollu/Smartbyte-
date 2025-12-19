# SmartBite Deployment Guide

## Quick Start

### 1. Clone and Setup

```bash
git clone <repository-url>
cd smartbite
cp .env.example .env
# Edit .env with your API keys and passwords
```

### 2. Docker Deployment

```bash
# Build and run
docker-compose up -d

# View logs
docker-compose logs -f

# Stop
docker-compose down
```

### 3. Access

- Application: http://localhost:8501
- Default login: Use password from `.env` file

## Features

### Authentication
- Password-based authentication
- Session management
- Configurable via `ADMIN_PASSWORD` environment variable

### Rate Limiting
- LLM API call rate limiting
- Configurable requests per minute (default: 30)
- Per-session limits
- Graceful error messages

### CI/CD
- GitHub Actions workflow
- Automated linting and testing
- Docker image builds
- Deployment ready

### Load Testing
- Locust configuration included
- Multiple test scenarios
- Burst traffic simulation

## Environment Variables

See `.env.example` for all available variables.

**Required:**
- `OPENROUTER_API_KEY` - Your OpenRouter API key
- `ADMIN_PASSWORD` - Admin password for authentication

**Optional:**
- `LLM_RATE_LIMIT` - Rate limit (default: 30 req/min)
- `EMBEDDING_MODEL_NAME` - Embedding model (default: all-MiniLM-L6-v2)

## Testing

### Run Tests

```bash
pytest tests/ -v
```

### Load Testing

```bash
# Install Locust
pip install locust

# Run load test
locust -f locustfile.py --host=http://localhost:8501
```

## Production Checklist

- [ ] Change default `ADMIN_PASSWORD`
- [ ] Set secure API keys
- [ ] Configure HTTPS/TLS
- [ ] Set up monitoring
- [ ] Configure backups
- [ ] Review rate limits
- [ ] Test load scenarios
- [ ] Set up CI/CD pipeline

## Support

For deployment issues, check:
1. `docker-compose logs` for errors
2. Environment variables are set correctly
3. Ports are not already in use
4. Required files exist (data files, KB files)

