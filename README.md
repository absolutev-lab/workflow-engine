# Workflow Engine

A powerful Python-based workflow automation engine with n8n integration, real-time streaming, and comprehensive monitoring.

## Features

- **FastAPI Backend**: High-performance REST API with automatic documentation
- **PostgreSQL Database**: Robust data storage with SQLAlchemy ORM
- **Celery Task Queue**: Asynchronous workflow execution with Redis backend
- **n8n Integration**: Seamless workflow synchronization and execution
- **WebSocket Support**: Real-time workflow monitoring and event streaming
- **Webhook Management**: Dynamic webhook endpoints for external integrations
- **Authentication & Security**: JWT tokens, API keys, and role-based access control
- **Monitoring & Logging**: Comprehensive system metrics and health checks
- **Docker Support**: Complete containerization with Docker Compose

## Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL 15+
- Redis 7+
- Docker & Docker Compose (optional)

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd workflow-engine
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

4. **Initialize the database**
   ```bash
   # Make sure PostgreSQL is running
   python -c "from app.core.database import engine, Base; Base.metadata.create_all(bind=engine)"
   ```

5. **Start Redis**
   ```bash
   redis-server
   ```

6. **Start Celery worker**
   ```bash
   celery -A app.celery_app worker --loglevel=info
   ```

7. **Start the application**
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```

### Docker Deployment

1. **Build and start all services**
   ```bash
   docker-compose up -d
   ```

2. **View logs**
   ```bash
   docker-compose logs -f
   ```

3. **Stop services**
   ```bash
   docker-compose down
   ```

## API Documentation

Once the application is running, visit:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## Architecture

### Core Components

- **FastAPI Application** (`app/main.py`): Main web server
- **Database Models** (`app/models/`): SQLAlchemy models for data persistence
- **API Endpoints** (`app/api/v1/`): REST API routes and handlers
- **Services** (`app/services/`): Business logic and external integrations
- **Tasks** (`app/tasks/`): Celery background tasks
- **WebSocket** (`app/websocket/`): Real-time communication

### Database Schema

- **Users**: User accounts and authentication
- **Workflows**: Workflow definitions and configurations
- **Executions**: Workflow execution records and results
- **Triggers**: Workflow trigger configurations
- **Webhooks**: Dynamic webhook endpoints
- **Integrations**: External service connections
- **API Keys**: API access management
- **Execution Logs**: Detailed execution logging

## Configuration

### Environment Variables

```bash
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/workflow_engine

# Redis
REDIS_URL=redis://localhost:6379/0

# Security
SECRET_KEY=your-secret-key-here
ACCESS_TOKEN_EXPIRE_MINUTES=30

# n8n Integration
N8N_BASE_URL=http://localhost:5678
N8N_API_KEY=your-n8n-api-key

# Application
ENVIRONMENT=development
LOG_LEVEL=INFO
```

## API Usage

### Authentication

1. **Register a new user**
   ```bash
   curl -X POST "http://localhost:8000/api/v1/auth/register" \
        -H "Content-Type: application/json" \
        -d '{"email": "user@example.com", "password": "password123"}'
   ```

2. **Login**
   ```bash
   curl -X POST "http://localhost:8000/api/v1/auth/login" \
        -H "Content-Type: application/json" \
        -d '{"username": "user@example.com", "password": "password123"}'
   ```

### Workflow Management

1. **Create a workflow**
   ```bash
   curl -X POST "http://localhost:8000/api/v1/workflows/" \
        -H "Authorization: Bearer <token>" \
        -H "Content-Type: application/json" \
        -d '{"name": "My Workflow", "definition": {...}}'
   ```

2. **Execute a workflow**
   ```bash
   curl -X POST "http://localhost:8000/api/v1/executions/execute/<workflow_id>" \
        -H "Authorization: Bearer <token>" \
        -H "Content-Type: application/json" \
        -d '{"input_data": {...}}'
   ```

### WebSocket Connection

```javascript
const ws = new WebSocket('ws://localhost:8000/api/v1/ws/ws?token=<your_token>');

ws.onopen = function() {
    // Subscribe to workflow updates
    ws.send(JSON.stringify({
        type: 'subscribe_workflow',
        workflow_id: 'workflow-id-here'
    }));
};

ws.onmessage = function(event) {
    const message = JSON.parse(event.data);
    console.log('Received:', message);
};
```

## Monitoring

### Health Checks

- **Basic Health**: `GET /api/v1/health`
- **Detailed Status**: `GET /api/v1/status` (authenticated)
- **System Metrics**: `GET /api/v1/metrics/system` (admin only)

### Celery Monitoring

Access Flower dashboard at: http://localhost:5555

### Logs

- Application logs: `logs/app.log`
- Docker logs: `docker-compose logs`

## Development

### Project Structure

```
workflow-engine/
├── app/
│   ├── api/v1/          # API endpoints
│   ├── core/            # Core configuration and utilities
│   ├── models/          # Database models
│   ├── services/        # Business logic
│   ├── tasks/           # Celery tasks
│   ├── websocket/       # WebSocket handlers
│   └── main.py          # FastAPI application
├── logs/                # Application logs
├── docker-compose.yml   # Docker services
├── Dockerfile          # Application container
├── requirements.txt    # Python dependencies
└── README.md           # This file
```

### Running Tests

```bash
# Install test dependencies
pip install pytest pytest-asyncio httpx

# Run tests
pytest
```

### Code Quality

```bash
# Format code
black app/

# Lint code
flake8 app/

# Type checking
mypy app/
```

## n8n Integration

### Setup

1. **Start n8n**
   ```bash
   docker run -it --rm --name n8n -p 5678:5678 n8nio/n8n
   ```

2. **Configure API access**
   - Enable API access in n8n settings
   - Generate API key
   - Update `N8N_API_KEY` environment variable

3. **Sync workflows**
   ```bash
   curl -X POST "http://localhost:8000/api/v1/integrations/n8n/sync" \
        -H "Authorization: Bearer <token>" \
        -H "Content-Type: application/json" \
        -d '{"sync_direction": "from_n8n"}'
   ```

## Deployment

### Production Considerations

1. **Security**
   - Use strong secret keys
   - Enable HTTPS
   - Configure proper CORS settings
   - Use environment-specific configurations

2. **Performance**
   - Scale Celery workers based on load
   - Configure database connection pooling
   - Use Redis clustering for high availability
   - Implement proper caching strategies

3. **Monitoring**
   - Set up log aggregation
   - Configure alerting for critical metrics
   - Monitor database performance
   - Track API response times

### Docker Production Setup

```yaml
# docker-compose.prod.yml
version: '3.8'
services:
  app:
    build: .
    environment:
      - ENVIRONMENT=production
      - SECRET_KEY=${SECRET_KEY}
    deploy:
      replicas: 3
      resources:
        limits:
          memory: 512M
        reservations:
          memory: 256M
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For support and questions:
- Create an issue on GitHub
- Check the documentation
- Review the API documentation at `/docs`