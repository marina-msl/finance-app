from sqlalchemy import Column, Integer, String, Float, Boolean, UniqueConstraint
from database import Base


class Expense(Base):
    __tablename__ = "expenses"

    id = Column(Integer, primary_key=True, index=True)
    day = Column(Integer, nullable=False)
    amount = Column(Float, nullable=False)
    category = Column(String, nullable=False)      # Food, Other, Accommodation
    sub_category = Column(String, nullable=False)  # mercado, educação, aluguel...
    description = Column(String, default="")
    month = Column(Integer, nullable=False)
    year = Column(Integer, nullable=False)


class FoodExpense(Base):
    __tablename__ = "food_expenses"

    id = Column(Integer, primary_key=True, index=True)
    day = Column(Integer, nullable=False)
    amount = Column(Float, nullable=False)
    category = Column(String, nullable=False)
    description = Column(String, default="")
    month = Column(Integer, nullable=False)
    year = Column(Integer, nullable=False)


class OtherExpense(Base):
    __tablename__ = "other_expenses"

    id = Column(Integer, primary_key=True, index=True)
    day = Column(Integer, nullable=False)
    name = Column(String, nullable=False)
    amount = Column(Float, nullable=False)
    category = Column(String, nullable=False)
    sub_description = Column(String, default="")
    month = Column(Integer, nullable=False)
    year = Column(Integer, nullable=False)


class Category(Base):
    __tablename__ = "categories"
    __table_args__ = (UniqueConstraint("name", "section"),)

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    section = Column(String, nullable=False)  # "food", "other", or "accom"


class AccommodationExpense(Base):
    __tablename__ = "accommodation_expenses"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    amount = Column(Float, nullable=False)
    month = Column(Integer, nullable=False)
    year = Column(Integer, nullable=False)


class PlannedEntry(Base):
    __tablename__ = "planned_entries"

    id = Column(Integer, primary_key=True, index=True)
    day = Column(Integer, nullable=False)
    name = Column(String, nullable=False)
    # positivo = receita, negativo = gasto
    amount = Column(Float, nullable=False)
    month = Column(Integer, nullable=False)
    year = Column(Integer, nullable=False)
    is_fixed = Column(Boolean, default=False)


class PlannedMonth(Base):
    __tablename__ = "planned_months"
    __table_args__ = (UniqueConstraint("month", "year"),)

    id = Column(Integer, primary_key=True, index=True)
    month = Column(Integer, nullable=False)
    year = Column(Integer, nullable=False)


class PlanningConfig(Base):
    __tablename__ = "planning_config"

    id = Column(Integer, primary_key=True, index=True)
    starting_balance = Column(Float, default=0.0)   # saldo inicial do primeiro mês planejado
    starting_month = Column(Integer, nullable=False)
    starting_year = Column(Integer, nullable=False)


class StudyDay(Base):
    __tablename__ = "study_days"
    __table_args__ = (UniqueConstraint("day", "month", "year"),)

    id = Column(Integer, primary_key=True, index=True)
    day = Column(Integer, nullable=False)
    month = Column(Integer, nullable=False)
    year = Column(Integer, nullable=False)
    studied = Column(Boolean, default=False)
    description = Column(String, default="")
