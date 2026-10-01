"""
Service IA du chatbot SAV.

Fournisseur IA : Groq (gratuit) via la librairie requests.
Ajoutez dans .env : GROQ_API_KEY=gsk_votre_cle_ici

Stratégie de robustesse : fallback automatique multi-modèles.
Si un modèle est retiré (404), rate-limited (429) ou en erreur réseau,
le suivant de MODELES_FALLBACK est essayé automatiquement.
"""
import json
import logging

from django.conf import settings

from catalogue.models import Produit

logger = logging.getLogger(__name__)

PROMPT_SYSTEME_BASE = """Tu es un assistant service après-vente (SAV) expert et bienveillant.
Tu aides les clients avec leurs questions sur les produits de notre catalogue.

Règles absolues :
- Réponds UNIQUEMENT en te basant sur le contexte produit fourni ci-dessous.
- Si un produit n'est pas dans le contexte, dis que tu ne peux pas renseigner ce produit.
- Sois concis, précis et professionnel.
- Si tu ne sais pas, dis-le honnêtement plutôt que d'inventer.
- Pour les remboursements/retours : oriente vers le service commercial humain.
- Réponds toujours en français.

FORMAT DE RÉPONSE : Texte clair en français, sans markdown excessif.
"""

# ── Modèles Groq avec fallback automatique ──
# Ordre de préférence : du plus puissant au plus léger.
# Vérifier la disponibilité : curl -H "Authorization: Bearer $GROQ_API_KEY" \
#   https://api.groq.com/openai/v1/models
MODELES_FALLBACK = [
    "openai/gpt-oss-120b",        # Principal — le plus performant
    "openai/gpt-oss-20b",         # Fallback rapide et léger
    "qwen/qwen3.8-27b",           # Fallback multimodal (texte + image)
]


def _construire_contexte_produits(question: str) -> tuple[str, list]:
    """Recherche les produits pertinents et construit le texte de contexte."""
    nb_max = getattr(settings, "CHATBOT_MAX_PRODUITS_CONTEXTE", 5)

    produits = (
        Produit.objects
        .recherche_plein_texte(question)
        .avec_contexte_chatbot()
        .disponibles()[:nb_max]
    )

    if not produits:
        produits = (
            Produit.objects
            .avec_contexte_chatbot()
            .disponibles()
            .order_by("-note_moyenne")[:3]
        )

    if not produits:
        return "Aucun produit disponible dans le catalogue.", []

    lignes = ["=== CATALOGUE PRODUITS DISPONIBLES ==="]
    for p in produits:
        d = p.to_dict_contexte()
        stock = "En stock" if d["en_stock"] else "Rupture de stock"
        note = f"{d['note']}/5" if d["note"] else "Pas encore noté"
        lignes.append(
            f"\n[Produit #{d['id']}] {d['nom']}"
            f"\n  Catégorie : {d['categorie']}"
            f"\n  Prix : {d['prix']} EUR"
            f"\n  Disponibilité : {stock}"
            f"\n  Note clients : {note}"
            f"\n  Description : {d['description']}"
        )
        if d["attributs"]:
            lignes.append(
                f"  Caractéristiques : {json.dumps(d['attributs'], ensure_ascii=False)}"
            )

    return "\n".join(lignes), list(produits)


def _appeler_api_groq(historique_messages: list, system_prompt: str) -> str:
    """
    Appelle l'API Groq avec fallback automatique multi-modèles.

    Si le modèle courant retourne 404 (retiré), 429 (rate limit) ou une
    erreur réseau, passe automatiquement au modèle suivant de MODELES_FALLBACK.
    Lève ConnectionError si tous les modèles échouent.

    Note : requests envoie un User-Agent standard qui passe le WAF Cloudflare,
    contrairement à urllib qui est bloqué (error 1010).
    """
    try:
        import requests as req
    except ImportError:
        raise RuntimeError(
            "La librairie 'requests' est manquante. "
            "Installez-la avec : pip install requests"
        )

    api_key = getattr(settings, "GROQ_API_KEY", "")

    if not api_key:
        raise ValueError(
            "GROQ_API_KEY manquante. "
            "Inscrivez-vous sur https://console.groq.com "
            "et ajoutez GROQ_API_KEY=gsk_... dans votre .env"
        )

    if not api_key.startswith("gsk_"):
        raise ValueError(
            f"GROQ_API_KEY invalide (commence par '{api_key[:8]}'). "
            "Elle doit commencer par 'gsk_'."
        )

    messages_complets = [{"role": "system", "content": system_prompt}] + historique_messages

    derniere_erreur = None

    for modele in MODELES_FALLBACK:
        try:
            logger.info("Tentative avec le modèle : %s", modele)

            reponse = req.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": modele,
                    "messages": messages_complets,
                    "max_tokens": 1024,
                    "temperature": 0.3,
                },
                timeout=30,
            )
            reponse.raise_for_status()

            logger.info("Succès avec le modèle : %s", modele)
            return reponse.json()["choices"][0]["message"]["content"]

        except req.exceptions.HTTPError as exc:
            statut = exc.response.status_code

            # 404 = modèle retiré | 429 = rate limit → essayer le suivant
            if statut in (404, 429):
                try:
                    msg = exc.response.json().get("error", {}).get("message", str(exc))
                except Exception:
                    msg = str(exc)

                logger.warning(
                    "Modèle %s indisponible (HTTP %d) : %s — passage au suivant",
                    modele, statut, msg
                )
                derniere_erreur = ConnectionError(
                    f"Modèle {modele} échoué (HTTP {statut}) : {msg}"
                )
                continue

            # Autres erreurs HTTP (401, 500…) → échec immédiat
            try:
                msg = exc.response.json().get("error", {}).get("message", str(exc))
            except Exception:
                msg = str(exc)
            raise ConnectionError(
                f"Erreur API Groq ({statut}) : {msg}"
            ) from exc

        except req.exceptions.RequestException as exc:
            logger.warning("Erreur réseau avec %s : %s — passage au suivant", modele, exc)
            derniere_erreur = ConnectionError(f"Erreur réseau Groq : {exc}")
            continue

    # Tous les modèles ont échoué
    raise derniere_erreur or ConnectionError(
        "Tous les modèles Groq sont indisponibles. "
        "Vérifiez votre clé API et les modèles disponibles."
    )


def generer_reponse_sav(question_utilisateur: str, historique_messages: list) -> tuple:
    """
    Point d'entrée principal : génère une réponse SAV contextualisée.
    Retourne (reponse_texte, produits_references).
    """
    contexte_produits, produits_references = _construire_contexte_produits(
        question_utilisateur
    )

    system_prompt_complet = f"{PROMPT_SYSTEME_BASE}\n\n{contexte_produits}"

    messages_avec_question = historique_messages + [
        {"role": "user", "content": question_utilisateur}
    ]

    try:
        reponse = _appeler_api_groq(messages_avec_question, system_prompt_complet)
    except (ConnectionError, ValueError, RuntimeError, KeyError) as exc:
        logger.error("Erreur génération réponse SAV : %s", exc)
        if getattr(settings, "DEBUG", False):
            reponse = f"Erreur technique (DEBUG) : {exc}"
        else:
            reponse = (
                "Je rencontre une difficulté technique momentanée. "
                "Veuillez réessayer dans quelques instants ou contacter notre support."
            )
        produits_references = []

    return reponse, produits_references