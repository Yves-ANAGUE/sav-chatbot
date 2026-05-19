# SAV Chatbot — Assistant Intelligent e-commerce

Application Django de service après-vente dotée d'un chatbot IA contextuel,
alimenté par un catalogue produit importé depuis FakeStore API.

---

## Architecture

```
sav_chatbot/
├── sav_chatbot/          # Projet Django (settings, urls, wsgi)
├── catalogue/            # App catalogue produits
│   ├── models.py         # Produit, CategorieProduit, HistoriqueImport
│   ├── parseurs.py       # Parseurs FakeStore, CSV, Open Food Facts
│   ├── serializers.py    # Validation via Django Forms
│   ├── services.py       # Logique d'import bulk (O(n/batch) requêtes)
│   ├── signals.py        # Mise à jour auto vecteur full-text
│   ├── management/
│   │   └── commands/
│   │       └── charger_donnees.py   # python manage.py charger_donnees
│   └── tests.py
├── chatbot/              # App chatbot SAV
│   ├── models.py         # ConversationSAV, MessageSAV
│   ├── services.py       # RAG : recherche produits + appel API Anthropic
│   ├── views.py          # Endpoints AJAX JSON
│   └── tests.py
└── templates/
    └── chatbot/
        └── interface.html   # Interface de chat (HTML/CSS/JS pur)
```

---

## Démarrage rapide

### 1. Prérequis

- Python 3.11+
- PostgreSQL 14+
- Une clé API Anthropic (gratuit avec compte sur console.anthropic.com)

### 2. Installation

```bash
# Cloner et créer l'environnement virtuel
git clone <repo>
cd sav_chatbot
python -m venv .venv
source .venv/bin/activate          # Windows : .venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configuration

```bash
cp .env.example .env
# Éditez .env avec vos paramètres :
# - ANTHROPIC_API_KEY=sk-ant-...
# - DB_MOT_DE_PASSE=votre_mdp_postgres
```

Chargez les variables d'environnement :
```bash
export $(cat .env | grep -v '#' | xargs)
```

### 4. Base de données

```bash
# Créer la base PostgreSQL
psql -U postgres -c "CREATE DATABASE sav_chatbot_db;"

# Appliquer les migrations
python manage.py migrate

# Créer un superutilisateur (optionnel, pour l'admin)
python manage.py createsuperuser
```

### 5. Import du catalogue

```bash
# Import depuis FakeStore API (20 produits réels, gratuit, sans authentification)
python manage.py charger_donnees

# Import depuis un CSV local
python manage.py charger_donnees --source csv --csv /chemin/vers/produits.csv

# Options avancées
python manage.py charger_donnees --taille-lot 200 --sans-historique
```

### 6. Lancement

```bash
python manage.py runserver
```

Ouvrez http://localhost:8000 → interface de chat SAV.
Administration : http://localhost:8000/admin/

---

## API Endpoints

| Méthode | URL | Description |
|---------|-----|-------------|
| GET | `/` | Interface de chat |
| POST | `/chatbot/envoyer/` | Envoyer un message (JSON) |
| GET | `/chatbot/historique/<uuid>/` | Historique d'une conversation |
| GET | `/catalogue/rechercher/?q=terme` | Recherche de produits |
| GET | `/catalogue/categories/` | Liste des catégories |

### Exemple d'appel API

```bash
curl -X POST http://localhost:8000/chatbot/envoyer/ \
  -H "Content-Type: application/json" \
  -H "X-CSRFToken: <token>" \
  -d '{"message": "Avez-vous des vestes imperméables ?"}'
```

Réponse :
```json
{
  "reponse": "Oui, nous proposons plusieurs modèles...",
  "conversation_uuid": "550e8400-e29b-41d4-a716-446655440000",
  "produits_references": [
    {"id": 3, "nom": "Fjallraven Backpack", "prix": 109.95, "en_stock": true}
  ]
}
```

---

## Choix techniques

### Full-text search PostgreSQL

```python
# Signal post_save → SearchVectorField pré-calculé avec pondération
vecteur = (
    SearchVector("nom", weight="A", config="french")       # Poids max
    + SearchVector("description", weight="B", config="french")
    + SearchVector("marque", weight="C", config="french")
)
# Index GIN → O(log n) au lieu de O(n) pour LIKE
```

### Import bulk

```
Approche naïve :  N produits × 1 INSERT = O(N) requêtes
Approche bulk :   N produits / taille_lot INSERTs = O(N/500) requêtes
→ Gain : 50× moins de round-trips réseau pour N=50 000
```

### RAG (Retrieval-Augmented Generation)

```
Question utilisateur
      ↓
Recherche full-text catalogue (max 5 produits)
      ↓
Injection dans system prompt Anthropic
      ↓
Réponse contextualisée (ne "hallucine" pas de produits inexistants)
```

---

## Tests

```bash
# Tous les tests
python manage.py test

# Un module spécifique
python manage.py test catalogue.tests
python manage.py test chatbot.tests

# Avec verbosité
python manage.py test --verbosity=2
```

---

## Variables d'environnement

| Variable | Défaut | Description |
|----------|--------|-------------|
| `DJANGO_SECRET_KEY` | (dev key) | Clé secrète Django |
| `DEBUG` | `True` | Mode debug |
| `DB_NOM` | `sav_chatbot_db` | Nom de la base PostgreSQL |
| `DB_UTILISATEUR` | `postgres` | Utilisateur PostgreSQL |
| `DB_MOT_DE_PASSE` | `postgres` | Mot de passe PostgreSQL |
| `DB_HOTE` | `localhost` | Hôte PostgreSQL |
| `ANTHROPIC_API_KEY` | *(requis)* | Clé API Anthropic |
| `IMPORT_TAILLE_LOT` | `500` | Taille des lots d'import |
| `CHATBOT_MAX_PRODUITS_CONTEXTE` | `5` | Produits max injectés dans le prompt |

---

## Ajouter un nouveau dataset

1. Créez un parseur dans `catalogue/parseurs.py` suivant le patron `parser_fakestore_api`
2. Ajoutez-le dans `catalogue/services.py` avec une fonction `importer_depuis_xxx`
3. Exposez-le via `--source xxx` dans la commande `charger_donnees`
