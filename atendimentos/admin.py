from django.contrib import admin

from .models import Atendimento


@admin.register(Atendimento)
class AtendimentoAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "cliente",
        "veiculo",
        "categoria",
        "status",
        "prioridade",
        "criado_em",
    )

    list_filter = (
        "status",
        "prioridade",
        "categoria",
    )

    search_fields = (
        "cliente__nome",
        "cliente__telefone",
        "veiculo__placa",
        "veiculo__modelo",
        "relato_cliente",
        "resumo",
    )

    readonly_fields = (
        "criado_em",
        "atualizado_em",
    )
