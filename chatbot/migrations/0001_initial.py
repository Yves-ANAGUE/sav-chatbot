"""Migration initiale du chatbot."""
import uuid
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("catalogue", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="ConversationSAV",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True)),
                ("uuid", models.UUIDField(db_index=True, default=uuid.uuid4, unique=True)),
                ("cree_le", models.DateTimeField(auto_now_add=True)),
                ("modifie_le", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Conversation SAV",
                "verbose_name_plural": "Conversations SAV",
                "ordering": ["-modifie_le"],
            },
        ),
        migrations.CreateModel(
            name="MessageSAV",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True)),
                (
                    "conversation",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="messages",
                        to="chatbot.conversationsav",
                    ),
                ),
                (
                    "role",
                    models.CharField(
                        choices=[("user", "Utilisateur"), ("assistant", "Assistant")],
                        max_length=20,
                    ),
                ),
                ("contenu", models.TextField()),
                (
                    "produits_references",
                    models.ManyToManyField(
                        blank=True,
                        related_name="messages_sav",
                        to="catalogue.produit",
                    ),
                ),
                ("cree_le", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "verbose_name": "Message SAV",
                "verbose_name_plural": "Messages SAV",
                "ordering": ["cree_le"],
            },
        ),
    ]
