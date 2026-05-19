#!/usr/bin/env bash
# build.sh — Script exécuté par Render à chaque déploiement
# Rend le fichier exécutable : chmod +x build.sh

set -o errexit  # Arrêt immédiat si une commande échoue

pip install --upgrade pip
pip install -r requirements.txt

# Collecte les fichiers statiques (CSS, JS) pour WhiteNoise
python manage.py collectstatic --noinput

# Applique les migrations de base de données
python manage.py migrate --noinput

# Importe le catalogue produits (idempotent : update_or_create)
python manage.py charger_donnees --sans-historique
