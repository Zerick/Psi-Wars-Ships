# =============================================================================
# Psi-Wars Space Combat Simulator — config.py
# =============================================================================
# Central configuration. Edit these values to match your environment.
# All values can be overridden by environment variables.
# =============================================================================
import os

# Server
HOST = os.getenv("PSIWARS_HOST", "0.0.0.0")
PORT = int(os.getenv("PSIWARS_PORT", "8000"))

# Database
# For development: current directory is fine.
# For production on Pi: point this at your SSD/USB mount, e.g.:
#   /mnt/ssd/psiwars/psiwars.db
DB_PATH = os.getenv("PSIWARS_DB_PATH", "./psiwars.db")

# CORS origins — add your Pi's local IP if accessing from another machine
# e.g. "http://192.168.1.42:5173" for Vite dev server on the Pi
CORS_ORIGINS = [
    "http://localhost:5173",
    "http://localhost:8000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:8000",
    "http://192.168.0.95:8000",
]
# Token store TTL (seconds). Tokens are kept in memory; this is the max age.
# In the PoC tokens live for the life of the process. Proper auth is a later slice.
TOKEN_TTL_SECONDS = 60 * 60 * 24 * 7  # 7 days
