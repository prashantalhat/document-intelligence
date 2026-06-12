"""Pydantic schema for rental statement extraction.

This model is used both as a Docling extraction template and as
a validation target for the tagged output.
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel, Field


class RentalLineItem(BaseModel):
    """A single charge or credit on a rental statement."""

    description: str = Field(default="", examples=["Monthly Rent"])
    amount: float = Field(default=0.0, examples=[1500.00])
    date: Optional[str] = Field(default=None, examples=["2025-01-01"])
    category: Optional[str] = Field(default=None, examples=["rent", "utility", "fee"])


class RentalStatement(BaseModel):
    """Top-level schema for a residential rental / property statement."""

    # -- parties --
    tenant_name: Optional[str] = Field(default=None, examples=["Jane Doe"])
    landlord_name: Optional[str] = Field(default=None, examples=["Acme Properties LLC"])

    # -- property --
    property_address: Optional[str] = Field(
        default=None, examples=["123 Main St, Apt 4B, Springfield, IL 62704"]
    )
    unit_number: Optional[str] = Field(default=None, examples=["4B"])

    # -- statement period --
    statement_date: Optional[str] = Field(default=None, examples=["2025-01-15"])
    period_start: Optional[str] = Field(default=None, examples=["2025-01-01"])
    period_end: Optional[str] = Field(default=None, examples=["2025-01-31"])

    # -- financials --
    rent_amount: Optional[float] = Field(default=None, examples=[1500.00])
    total_charges: Optional[float] = Field(default=None, examples=[1650.00])
    total_payments: Optional[float] = Field(default=None, examples=[1500.00])
    balance_due: Optional[float] = Field(default=None, examples=[150.00])
    previous_balance: Optional[float] = Field(default=None, examples=[0.00])

    # -- line items --
    line_items: list[RentalLineItem] = Field(default_factory=list)

    # -- payment info --
    payment_due_date: Optional[str] = Field(default=None, examples=["2025-02-01"])
    payment_method: Optional[str] = Field(default=None, examples=["ACH", "Check"])
    account_number: Optional[str] = Field(default=None, examples=["ACCT-9832"])
