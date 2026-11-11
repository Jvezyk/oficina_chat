from django.contrib import admin

from django.contrib import admin

from agendamentos.models import Agendamento


@admin.register(Agendamento)
class AgendamentoAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "atendimento",
        "data_solicitada",
        "horario_solicitado",
        "periodo_preferido",
        "data_hora_confirmada",
        "status",
        "criado_em",
    )

    list_filter = (
        "status",
        "periodo_preferido",
        "data_solicitada",
    )

    search_fields = (
        "atendimento__cliente__nome",
        "atendimento__cliente__telefone",
        "atendimento__veiculo__placa",
    )