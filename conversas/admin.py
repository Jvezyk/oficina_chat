from django.contrib import admin
from .models import Conversa, Mensagem


@admin.register(Conversa)
class ConversaAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "cliente",
        "canal",
        "status",
        "iniciada_em",
        "atualizada_em",
    )

    list_filter = (
        "canal",
        "status",
    )

    search_fields = (
        "cliente__nome",
        "cliente__telefone",
    )


@admin.register(Mensagem)
class MensagemAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "conversa",
        "remetente",
        "tipo",
        "processada_por_ia",
        "criada_em",
    )

    list_filter = (
        "remetente",
        "tipo",
        "processada_por_ia",
    )

    search_fields = (
        "conteudo",
        "conversa__cliente__nome",
        "conversa__cliente__telefone",
    )