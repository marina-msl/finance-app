"""MCP Server do Finance App — conecta ao Claude Desktop."""
import os
import sys
from collections import defaultdict
from datetime import datetime

# Garante que o diretório do projeto está no path E é o diretório de trabalho
# (necessário para o banco SQLite relativo funcionar)
PROJECT_DIR = r"C:\Users\marin\Documents\finance-app"
os.chdir(PROJECT_DIR)
sys.path.insert(0, PROJECT_DIR)

from dotenv import load_dotenv
load_dotenv(os.path.join(PROJECT_DIR, ".env"))

from mcp.server.fastmcp import FastMCP
from database import SessionLocal
import models

mcp = FastMCP("Finance App 💰")

MONTHS_PT = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
             "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]

CATEGORIES = {
    "Food":          ["restaurante", "mercado", "padaria", "açougue", "suplemento", "ifood", "café", "marmita", "outro"],
    "Other":         ["educação", "academia", "farmacia", "lazer", "terapia", "transporte", "uber", "doação",
                      "carreira", "moradia", "casa", "beleza", "juros", "viagem", "netflix", "roupa", "saude", "massagem", "outro"],
    "Accommodation": ["aluguel", "luz", "internet", "condominio", "outro"],
}


@mcp.tool()
def add_expense(
    amount: float,
    sub_category: str,
    category: str = "Other",
    day: int = 0,
    description: str = "",
    month: int = 0,
    year: int = 0,
) -> str:
    """
    Adiciona um gasto no finance app.

    Parâmetros:
    - amount: valor em reais (ex: 45.50)
    - sub_category: tipo do gasto (ex: mercado, uber, restaurante, netflix...)
    - category: "Food", "Other" ou "Accommodation" (padrão: "Other")
    - day: dia do mês (padrão: dia de hoje)
    - description: descrição extra (ex: "ifood pizza")
    - month: mês 1-12 (padrão: mês atual)
    - year: ano (padrão: ano atual)
    """
    now = datetime.now()
    day   = day   or now.day
    month = month or now.month
    year  = year  or now.year

    db = SessionLocal()
    try:
        entry = models.Expense(
            day=day, amount=amount, category=category,
            sub_category=sub_category, description=description,
            month=month, year=year,
        )
        db.add(entry)
        db.commit()
        db.refresh(entry)
        mes = MONTHS_PT[month - 1]
        return (
            f"✅ Adicionado!\n"
            f"   {sub_category} — R$ {amount:.2f}\n"
            f"   Dia {day} de {mes} {year}\n"
            f"   ID: {entry.id}"
        )
    finally:
        db.close()


@mcp.tool()
def get_month_summary(month: int = 0, year: int = 0) -> str:
    """
    Mostra o resumo de gastos de um mês com totais por categoria.
    Se não informar mês/ano, usa o mês atual.
    """
    now = datetime.now()
    month = month or now.month
    year  = year  or now.year

    db = SessionLocal()
    try:
        expenses = db.query(models.Expense).filter_by(month=month, year=year).all()
        mes = MONTHS_PT[month - 1]

        if not expenses:
            return f"Nenhum gasto registrado em {mes} {year}."

        summary = defaultdict(lambda: defaultdict(float))
        for e in expenses:
            summary[e.category][e.sub_category] += e.amount

        total = sum(e.amount for e in expenses)
        lines = [f"📊 {mes} {year} — Total: R$ {total:.2f}\n"]

        for cat, subs in summary.items():
            cat_total = sum(subs.values())
            lines.append(f"\n{cat}  (R$ {cat_total:.2f})")
            for sub, amt in sorted(subs.items(), key=lambda x: -x[1]):
                lines.append(f"  • {sub}: R$ {amt:.2f}")

        return "\n".join(lines)
    finally:
        db.close()


@mcp.tool()
def list_expenses(month: int = 0, year: int = 0, category: str = "", limit: int = 20) -> str:
    """
    Lista os gastos de um mês, do mais recente para o mais antigo.
    Parâmetros opcionais:
    - category: filtra por "Food", "Other" ou "Accommodation"
    - limit: máximo de itens retornados (padrão 20)
    """
    now = datetime.now()
    month = month or now.month
    year  = year  or now.year

    db = SessionLocal()
    try:
        query = db.query(models.Expense).filter_by(month=month, year=year)
        if category:
            query = query.filter_by(category=category)
        expenses = query.order_by(models.Expense.id.desc()).limit(limit).all()

        mes = MONTHS_PT[month - 1]
        if not expenses:
            return f"Nenhum gasto em {mes} {year}."

        lines = [f"📋 {mes} {year}:\n"]
        for e in expenses:
            desc = f" ({e.description})" if e.description else ""
            lines.append(f"[{e.id}] Dia {e.day:>2} • {e.sub_category}{desc} — R$ {e.amount:.2f}")

        return "\n".join(lines)
    finally:
        db.close()


@mcp.tool()
def delete_expense(expense_id: int) -> str:
    """Remove um gasto pelo ID. Use list_expenses para ver os IDs."""
    db = SessionLocal()
    try:
        entry = db.query(models.Expense).filter_by(id=expense_id).first()
        if not entry:
            return f"❌ Gasto ID {expense_id} não encontrado."
        info = f"{entry.sub_category} R$ {entry.amount:.2f} (dia {entry.day}/{entry.month})"
        db.delete(entry)
        db.commit()
        return f"🗑️ Removido: {info} [ID {expense_id}]"
    finally:
        db.close()


@mcp.tool()
def list_categories() -> str:
    """Mostra todas as categorias e sub-categorias disponíveis."""
    lines = ["📂 Categorias disponíveis:\n"]
    for cat, subs in CATEGORIES.items():
        lines.append(f"\n{cat}:")
        lines.append("  " + ", ".join(subs))
    return "\n".join(lines)


if __name__ == "__main__":
    mcp.run()
