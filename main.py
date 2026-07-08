from collections import defaultdict
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from datetime import datetime

import models
from database import engine, get_db, Base

Base.metadata.create_all(bind=engine)

MONTHS = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
          "Jul", "Ago", "Set", "Out", "Nov", "Dez"]

SECTIONS = ["Food", "Other", "Accommodation"]

DEFAULT_CATEGORIES = {
    "Food":          ["restaurante", "mercado", "padaria", "açougue", "suplemento", "ifood", "café", "marmita", "outro"],
    "Other":         ["educação", "academia", "farmacia", "lazer", "terapia", "transporte", "uber", "doação",
                      "carreira", "moradia", "casa", "beleza", "juros", "viagem", "netflix", "bar", "presente",
                      "roupa", "saude", "massagem", "outro"],
    "Accommodation": ["aluguel", "luz", "internet", "condominio", "outro"],
}


def seed_categories(db: Session):
    for section, names in DEFAULT_CATEGORIES.items():
        for name in names:
            exists = db.query(models.Category).filter_by(name=name, section=section).first()
            if not exists:
                db.add(models.Category(name=name, section=section))
    db.commit()


@asynccontextmanager
async def lifespan(_: FastAPI):
    db = next(get_db())
    seed_categories(db)
    yield


app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


@app.get("/", response_class=HTMLResponse)
def root():
    now = datetime.now()
    return RedirectResponse(f"/{now.year}/{now.month}")


@app.get("/{year}/{month}", response_class=HTMLResponse)
def month_view(year: int, month: int, request: Request, db: Session = Depends(get_db)):
    expenses = (
        db.query(models.Expense)
        .filter_by(year=year, month=month)
        .order_by(models.Expense.day)
        .all()
    )

    grand_total = sum(e.amount for e in expenses)

    # Group totals by category > sub_category
    summary = defaultdict(lambda: defaultdict(float))
    for e in expenses:
        summary[e.category][e.sub_category] += e.amount

    section_totals = {cat: sum(subs.values()) for cat, subs in summary.items()}

    all_cats = db.query(models.Category).order_by(models.Category.section, models.Category.name).all()
    cats_by_section = defaultdict(list)
    for c in all_cats:
        cats_by_section[c.section].append(c)

    cats_json = {
        section: [{"id": c.id, "name": c.name} for c in cats]
        for section, cats in cats_by_section.items()
    }

    return templates.TemplateResponse(request, "index.html", {
        "year": year,
        "month": month,
        "months": MONTHS,
        "sections": SECTIONS,
        "expenses": expenses,
        "grand_total": grand_total,
        "summary": {cat: dict(sorted(subs.items(), key=lambda x: x[1], reverse=True))
                    for cat, subs in summary.items()},
        "section_totals": section_totals,
        "cats_by_section": cats_by_section,
        "cats_json": cats_json,
    })


@app.post("/expense/add")
def add_expense(
    year: int = Form(...),
    month: int = Form(...),
    day: int = Form(...),
    amount: float = Form(...),
    category: str = Form(...),
    sub_category: str = Form(...),
    description: str = Form(""),
    db: Session = Depends(get_db),
):
    entry = models.Expense(
        day=day, amount=amount, category=category,
        sub_category=sub_category, description=description,
        month=month, year=year,
    )
    db.add(entry)
    db.commit()
    return RedirectResponse(f"/{year}/{month}", status_code=303)


@app.post("/expense/edit/{entry_id}")
def edit_expense(
    entry_id: int,
    year: int = Form(...), month: int = Form(...),
    day: int = Form(...), amount: float = Form(...),
    category: str = Form(...), sub_category: str = Form(...),
    description: str = Form(""),
    db: Session = Depends(get_db),
):
    entry = db.query(models.Expense).filter_by(id=entry_id).first()
    if entry:
        entry.day = day
        entry.amount = amount
        entry.category = category
        entry.sub_category = sub_category
        entry.description = description
        db.commit()
    return RedirectResponse(f"/{year}/{month}", status_code=303)


@app.post("/expense/delete/{entry_id}")
def delete_expense(entry_id: int, year: int = Form(...), month: int = Form(...), db: Session = Depends(get_db)):
    db.query(models.Expense).filter_by(id=entry_id).delete()
    db.commit()
    return RedirectResponse(f"/{year}/{month}", status_code=303)


@app.post("/category/add")
def add_category(
    year: int = Form(...),
    month: int = Form(...),
    section: str = Form(...),
    name: str = Form(...),
    db: Session = Depends(get_db),
):
    name = name.strip()
    if name:
        exists = db.query(models.Category).filter_by(name=name, section=section).first()
        if not exists:
            db.add(models.Category(name=name, section=section))
            db.commit()
    return RedirectResponse(f"/{year}/{month}", status_code=303)


@app.post("/category/delete/{cat_id}")
def delete_category(cat_id: int, year: int = Form(...), month: int = Form(...), db: Session = Depends(get_db)):
    db.query(models.Category).filter_by(id=cat_id).delete()
    db.commit()
    return RedirectResponse(f"/{year}/{month}", status_code=303)


def _get_or_create_config(db: Session, year: int, month: int) -> models.PlanningConfig:
    config = db.query(models.PlanningConfig).first()
    if not config:
        config = models.PlanningConfig(starting_balance=0.0, starting_month=month, starting_year=year)
        db.add(config)
        db.commit()
        db.refresh(config)
    return config


def _month_range(start_month: int, start_year: int, n: int):
    """Gera n pares (month, year) a partir do mês inicial."""
    m, y = start_month, start_year
    for _ in range(n):
        yield m, y
        m += 1
        if m > 12:
            m = 1
            y += 1


def _get_planned_months(db: Session):
    return (
        db.query(models.PlannedMonth)
        .order_by(models.PlannedMonth.year, models.PlannedMonth.month)
        .all()
    )


def _accumulate_balances(db: Session, config: models.PlanningConfig, planned_months, up_to_month: int, up_to_year: int) -> float:
    """Soma os saldos de todos os meses planejados até o mês informado (exclusive)."""
    balance = config.starting_balance
    for pm in planned_months:
        if (pm.year, pm.month) >= (up_to_year, up_to_month):
            break
        entries = db.query(models.PlannedEntry).filter_by(month=pm.month, year=pm.year).all()
        balance += sum(e.amount for e in entries)
    return balance


@app.get("/planning", response_class=HTMLResponse)
def planning_root(db: Session = Depends(get_db)):
    planned = _get_planned_months(db)
    if planned:
        pm = planned[-1]  # vai para o último mês planejado
        return RedirectResponse(f"/planning/{pm.year}/{pm.month}")
    now = datetime.now()
    return RedirectResponse(f"/planning/{now.year}/{now.month}")


@app.get("/planning/{year}/{month}", response_class=HTMLResponse)
def planning_view(year: int, month: int, request: Request, db: Session = Depends(get_db)):
    config = _get_or_create_config(db, year, month)
    planned_months = _get_planned_months(db)

    entries = (
        db.query(models.PlannedEntry)
        .filter_by(month=month, year=year)
        .order_by(models.PlannedEntry.day)
        .all()
    )

    total_in  = sum(e.amount for e in entries if e.amount > 0)
    total_out = sum(e.amount for e in entries if e.amount < 0)
    saldo_mes = total_in + total_out

    saldo_anterior  = _accumulate_balances(db, config, planned_months, month, year)
    saldo_acumulado = saldo_anterior + saldo_mes

    # Projeção: todos os meses planejados com saldo acumulado
    projection = []
    running = config.starting_balance
    for pm in planned_months:
        month_entries = db.query(models.PlannedEntry).filter_by(month=pm.month, year=pm.year).all()
        running += sum(e.amount for e in month_entries)
        projection.append({
            "id": pm.id, "month": MONTHS[pm.month - 1], "year": pm.year,
            "saldo": running, "m": pm.month, "y": pm.year,
        })

    # Verifica se o mês atual tem um PlannedMonth registrado
    current_planned = db.query(models.PlannedMonth).filter_by(month=month, year=year).first()

    return templates.TemplateResponse(request, "planning.html", {
        "year": year, "month": month, "months": MONTHS,
        "entries": entries,
        "total_in": total_in, "total_out": total_out,
        "saldo_mes": saldo_mes, "saldo_anterior": saldo_anterior,
        "saldo_acumulado": saldo_acumulado,
        "projection": projection, "config": config,
        "current_planned": current_planned,
    })


@app.post("/planning/config")
def update_config(
    year: int = Form(...), month: int = Form(...),
    starting_balance: float = Form(...),
    db: Session = Depends(get_db),
):
    config = db.query(models.PlanningConfig).first()
    if config:
        config.starting_balance = starting_balance
    else:
        config = models.PlanningConfig(starting_balance=starting_balance, starting_month=month, starting_year=year)
        db.add(config)
    db.commit()
    return RedirectResponse(f"/planning/{year}/{month}", status_code=303)


@app.post("/planning/month/add")
def add_planned_month(
    month: int = Form(...), year: int = Form(...),
    db: Session = Depends(get_db),
):
    exists = db.query(models.PlannedMonth).filter_by(month=month, year=year).first()
    if not exists:
        db.add(models.PlannedMonth(month=month, year=year))

        # Busca o mês planejado imediatamente anterior a este
        from sqlalchemy import or_, and_
        prev = (
            db.query(models.PlannedMonth)
            .filter(
                or_(
                    models.PlannedMonth.year < year,
                    and_(models.PlannedMonth.year == year, models.PlannedMonth.month < month),
                )
            )
            .order_by(models.PlannedMonth.year.desc(), models.PlannedMonth.month.desc())
            .first()
        )

        if prev:
            # Copia todos os lançamentos fixos do mês anterior para o novo mês
            fixed = db.query(models.PlannedEntry).filter_by(
                month=prev.month, year=prev.year, is_fixed=True
            ).all()
            for fe in fixed:
                already = db.query(models.PlannedEntry).filter_by(
                    name=fe.name, day=fe.day, month=month, year=year
                ).first()
                if not already:
                    db.add(models.PlannedEntry(
                        day=fe.day, name=fe.name, amount=fe.amount,
                        month=month, year=year, is_fixed=True,
                    ))

        db.commit()
    return RedirectResponse(f"/planning/{year}/{month}", status_code=303)


@app.post("/planning/month/delete/{pm_id}")
def delete_planned_month(pm_id: int, db: Session = Depends(get_db)):
    pm = db.query(models.PlannedMonth).filter_by(id=pm_id).first()
    if pm:
        # Remove também todos os lançamentos do mês
        db.query(models.PlannedEntry).filter_by(month=pm.month, year=pm.year).delete()
        db.delete(pm)
        db.commit()
    # Redireciona para o primeiro mês planejado restante, ou /planning
    remaining = _get_planned_months(db)
    if remaining:
        r = remaining[0]
        return RedirectResponse(f"/planning/{r.year}/{r.month}", status_code=303)
    return RedirectResponse("/planning", status_code=303)


@app.post("/planning/entry/add")
def add_planned_entry(
    year: int = Form(...), month: int = Form(...),
    day: int = Form(...), name: str = Form(...),
    amount: float = Form(...), sign: str = Form("+"),
    is_fixed: bool = Form(False),
    db: Session = Depends(get_db),
):
    # sign="-" inverte o valor para negativo (gasto)
    final_amount = abs(amount) if sign == "+" else -abs(amount)

    if is_fixed:
        for m, y in _month_range(month, year, 12):
            exists = db.query(models.PlannedEntry).filter_by(name=name, day=day, month=m, year=y).first()
            if not exists:
                db.add(models.PlannedEntry(day=day, name=name, amount=final_amount, month=m, year=y, is_fixed=True))
    else:
        db.add(models.PlannedEntry(day=day, name=name, amount=final_amount, month=month, year=year, is_fixed=False))

    db.commit()
    return RedirectResponse(f"/planning/{year}/{month}", status_code=303)


@app.post("/planning/entry/edit/{item_id}")
def edit_planned_entry(
    item_id: int,
    year: int = Form(...), month: int = Form(...),
    day: int = Form(...), name: str = Form(...),
    amount: float = Form(...), sign: str = Form("+"),
    db: Session = Depends(get_db),
):
    entry = db.query(models.PlannedEntry).filter_by(id=item_id).first()
    if entry:
        entry.day = day
        entry.name = name
        entry.amount = abs(amount) if sign == "+" else -abs(amount)
        db.commit()
    return RedirectResponse(f"/planning/{year}/{month}", status_code=303)


@app.post("/planning/entry/delete/{item_id}")
def delete_planned_entry(item_id: int, year: int = Form(...), month: int = Form(...), db: Session = Depends(get_db)):
    db.query(models.PlannedEntry).filter_by(id=item_id).delete()
    db.commit()
    return RedirectResponse(f"/planning/{year}/{month}", status_code=303)


@app.post("/analyze/{year}/{month}")
async def analyze_month(year: int, month: int, db: Session = Depends(get_db)):
    import asyncio
    import queue
    import threading
    import json
    from fastapi.responses import StreamingResponse
    from analyze import run_analysis_stream

    q: queue.Queue = queue.Queue()

    def run_in_thread():
        for event in run_analysis_stream(db, month, year):
            q.put(event)
        q.put(None)  # sentinel de fim

    threading.Thread(target=run_in_thread, daemon=True).start()

    async def generate():
        while True:
            try:
                item = q.get_nowait()
            except queue.Empty:
                await asyncio.sleep(0.02)
                continue
            if item is None:
                break
            event_type, data = item
            yield f"data: {json.dumps({'type': event_type, 'content': data}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
