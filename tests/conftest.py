"""Bootstrap de tests: garantiza BOVEDA_MASTER_KEY antes de cualquier import de lib."""

import os
import secrets

os.environ.setdefault("BOVEDA_MASTER_KEY", secrets.token_hex(32))
os.environ.setdefault("DJANGO_SECRET_KEY", secrets.token_hex(32))
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
