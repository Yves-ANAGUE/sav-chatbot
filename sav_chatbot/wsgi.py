import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "sav_chatbot.settings")

application = get_wsgi_application()

# Vercel cherche une variable nommée "app" (pas "application")
app = application
