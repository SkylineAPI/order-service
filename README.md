# order-service

Part of **FoodExpress**, a microservices-based online food ordering system.
This service places and tracks orders. Before creating an order it synchronously calls the
**restaurant-service** (`POST /restaurants/{id}/validate-order`) to validate items and get authoritative prices.

| | |
|---|---|
| Language / framework | Python 3.12, FastAPI, SQLAlchemy 2 |
| Database | PostgreSQL 16 – private to this service |
| Inter-service communication | REST over HTTP (httpx) with timeout + retry, via Kubernetes DNS |
| Port | 8000 (interactive API docs at `/docs`) |
| Container image | `order-service:1.0.0` |

## API

| Type | Method | Path | Description |
|---|---|---|---|
| Command | POST | `/orders` | Place an order (validated by restaurant-service) |
| Command | PATCH | `/orders/{id}/status` | Move order through its lifecycle |
| Command | POST | `/orders/{id}/cancel` | Cancel (only while `CONFIRMED`) |
| Query | GET | `/orders?customerId=&restaurantId=&status=` | List / filter orders |
| Query | GET | `/orders/{id}` | Order details |
| Probe | GET | `/ready` | Readiness/liveness (own DB only) |
| Probe | GET | `/health` | Health incl. restaurant-service reachability |

Order lifecycle: `CONFIRMED → PREPARING → OUT_FOR_DELIVERY → DELIVERED`, or `CONFIRMED → CANCELLED`.
Pricing: `total = subtotal + 5% tax + ₹40 delivery fee`.

Error mapping: restaurant-service 404/422 is passed through to the caller; if restaurant-service is
unreachable after retries the order service returns **503** instead of hanging.

## Project structure

```
order-service/
├── app/
│   ├── main.py               # FastAPI routes (commands + queries + probes)
│   ├── models.py             # SQLAlchemy models, order state machine
│   ├── schemas.py            # Pydantic request/response models
│   ├── restaurant_client.py  # REST client for restaurant-service (timeout, retry)
│   ├── database.py           # engine/session, DB connection with retry
│   └── config.py             # env-based configuration
├── tests/test_orders.py      # pytest (SQLite + mocked restaurant client)
├── k8s/
│   ├── namespace.yaml
│   ├── postgres.yaml         # Secret + PVC + Deployment + ClusterIP Service
│   └── order-service.yaml    # ConfigMap + Deployment + NodePort Service + HPA
├── .github/workflows/ci.yml  # test → docker build → deploy to ephemeral minikube
├── Dockerfile
└── docker-compose.yml
```

## Run

```bash
# Unit tests
pip install -r requirements-dev.txt && pytest -q

# Docker (start restaurant-service's compose first – it creates foodexpress-net)
docker compose up -d --build
curl localhost:8000/health

# Kubernetes (minikube) – deploy restaurant-service first
minikube image build -t order-service:1.0.0 .
kubectl apply -f k8s/namespace.yaml && kubectl apply -f k8s/
kubectl -n foodexpress port-forward svc/order-service 8000:8000
```
