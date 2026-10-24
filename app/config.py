import os

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://orderuser:orderpass@localhost:5432/orderdb"
)
RESTAURANT_SERVICE_URL = os.getenv("RESTAURANT_SERVICE_URL", "http://localhost:3000")
RESTAURANT_TIMEOUT_SECONDS = float(os.getenv("RESTAURANT_TIMEOUT_SECONDS", "3"))
RESTAURANT_MAX_RETRIES = int(os.getenv("RESTAURANT_MAX_RETRIES", "2"))

DELIVERY_FEE = float(os.getenv("DELIVERY_FEE", "40"))
TAX_RATE = float(os.getenv("TAX_RATE", "0.05"))
