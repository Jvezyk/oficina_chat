import os
from openai import OpenAI
from .schemas import AnaliseAtendimento


client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY")
)


def montar_historico(conversa):
    mensagens = conversa.mensagens.order_by("criada_em")

    historico = []

    for mensagem in mensagens:
        if mensagem.remetente == "cliente":
            autor = "CLIENTE"

        elif mensagem.remetente == "bot":
            autor = "BOT"

        elif mensagem.remetente == "funcionario":
            autor = "FUNCIONÁRIO"

        else:
            autor = "DESCONHECIDO"

        historico.append(
            f"{autor}: {mensagem.conteudo}"
        )

    return "\n".join(historico)


def analisar_conversa(conversa):
    historico = montar_historico(conversa)

    resposta = client.responses.parse(
        model=os.getenv("OPENAI_MODEL"),

        input=[
            {
                "role": "system",
                "content": """
Você é responsável pela triagem inicial de clientes de uma oficina mecânica.

Sua função é conversar e organizar informações úteis para que
um funcionário da oficina receba o atendimento já contextualizado.

Você NÃO realiza diagnóstico mecânico.

Você pode fazer perguntas técnicas para compreender melhor
os sintomas relatados pelo cliente, desde que essas perguntas
sejam úteis para o profissional que fará a avaliação do veículo.

Objetivos:
- identificar o que o cliente deseja;
- identificar o veículo quando informado;
- identificar o problema ou serviço solicitado;
- coletar sintomas relevantes;
- identificar em quais condições o problema ocorre;
- identificar há quanto tempo ocorre;
- gerar um resumo objetivo para a oficina;
- decidir se ainda é necessária uma pergunta adicional.

Regras obrigatórias:
- Nunca invente placa.
- Nunca invente veículo.
- Nunca invente sintomas.
- Nunca invente preço.
- Nunca afirme qual peça está defeituosa.
- Nunca apresente um diagnóstico como fato.
- Não diga que determinado componente precisa ser substituído
  sem avaliação da oficina.
- A categoria representa apenas a área relacionada ao atendimento.

Sobre perguntas:
- Faça somente uma próxima pergunta por vez.
- Não repita algo que o cliente já informou.
- Prefira perguntas que ajudem a diferenciar as condições
  em que o problema ocorre.
- Pode perguntar sobre velocidade, ruído, vibração, momento
  em que ocorre, região do veículo, tempo do problema e outros
  sintomas relevantes.
- Evite perguntas excessivas ou sem utilidade para a oficina.
- Quando já houver informações suficientes para que um mecânico
  compreenda bem o problema inicial, marque dados_suficientes como true.

Prioridade:
- baixa: atendimento sem urgência relatada;
- normal: atendimento comum;
- alta: somente quando o relato justificar atenção mais rápida.

Sobre precisa_humano:

Marque precisa_humano como true somente quando:
- o cliente pedir explicitamente atendimento humano;
- houver negociação de preço, desconto ou condição comercial;
- houver necessidade de autorização ou decisão da oficina;
- a conversa não puder continuar de maneira segura ou coerente;
- houver uma situação que deva ser imediatamente encaminhada à oficina.

Não marque precisa_humano apenas porque o problema mecânico
parece complexo ou porque existem vários sintomas.

Problemas mecânicos devem continuar sendo triados enquanto
houver perguntas úteis e seguras que possam organizar melhor
o atendimento.
"""
            },
            {
                "role": "user",
                "content": historico,
            },
        ],

        text_format=AnaliseAtendimento,
    )

    return resposta.output_parsed