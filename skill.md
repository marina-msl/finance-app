# Finance App — Project Restoration Guide

## What this is
A FastAPI web application to replace a Google Sheets finance tracker.
Tracks 3 sections per month (like the sheet), stored in SQLite, rendered as a spreadsheet-like web UI.

## Tech stack
- **Backend**: FastAPI + SQLAlchemy (ORM) + SQLite (database file: `finance.db`)
- **Frontend**: Jinja2 HTML templates + plain CSS
- **Python venv**: `venv/` folder inside the project

## Project location
`C:\Users\marin\Documents\finance-app`

## File map
| File | Purpose |
|------|---------|
| `database.py` | SQLAlchemy engine + session + Base (do not modify) |
| `models.py` | 3 database table classes: FoodExpense, OtherExpense, AccommodationExpense |
| `main.py` | FastAPI app with all routes (GET page, POST add, POST delete) |
| `templates/index.html` | Jinja2 template — the spreadsheet-like UI |
| `static/style.css` | All CSS styling |
| `finance.db` | SQLite database (auto-created on first run) |

## Data model (3 sections)
### FoodExpense
- day (int), amount (float), category (str), description (str), month, year

### OtherExpense
- day (int), name (str), amount (float), category (str), sub_description (str), month, year

### AccommodationExpense
- name (str), amount (float), month, year

## Routes
- `GET /` - redirects to current month
- `GET /{year}/{month}` - renders the page with all 3 sections
- `POST /food/add` - add food row, redirects back
- `POST /food/delete/{id}` - delete food row
- `POST /other/add`, `POST /other/delete/{id}`
- `POST /accom/add`, `POST /accom/delete/{id}`

## How to run
```powershell
cd "C:\Users\marin\Documents\finance-app"
.\venv\Scripts\uvicorn main:app --reload
```
Then open http://127.0.0.1:8000 in browser.

## What still needs to be done / future ideas
- [ ] Edit rows (currently can only add or delete)
- [ ] Export to CSV
- [ ] Copy accommodation from previous month (for fixed costs)
- [ ] Charts / summary view

## Source of truth
The original Google Sheet had columns in this order:
Food (A-D) | Other/day (F-I) | Accommodation (J-K)
With totals at top and month tabs at the bottom.
