"""
Script de diagnostic — lancez depuis le dossier sav_chatbot :
    set -a && source .env && set +a
    python test_groq.py
"""
import json
import os
import sys
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError

api_key = os.environ.get("GROQ_API_KEY", "")
print(f"Clé détectée : {api_key[:12]}...{api_key[-4:]} ({len(api_key)} caractères)")

if not api_key:
    print("ERREUR : GROQ_API_KEY vide")
    sys.exit(1)

corps = json.dumps({
    "model": "llama-3.3-70b-versatile",
    "messages": [
        {"role": "system", "content": "Tu es un assistant SAV."},
        {"role": "user", "content": "bonjour"},
    ],
    "max_tokens": 50,
    "temperature": 0.3,
}).encode("utf-8")

requete = Request(
    "https://api.groq.com/openai/v1/chat/completions",
    data=corps,
    headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    },
    method="POST",
)

print(f"\nEnvoi vers : {requete.full_url}")
print(f"Authorization header : Bearer {api_key[:12]}...")

try:
    with urlopen(requete, timeout=30) as rep:
        donnees = json.loads(rep.read().decode("utf-8"))
        reponse = donnees["choices"][0]["message"]["content"]
        print(f"\nSUCCES ! Réponse Groq : {reponse}")
except HTTPError as exc:
    corps_erreur = exc.read().decode("utf-8")
    print(f"\nHTTPError {exc.code} : {exc.reason}")
    print(f"Corps de l'erreur : {corps_erreur}")
except URLError as exc:
    print(f"\nURLError : {exc.reason}")
except Exception as exc:
    print(f"\nErreur inattendue : {type(exc).__name__} : {exc}")