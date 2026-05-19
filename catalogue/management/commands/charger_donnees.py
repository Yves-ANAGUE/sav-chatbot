"""
Commande de gestion : python manage.py charger_donnees

Usage :
    python manage.py charger_donnees                    # FakeStore API (défaut)
    python manage.py charger_donnees --source fakestore
    python manage.py charger_donnees --csv /chemin/fichier.csv
    python manage.py charger_donnees --taille-lot 200
"""
import logging
import sys
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from catalogue.models import HistoriqueImport
from catalogue.services import importer_catalogue_fakestore, importer_depuis_csv

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Télécharge et importe le catalogue produits depuis une source externe."

    def add_arguments(self, parser):
        parser.add_argument(
            "--source",
            choices=["fakestore", "csv"],
            default="fakestore",
            help="Source des données (défaut : fakestore)",
        )
        parser.add_argument(
            "--csv",
            dest="chemin_csv",
            type=str,
            help="Chemin vers le fichier CSV (requis si --source=csv)",
        )
        parser.add_argument(
            "--taille-lot",
            type=int,
            default=500,
            help="Taille des lots pour l'import bulk (défaut : 500)",
        )
        parser.add_argument(
            "--sans-historique",
            action="store_true",
            help="Ne pas enregistrer dans HistoriqueImport",
        )

    def handle(self, *args, **options):
        source = options["source"]
        taille_lot = options["taille_lot"]
        enregistrer_historique = not options["sans_historique"]

        self.stdout.write(
            self.style.MIGRATE_HEADING(
                f"\n🚀 Import catalogue — source: {source}, lot: {taille_lot}"
            )
        )

        historique = None
        if enregistrer_historique:
            url_source = (
                "https://fakestoreapi.com/products"
                if source == "fakestore"
                else options.get("chemin_csv", "fichier_local")
            )
            historique = HistoriqueImport.objects.create(source_url=url_source)

        try:
            if source == "fakestore":
                resultat = importer_catalogue_fakestore(
                    taille_lot=taille_lot,
                    historique=historique,
                )

            elif source == "csv":
                chemin_csv = options.get("chemin_csv")
                if not chemin_csv:
                    raise CommandError("--csv requis avec --source=csv")

                fichier = Path(chemin_csv)
                if not fichier.exists():
                    raise CommandError(f"Fichier introuvable : {chemin_csv}")

                # Détection automatique de l'encodage
                contenu = self._lire_csv_avec_encodage(fichier)
                resultat = importer_depuis_csv(contenu, taille_lot=taille_lot)

        except Exception as exc:
            if historique:
                historique.marquer_echec(str(exc))
            raise CommandError(f"Import échoué : {exc}") from exc

        # Rapport final
        self._afficher_rapport(resultat)

        if resultat.nb_erreurs > 0 and resultat.nb_traites == 0:
            sys.exit(1)

    def _lire_csv_avec_encodage(self, fichier: Path) -> str:
        """Tente UTF-8 puis Latin-1 comme fallback (encodages les plus courants)."""
        for encodage in ("utf-8-sig", "latin-1"):
            try:
                return fichier.read_text(encoding=encodage)
            except UnicodeDecodeError:
                continue
        raise CommandError(f"Encodage non supporté pour {fichier}")

    def _afficher_rapport(self, resultat) -> None:
        self.stdout.write("\n" + "─" * 50)
        self.stdout.write(
            self.style.SUCCESS(f"  ✅ Traités     : {resultat.nb_traites}")
        )
        self.stdout.write(
            self.style.SUCCESS(f"  ➕ Créés       : {resultat.nb_crees}")
        )
        self.stdout.write(
            self.style.SUCCESS(f"  🔄 Mis à jour  : {resultat.nb_mis_a_jour}")
        )
        if resultat.nb_erreurs:
            self.stdout.write(
                self.style.WARNING(f"  ⚠️  Erreurs     : {resultat.nb_erreurs}")
            )
            for erreur in resultat.erreurs[:5]:  # Limite l'affichage
                self.stdout.write(self.style.WARNING(f"     → {erreur}"))
        self.stdout.write(
            self.style.SUCCESS(f"  📊 Taux succès : {resultat.taux_succes}%")
        )
        self.stdout.write("─" * 50 + "\n")
