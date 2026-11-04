"""Vercel ASGI entrypoint; configuration comes from the deployment environment.

Importing this module creates the HTTP application only. Migrations and the
research worker must be managed separately from serverless request handlers.
"""

from app.core.config import Settings
from app.main import create_app


app = create_app(Settings(_env_file=None))
