import requests

from django.core.management.base import BaseCommand

from atendimentos.models import Atendimento
from integracoes.trello.services import (
    sincronizar_status_trello_para_django,
)


class Command(BaseCommand):
    help = (
        "Sincroniza alterações realizadas no Trello "
        "com os Atendimentos do Django."
    )

    def handle(self, *args, **options):

        atendimentos = (
            Atendimento.objects
            .exclude(trello_card_id__isnull=True)
            .exclude(trello_card_id="")
        )

        total = atendimentos.count()

        alterados = 0
        sem_alteracao = 0
        agendamentos_pendentes = 0
        erros = 0

        self.stdout.write(
            f"Encontrados {total} atendimentos "
            "vinculados ao Trello."
        )

        # =====================================================
        # PERCORRER ATENDIMENTOS
        # =====================================================

        for atendimento in atendimentos:

            try:

                resultado = (
                    sincronizar_status_trello_para_django(
                        atendimento
                    )
                )

            # =================================================
            # ERRO DE COMUNICAÇÃO COM O TRELLO
            # =================================================

            except requests.RequestException as erro:

                erros += 1

                self.stderr.write(
                    self.style.ERROR(
                        f"Atendimento #{atendimento.id}: "
                        f"erro na API do Trello: {erro}"
                    )
                )

                continue

            # =================================================
            # OUTROS ERROS
            # =================================================

            except Exception as erro:

                erros += 1

                self.stderr.write(
                    self.style.ERROR(
                        f"Atendimento #{atendimento.id}: "
                        f"erro inesperado: {erro}"
                    )
                )

                continue

            # =================================================
            # ALGUMA ALTERAÇÃO FOI REALIZADA
            # =================================================

            if resultado.get("alterado"):

                alterados += 1

                motivo = resultado.get("motivo")

                # ---------------------------------------------
                # AGENDAMENTO CONFIRMADO
                # ---------------------------------------------

                if motivo == "agendamento_confirmado":

                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Atendimento #{atendimento.id}: "
                            "agendamento confirmado pela oficina."
                        )
                    )

                # ---------------------------------------------
                # AGENDAMENTO RECUSADO
                # ---------------------------------------------

                elif motivo == "agendamento_recusado":

                    self.stdout.write(
                        self.style.WARNING(
                            f"Atendimento #{atendimento.id}: "
                            "agendamento recusado. "
                            "Aguardando nova opção do cliente."
                        )
                    )

                # ---------------------------------------------
                # ALTERAÇÃO NORMAL DE STATUS
                # ---------------------------------------------

                else:

                    status_anterior = resultado.get(
                        "status_anterior"
                    )

                    status_novo = resultado.get(
                        "status_novo"
                    )

                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Atendimento #{atendimento.id}: "
                            f"{status_anterior} "
                            f"-> {status_novo}"
                        )
                    )

                continue

            # =================================================
            # NÃO HOUVE ALTERAÇÃO
            # =================================================

            motivo = resultado.get("motivo")

            # ---------------------------------------------
            # AGENDAMENTO AINDA NÃO TRATADO
            # ---------------------------------------------

            if motivo == "agendamento_requer_tratamento":

                agendamentos_pendentes += 1

                self.stdout.write(
                    self.style.WARNING(
                        f"Atendimento #{atendimento.id}: "
                        "agendamento precisa de tratamento."
                    )
                )

                continue

            # ---------------------------------------------
            # LISTA NÃO RECONHECIDA
            # ---------------------------------------------

            if motivo == "lista_desconhecida":

                sem_alteracao += 1

                self.stdout.write(
                    self.style.WARNING(
                        f"Atendimento #{atendimento.id}: "
                        f"lista não reconhecida: "
                        f"{resultado.get('lista')}"
                    )
                )

                continue

            # ---------------------------------------------
            # STATUS INTERNO PRESERVADO
            # ---------------------------------------------

            if motivo == "status_interno_preservado":

                sem_alteracao += 1

                continue

            # ---------------------------------------------
            # JÁ ESTAVA SINCRONIZADO
            # ---------------------------------------------

            if motivo == "status_ja_sincronizado":

                sem_alteracao += 1

                continue

            # ---------------------------------------------
            # QUALQUER OUTRO CASO
            # ---------------------------------------------

            sem_alteracao += 1

        # =====================================================
        # RESUMO FINAL
        # =====================================================

        self.stdout.write("")

        self.stdout.write(
            self.style.SUCCESS(
                "Sincronização concluída."
            )
        )

        self.stdout.write(
            f"Total analisado: {total}"
        )

        self.stdout.write(
            f"Status alterados: {alterados}"
        )

        self.stdout.write(
            f"Sem alteração: {sem_alteracao}"
        )

        self.stdout.write(
            f"Agendamentos aguardando tratamento: "
            f"{agendamentos_pendentes}"
        )

        self.stdout.write(
            f"Erros: {erros}"
        )