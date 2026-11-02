# Prometheus and Grafana Monitoring

Monitoring stack for the DevSecOps CI/CD project.

## Components

- Prometheus v3.5.0
- Grafana v12.1.0

## Directory Structure

    monitoring/
    ├── docker-compose.yml
    ├── .env.example
    ├── README.md
    └── prometheus/
        └── prometheus.yml

## Prerequisites

- Docker Engine
- Docker Compose
- Existing Docker network named monitoring-net
- Flask application exposing /metrics on port 5000

## Configuration

Copy .env.example to .env and configure a strong Grafana admin password.

The default monitoring host binding is 127.0.0.1.
Change MONITORING_HOST_IP if remote access is required.

## Run

    docker compose up -d

## Access

- Prometheus: http://localhost:9090
- Grafana: http://localhost:3000

Username: admin

## Prometheus Target

- Job: flask-app
- Target: devsecops-app:5000
- Metrics path: /metrics
- Scrape interval: 15 seconds

The Flask container must be connected to the external Docker network
monitoring-net and expose the /metrics endpoint.

## Stop

    docker compose down

Named volumes are retained when the stack is stopped.
