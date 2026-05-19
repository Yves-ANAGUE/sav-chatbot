from django.contrib import admin
from .models import ConversationSAV, MessageSAV


class MessageSAVInline(admin.TabularInline):
    model = MessageSAV
    extra = 0
    readonly_fields = ("role", "contenu", "cree_le")
    can_delete = False


@admin.register(ConversationSAV)
class ConversationSAVAdmin(admin.ModelAdmin):
    list_display = ("uuid", "nb_messages", "cree_le", "modifie_le")
    readonly_fields = ("uuid", "cree_le", "modifie_le")
    inlines = [MessageSAVInline]

    def nb_messages(self, obj):
        return obj.messages.count()
    nb_messages.short_description = "Messages"


@admin.register(MessageSAV)
class MessageSAVAdmin(admin.ModelAdmin):
    list_display = ("conversation", "role", "apercu_contenu", "cree_le")
    list_filter = ("role",)
    readonly_fields = ("conversation", "role", "contenu", "produits_references", "cree_le")

    def apercu_contenu(self, obj):
        return obj.contenu[:80]
    apercu_contenu.short_description = "Contenu"
