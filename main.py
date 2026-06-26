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
