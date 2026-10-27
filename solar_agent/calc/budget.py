"""Budgets that add up by construction, and a check for budgets that were written by hand."""

from __future__ import annotations

from dataclasses import dataclass

from solar_agent.trace import Value, derive


@dataclass(frozen=True)
class LineItem:
    category: str
    description: str
    quantity: Value
    unit_price: Value

    @property
    def total(self) -> Value:
        return derive(
            self.description, self.unit_price.unit, "quantity x unit price",
            lambda q, p: q * p,
            q=self.quantity, p=self.unit_price,
        )


@dataclass(frozen=True)
class Budget:
    items: tuple[LineItem, ...]
    currency: str = "USD"

    def __post_init__(self) -> None:
        for item in self.items:
            if item.unit_price.unit != self.currency:
                raise ValueError(f"{item.description}: price in {item.unit_price.unit}, budget in {self.currency}")

    def categories(self) -> list[str]:
        return list(dict.fromkeys(item.category for item in self.items))

    def category_total(self, category: str) -> Value:
        lines = {f"line_{i}": item.total for i, item in enumerate(self.items) if item.category == category}
        if not lines:
            raise KeyError(category)
        return derive(f"Subtotal {category}", self.currency, "sum of line totals", lambda **kw: sum(kw.values()), **lines)

    def total(self) -> Value:
        subtotals = {f"cat_{i}": self.category_total(c) for i, c in enumerate(self.categories())}
        return derive("Total", self.currency, "sum of category subtotals", lambda **kw: sum(kw.values()), **subtotals)

    def shares(self) -> dict[str, float]:
        grand = self.total().value
        return {c: self.category_total(c).value / grand for c in self.categories()}


@dataclass(frozen=True)
class Discrepancy:
    where: str
    declared: float
    computed: float

    @property
    def difference(self) -> float:
        return self.declared - self.computed


def check_declared(declared_total: float, declared_parts: dict[str, float], where: str,
                   tolerance: float = 0.5) -> list[Discrepancy]:
    """Does a hand-written total match the sum of its parts? Used to audit existing proposals."""
    computed = sum(declared_parts.values())
    if abs(declared_total - computed) > tolerance:
        return [Discrepancy(where, declared_total, computed)]
    return []
