"""Agentic workflow com streaming: GPT analisa gastos usando tools e transmite a resposta em tempo real."""
import calendar
import json
import os
from collections import defaultdict

from dotenv import load_dotenv
from openai import OpenAI
from sqlalchemy.orm import Session

import models

load_dotenv()

MONTHS_PT = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
             "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]

# ── Tools: funções que o modelo pode chamar ───────────────────────────────────

def _get_month_summary(db: Session, month: int, year: int) -> dict:
    expenses = db.query(models.Expense).filter_by(month=month, year=year).all()
    summary = defaultdict(lambda: defaultdict(float))
    for e in expenses:
        summary[e.category][e.sub_category] += e.amount
    return {
        "month": MONTHS_PT[month - 1],
        "year": year,
        "total_geral": round(sum(e.amount for e in expenses), 2),
        "por_secao": {
            cat: {
                "total": round(sum(subs.values()), 2),
                "por_categoria": {sub: round(amt, 2) for sub, amt in sorted(subs.items(), key=lambda x: -x[1])}
            }
            for cat, subs in summary.items()
        }
    }

def _get_expenses_detail(db: Session, month: int, year: int, category: str) -> list:
    expenses = (
        db.query(models.Expense)
        .filter_by(month=month, year=year, category=category)
        .order_by(models.Expense.amount.desc())
        .all()
    )
    return [
        {"dia": e.day, "sub_categoria": e.sub_category, "valor": e.amount, "descricao": e.description}
        for e in expenses
    ]

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_month_summary",
            "description": "Retorna o resumo dos gastos do mês: total geral e totais por seção e sub-categoria.",
            "parameters": {
                "type": "object",
                "properties": {
                    "month": {"type": "integer", "description": "Mês (1-12)"},
                    "year":  {"type": "integer", "description": "Ano (ex: 2026)"}
                },
                "required": ["month", "year"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_expenses_detail",
            "description": "Retorna a lista detalhada de lançamentos de uma seção específica do mês.",
            "parameters": {
                "type": "object",
                "properties": {
                    "month":    {"type": "integer"},
                    "year":     {"type": "integer"},
                    "category": {"type": "string", "enum": ["Food", "Other", "Accommodation"]}
                },
                "required": ["month", "year", "category"]
            }
        }
    }
]

CATEGORY_LABELS = {"Food": "Alimentação", "Other": "Outros", "Accommodation": "Moradia"}

# ── Generator: yields (type, data) para SSE ──────────────────────────────────

def run_analysis_stream(db: Session, month: int, year: int):
    """
    Yields tuplas (tipo, conteúdo):
      ("status", "mensagem")  → passo atual do agente
      ("chunk",  "texto")     → pedaço do texto final em streaming
      ("error",  "mensagem")  → erro
      ("done",   "")          → finalizado
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        yield ("error", "OPENAI_API_KEY não encontrada.")
        return

    client = OpenAI(api_key=api_key)
    nome_mes = MONTHS_PT[month - 1]

    messages = [{
        "role": "user",
        "content": (
            f"Analise meus gastos de {nome_mes} {year}. "
            "Use as tools para buscar os dados que precisar. "
            "Escreva a análise em português com:\n"
            "1) Visão geral (total e divisão por seção)\n"
            "2) Onde gastei mais (top categorias)\n"
            "3) Observações importantes\n"
            "4) 2 sugestões de economia\n"
            "Seja direto e use valores em R$."
        )
    }]

    # ── Fase 1: loop de tool calls (sem streaming) ────────────────────────────
    yield ("status", f"🤔 Iniciando análise de {nome_mes}...")

    while True:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            max_tokens=500,
            tools=TOOLS,
            messages=messages,
        )

        message = response.choices[0].message
        finish_reason = response.choices[0].finish_reason

        if finish_reason != "tool_calls":
            break  # GPT não quer mais chamar tools → vai para fase 2

        messages.append(message)

        for tool_call in message.tool_calls:
            name = tool_call.function.name
            args = json.loads(tool_call.function.arguments)

            # Mostra o que o agente está fazendo
            if name == "get_month_summary":
                yield ("status", f"📊 Buscando resumo de {nome_mes}...")
            elif name == "get_expenses_detail":
                label = CATEGORY_LABELS.get(args.get("category", ""), args.get("category", ""))
                yield ("status", f"🔍 Detalhando {label}...")

            # Executa a tool
            if name == "get_month_summary":
                result = _get_month_summary(db, args["month"], args["year"])
            elif name == "get_expenses_detail":
                result = _get_expenses_detail(db, args["month"], args["year"], args["category"])
            else:
                result = {"erro": "tool desconhecida"}

            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": json.dumps(result, ensure_ascii=False)
            })

    # ── Fase 2: gera e transmite a análise final em streaming ─────────────────
    yield ("status", "✍️ Redigindo análise...")

    stream = client.chat.completions.create(
        model="gpt-4o-mini",
        max_tokens=1500,
        messages=messages,
        stream=True,
    )

    for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            yield ("chunk", delta)

    yield ("done", "")


def run_study_analysis_stream(db: Session, month: int, year: int):
    """Mesmo contrato de eventos de run_analysis_stream, mas avalia os estudos do mês."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        yield ("error", "OPENAI_API_KEY não encontrada.")
        return

    nome_mes = MONTHS_PT[month - 1]
    days_in_month = calendar.monthrange(year, month)[1]

    records = (
        db.query(models.StudyDay)
        .filter_by(year=year, month=month)
        .order_by(models.StudyDay.day)
        .all()
    )
    studied = [r for r in records if r.studied and r.description]

    if not studied:
        yield ("error", f"Nenhum dia estudado registrado em {nome_mes} {year} ainda.")
        return

    percent = round(len(studied) / days_in_month * 100, 1) if days_in_month else 0
    dias_texto = "\n".join(f"Dia {r.day}: {r.description}" for r in studied)

    client = OpenAI(api_key=api_key)

    yield ("status", f"📚 Analisando estudos de {nome_mes}...")

    messages = [{
        "role": "user",
        "content": (
            f"Aqui está meu registro de estudos de {nome_mes} {year} "
            f"({len(studied)} de {days_in_month} dias estudados, {percent}%):\n\n"
            f"{dias_texto}\n\n"
            "Com base nisso, escreva uma avaliação em português com:\n"
            "1) Quais temas/assuntos venho estudando (agrupe e identifique os principais)\n"
            "2) Consistência: dias seguidos, intervalos sem estudar, padrão observado\n"
            "3) Pontos de atenção (ex: um tema dominando demais, pouca variedade)\n"
            "4) 2 sugestões práticas para melhorar a rotina de estudo\n"
            "Seja direto e específico, citando os temas que encontrar no texto."
        )
    }]

    yield ("status", "✍️ Redigindo avaliação...")

    stream = client.chat.completions.create(
        model="gpt-4o-mini",
        max_tokens=1200,
        messages=messages,
        stream=True,
    )

    for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            yield ("chunk", delta)

    yield ("done", "")
