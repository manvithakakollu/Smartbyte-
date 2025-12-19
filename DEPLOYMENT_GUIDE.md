# Deployment Guide

## Overview

This guide covers deploying SmartBite in production environments using Docker, Docker Compose, and CI/CD pipelines.

## Prerequisites

- Docker and Docker Compose installed
- Python 3.10+ (for local development)
- Environment variables configured
- GitHub Actions (for CI/CD)

## Quick Start

### 1. Environment Setup

Create a `.env` file:

```bash
OPENROUTER_API_KEY=your-api-key-here
ADMIN_PASSWORD=secure-password-here
EMBEDDING_MODEL_NAME=all-MiniLM-L6-v2
DATA_FILENAME=updated_nyc_inspections.xlsx
LLM_RATE_LIMIT=30
```

### 2. Build and Run with Docker Compose

```bash
# Build and start services
docker-compose up -d

# View logs
docker-compose logs -f web

# Stop services
docker-compose down
```

### 3. Access Application

Open http://localhost:8501 in your browser.

## Authentication

The application uses basic password authentication. Set `ADMIN_PASSWORD` in your `.env` file.

**Security Note:** In production, use a strong password and consider implementing:
- OAuth2 / OIDC integration
- Multi-factor authentication
- Session management with secure cookies

## Rate Limiting

LLM API calls are rate-limited to prevent abuse:

- Default: 30 requests per minute per session
- Configurable via `LLM_RATE_LIMIT` environment variable
- Rate limit status shown when exceeded

**Production Recommendations:**
- Use Redis for distributed rate limiting
- Implement per-user/IP limits
- Add monitoring and alerting

## Docker Configuration

### Dockerfile

The Dockerfile uses:
- Python 3.10 slim base image
- Multi-stage build (optional optimization)
- Health checks
- Non-root user (recommended for production)

### Docker Compose

Services:
- **web**: Main Streamlit application
- **chromadb**: ChromaDB vector database (optional)
- Volumes: Persistent storage for data and indexes

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENROUTER_API_KEY` | OpenRouter API key | Required |
| `ADMIN_PASSWORD` | Admin password | `admin123` |
| `EMBEDDING_MODEL_NAME` | Embedding model | `all-MiniLM-L6-v2` |
| `CHROMA_DB_PATH` | ChromaDB path | `chroma_db` |
| `KB_FOLDER` | Knowledge base folder | `kb` |
| `LLM_RATE_LIMIT` | Rate limit (req/min) | `30` |

## CI/CD Pipeline

### GitHub Actions Workflow

The workflow includes:
1. **Lint**: Code quality checks with flake8
2. **Test**: Unit tests with pytest
3. **Build**: Docker image build
4. **Deploy**: (Optional) Deployment step

### Running Tests Locally

```bash
# Install test dependencies
pip install pytest pytest-cov flake8

# Run tests
pytest tests/ -v

# Run linting
flake8 . --max-line-length=127
```

## Load Testing

### Using Locust

```bash
# Install Locust
pip install locust

# Run load test
locust -f locustfile.py --host=http://localhost:8501

# Open Locust web UI at http://localhost:8089
# Or run headless:
locust -f locustfile.py --host=http://localhost:8501 --headless -u 50 -r 5 -t 60s
```

### Test Scenarios

1. **Normal Traffic**: 50 concurrent users
2. **High Traffic**: 100 concurrent users
3. **Burst Traffic**: 20 rapid-fire users

### Expected Metrics

- Response time < 2s (p95)
- Error rate < 1%
- Rate limiting working correctly
- No memory leaks

## Production Deployment

### Recommended Setup

1. **Reverse Proxy** (Nginx/Traefik):
   - SSL/TLS termination
   - Load balancing
   - Rate limiting at edge

2. **Container Orchestration**:
   - Kubernetes (for scale)
   - Docker Swarm (simpler alternative)

3. **Monitoring**:
   - Prometheus + Grafana
   - Application logs (ELK stack)
   - Health check endpoints

4. **Backup**:
   - ChromaDB data
   - Configuration files
   - Knowledge base

### Health Checks

Health check endpoint: `/_stcore/health`

### Scaling

To scale horizontally:
1. Use shared ChromaDB instance
2. Use Redis for rate limiting
3. Use session store (Redis/Memcached)
4. Load balance with sticky sessions

## Security Checklist

- [ ] Change default `ADMIN_PASSWORD`
- [ ] Use HTTPS/TLS
- [ ] Enable firewall rules
- [ ] Regular security updates
- [ ] Secrets management (not in code)
- [ ] Input validation enabled
- [ ] Rate limiting configured
- [ ] Logging and monitoring enabled

## Troubleshooting

### Container won't start

```bash
# Check logs
docker-compose logs web

# Check environment variables
docker-compose config
```

### Rate limiting issues

- Check `LLM_RATE_LIMIT` environment variable
- Verify session state is working
- Check application logs

### ChromaDB connection issues

- Verify ChromaDB container is running
- Check network connectivity
- Verify volume mounts

## Support

For issues or questions:
1. Check logs: `docker-compose logs`
2. Review this guide
3. Check GitHub Issues
4. Contact support team

