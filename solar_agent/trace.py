"""Traceable values: every number in a proposal knows where it came from.

A leaf value is *given*: measured on site, read from a datasheet, taken from a
standard, or assumed. A derived value carries its formula and the values it was
computed from. Nothing else exists, so a proposal can always be explained back
to its sources, and every assumption can be surfaced as an open question.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Iterator, Literal

SourceKind = Literal["measured", "datasheet", "standard", "dataset", "assumption"]


@dataclass(frozen=True)
class Source:
    kind: SourceKind
    ref: str  # where to check it: document + page, URL, standard + table, or who assumed it
    note: str = ""


@dataclass(frozen=True)
class Value:
    value: float
    unit: str
    label: str
    formula: str = ""
    inputs: tuple["Value", ...] = field(default_factory=tuple)
    source: Source | None = None

    @property
    def is_given(self) -> bool:
        return self.source is not None

    def __post_init__(self) -> None:
        if (self.source is None) == (not self.inputs):
            raise ValueError(f"{self.label}: a value is either given (with a source) or derived (with inputs)")


def given(value: float, unit: str, label: str, kind: SourceKind, ref: str, note: str = "") -> Value:
    return Value(float(value), unit, label, source=Source(kind, ref, note))


def assumed(value: float, unit: str, label: str, why: str) -> Value:
    """A value nobody measured. It is usable, but it becomes an open question in the proposal."""
    return given(value, unit, label, "assumption", why)


def derive(label: str, unit: str, formula: str, fn: Callable[..., float], **inputs: Value) -> Value:
    result = fn(**{name: v.value for name, v in inputs.items()})
    return Value(float(result), unit, label, formula=formula, inputs=tuple(inputs.values()))


def leaves(v: Value) -> Iterator[Value]:
    if v.is_given:
        yield v
        return
    for child in v.inputs:
        yield from leaves(child)


def open_questions(*values: Value) -> list[Value]:
    """Assumptions behind the given values, deduplicated: what a person must confirm before signing."""
    seen: dict[tuple[str, float], Value] = {}
    for v in values:
        for leaf in leaves(v):
            if leaf.source and leaf.source.kind == "assumption":
                seen.setdefault((leaf.label, leaf.value), leaf)
    return list(seen.values())


def fmt(v: Value) -> str:
    n = f"{v.value:,.0f}" if abs(v.value) >= 100 else f"{v.value:,.3g}"
    return f"{n} {v.unit}".strip()


def explain(v: Value, indent: int = 0) -> str:
    pad = "  " * indent
    if v.is_given:
        s = v.source
        return f"{pad}{v.label} = {fmt(v)}  [{s.kind}: {s.ref}]"
    lines = [f"{pad}{v.label} = {fmt(v)}  ({v.formula})"]
    lines += [explain(child, indent + 1) for child in v.inputs]
    return "\n".join(lines)
