import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

# M1 ships a standard ASGI app; M4 swaps this for a Channels ProtocolTypeRouter
# (HTTP + WebSocket) when live job-progress lands.
application = get_asgi_application()
