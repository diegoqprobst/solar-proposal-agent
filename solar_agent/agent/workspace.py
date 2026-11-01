"""What the agent can do to a case, and the checks that keep it honest.

The model fills in values; it never computes and never decides what counts as proven.
A value is accepted only if it passes one of these:

* measured / datasheet / standard: it must cite a document of the case and quote it. The quote has
  to appear in that document, and the value has to appear in the quote.
* assumption: allowed, but it must say why, and it becomes an open question for a person.

`dataset` values come only from code (NASA POWER); the model cannot set them.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from solar_agent import case as case_mod
from solar_agent import llm
from solar_agent import sizing, solar_resource
from solar_agent.trace import Value

CITED_KINDS = ("measured", "datasheet", "standard")
MODEL_KINDS = CITED_KINDS + ("assumption", "image")
# Fractions between 0 and 1: 45 % is 0.45. The model once recorded 45, which would have broken the sizing.
FRACTION_FIELDS = {("pumping", "wire_to_water_eff"), ("system", "performance_ratio"),
                   ("system", "depth_of_discharge"), ("system", "battery_efficiency")}
NUMBER = re.compile(r"\d+(?:[.,]\d+)?")


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def numbers_in(text: str) -> list[float]:
    return [float(n.replace(",", ".")) for n in NUMBER.findall(text)]


def value_in_quote(value: float, quote: str) -> bool:
    """The value appears in the quote as written, or as a percentage (45 % -> 0.45)."""
    return any(abs(n - value) < 1e-9 or abs(n / 100 - value) < 1e-9 for n in numbers_in(quote))


@dataclass
class Workspace:
    case: dict
    documents: dict[str, str]
    solar_fetcher: Callable[[float, float], dict] = solar_resource.fetch
    questions: list[dict] = field(default_factory=list)
    events: list[dict] = field(default_factory=list)
    design: sizing.Design | None = None
    images: dict[str, Path] = field(default_factory=dict)
    unreadable: list[str] = field(default_factory=list)
    pending_images: list[tuple[str, Path]] = field(default_factory=list)
    _last_status: str = ""

    # ---- tools exposed to the model; each returns a JSON-serialisable dict ----

    def get_status(self) -> dict:
        have, missing, optional = {}, [], []
        for section, fields in case_mod.FIELDS.items():
            for key, (_, label) in fields.items():
                raw = self.case.get(section, {}).get(key)
                if raw is None:
                    item = {"section": section, "field": key, "label": label}
                    (optional if section in case_mod.OPTIONAL_SECTIONS else missing).append(item)
                else:
                    have.setdefault(section, {})[key] = {"value": raw["value"], "kind": raw["kind"]}
        status = {"documents": sorted(self.documents), "images": sorted(self.images), "site": self.case.get("site", {}),
                  "have": have, "missing_required": missing, "missing_optional_only_for_co2": optional,
                  "open_questions_for_human": self.questions}
        if self.unreadable:
            status["unreadable_documents"] = {"files": self.unreadable, "note": "scanned PDFs with no text layer; "
                                              "a person must provide the values or a photo of the page"}
        signature = json.dumps([have, len(self.questions), len(self.events)], sort_keys=True)
        if signature == self._last_status:
            status["note"] = ("Nothing changed since your last get_status. Do not call it again: record the missing "
                              "inputs (as assumptions with a reason if no document gives them), or call size_system.")
        self._last_status = signature
        return status

    def read_document(self, name: str) -> dict:
        if name not in self.documents:
            return {"error": f"no such document: {name!r}", "documents": sorted(self.documents)}
        return {"name": name, "text": self.documents[name]}

    def read_image(self, name: str) -> dict:
        """Queue a photo so the loop shows it to the model in the next message."""
        if name not in self.images:
            return {"error": f"no such image: {name!r}", "images": sorted(self.images)}
        if self.images[name].stat().st_size > llm.MAX_IMAGE_BYTES:
            return {"error": f"{name} is larger than {llm.MAX_IMAGE_BYTES // 1_000_000} MB; a person must resize it"}
        self.pending_images.append((name, self.images[name]))
        return {"name": name, "note": "the image is attached in the next message"}

    def set_value(self, section: str, field: str, value: float, kind: str, why_or_quote: str,
                  document: str = "") -> dict:
        label_info = case_mod.FIELDS.get(section, {}).get(field)
        if label_info is None:
            return self._reject(section, field, f"unknown field; valid: {self._valid_fields()}")
        if kind not in MODEL_KINDS:
            return self._reject(section, field, f"kind must be one of {MODEL_KINDS}; 'dataset' is set by code only")
        try:
            value = float(value)
        except (TypeError, ValueError):
            return self._reject(section, field, "value must be a number")
        if (section, field) in FRACTION_FIELDS and not 0 < value <= 1:
            return self._reject(section, field, f"{field} is a fraction between 0 and 1 (45 % is 0.45); got {value}")
        if kind == "image":
            if document not in self.images:
                return self._reject(section, field, f"cite an image of the case; have: {sorted(self.images)}")
            if len(why_or_quote.strip()) < 10:
                return self._reject(section, field, "describe what is visible in the photo that gives this value")
            ref = f"photo {document}: {why_or_quote.strip()}"
        elif kind == "assumption":
            if len(why_or_quote.strip()) < 10:
                return self._reject(section, field, "an assumption needs a reason of at least a sentence")
            ref = why_or_quote.strip()
        else:
            if document not in self.documents:
                return self._reject(section, field, f"cite a document of the case; have: {sorted(self.documents)}")
            if _norm(why_or_quote) not in _norm(self.documents[document]):
                return self._reject(section, field, "the quote does not appear in that document; copy it exactly")
            if not value_in_quote(value, why_or_quote):
                return self._reject(section, field, f"the value {value} does not appear in the quote")
            ref = f"{document}: \"{why_or_quote.strip()}\""
        self.case.setdefault(section, {})[field] = {"value": value, "kind": kind, "ref": ref}
        self.events.append({"event": "set", "section": section, "field": field, "value": value, "kind": kind, "ref": ref})
        return {"accepted": True, "section": section, "field": field, "value": value, "kind": kind}

    def ask_human(self, question: str, why: str) -> dict:
        """What cannot be proven from the documents goes to a person, never into a guess."""
        item = {"question": question.strip(), "why": why.strip()}
        self.questions.append(item)
        self.events.append({"event": "ask_human", **item})
        return {"recorded": True, "open_questions": len(self.questions)}

    def get_solar_resource(self) -> dict:
        site = self.case.get("site", {})
        if "latitude" not in site or "longitude" not in site:
            return {"error": "the case has no site coordinates; ask a person for them"}
        try:
            payload = self.solar_fetcher(site["latitude"], site["longitude"])
            psh = solar_resource.design_peak_sun_hours(payload, site["latitude"], site["longitude"])
        except Exception as e:
            return {"error": f"NASA POWER unavailable: {type(e).__name__}: {e}"}
        self.case.setdefault("solar", {})["design_psh"] = {
            "value": psh.value, "kind": "dataset", "ref": psh.source.ref, "note": psh.source.note}
        self.events.append({"event": "solar_resource", "value": psh.value, "label": psh.label})
        return {"design_peak_sun_hours": psh.value, "label": psh.label}

    def size_system(self) -> dict:
        try:
            self.design = sizing.size(self.case)
        except case_mod.MissingData as e:
            return {"sized": False, "missing": e.missing}
        except ValueError as e:
            return {"sized": False, "error": f"an input is out of range: {e}"}
        results = {v.label: {"value": round(v.value, 3), "unit": v.unit} for v in self.design.results()}
        questions = [{"label": q.label, "value": q.value, "why": q.source.ref} for q in self.design.open_questions()]
        self.events.append({"event": "sized", "results": results})
        return {"sized": True, "results": results, "assumptions_a_person_must_confirm": questions}

    # ---- outputs written by code, never by the model ----

    def proposal(self) -> str:
        if self.design is None:
            return "# Proposal not produced\n\nThe system could not be sized from the information available.\n" + self._questions_md()
        return sizing.report(self.design) + self._questions_md()

    def _questions_md(self) -> str:
        if not self.questions:
            return ""
        lines = ["", "## Questions for a person (the agent could not prove these)", ""]
        lines += [f"- **{q['question']}** {q['why']}" for q in self.questions]
        return "\n".join(lines) + "\n"

    def trace_json(self) -> str:
        return json.dumps({"events": self.events, "case": self.case}, indent=2, ensure_ascii=False)

    # ---- helpers ----

    def _valid_fields(self) -> dict:
        return {s: list(f) for s, f in case_mod.FIELDS.items()}

    def _reject(self, section: str, field: str, reason: str) -> dict:
        self.events.append({"event": "rejected", "section": section, "field": field, "reason": reason})
        return {"accepted": False, "reason": reason}


MIN_PDF_TEXT = 40


def pdf_text(path: Path) -> str:
    """Text of a PDF with page markers. Empty for scanned PDFs: nothing to quote, so nothing is guessed."""
    from pypdf import PdfReader

    pages = [(page.extract_text() or "").strip() for page in PdfReader(str(path)).pages]
    text = "\n".join(f"[page {i}]\n{t}" for i, t in enumerate(pages, 1) if t)
    return text if len(text.replace("\n", "")) >= MIN_PDF_TEXT else ""


def load_workspace(case_dir: str | Path, **kwargs) -> tuple[Workspace, str]:
    root = Path(case_dir)
    objective = (root / "objective.md").read_text(encoding="utf-8")
    case = json.loads((root / "site.json").read_text(encoding="utf-8")) if (root / "site.json").is_file() else {}
    files = sorted((root / "documents").glob("*"))
    docs = {p.name: p.read_text(encoding="utf-8") for p in files if p.suffix in (".txt", ".md")}
    unreadable = []
    for p in files:
        if p.suffix.lower() == ".pdf":
            text = pdf_text(p)
            if text:
                docs[p.name] = text
            else:
                unreadable.append(p.name)
    images = {p.name: p for p in files if p.suffix.lower() in llm.IMAGE_SUFFIXES}
    ws = Workspace(case=case, documents=docs, images=images, **kwargs)
    ws.unreadable = unreadable
    return ws, objective
