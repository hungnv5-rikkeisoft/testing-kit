"""Semi-automated critic over generated testcases — the review checklist as code.

Reuses the depth analysis (`check_depth`) and regroups it by category so the
output reads like the manual review. Flags categories with no checklist
technique (UI, BusinessRule) as needing AI/human judgment, and reports
`depends_on` edges with no linking case (the only hard-gate signal here).
Pure logic: no I/O, no printing, no exit.
"""
from __future__ import annotations
from dataclasses import dataclass, field

from tcformat.schema import VALID_CATEGORIES

# VALID_CATEGORIES is an unordered set; pin a stable order for output.
CATEGORY_ORDER = (
    "UI", "Function", "Validation", "Boundary", "BusinessRule",
    "API", "ErrorHandling", "Security", "UserBehavior",
)
assert set(CATEGORY_ORDER) == VALID_CATEGORIES, "CATEGORY_ORDER out of sync with schema"


@dataclass
class CategoryFinding:
    category: str
    in_matrix: bool
    case_count: int
    gaps: list = field(default_factory=list)        # [(element_id, technique)]
    needs_judgment: bool = False                     # True when outside the matrix


@dataclass
class DependsFinding:
    element_id: str          # the dependent (child) element
    depends_on: str          # the parent element id
    linked: bool             # a case ties child -> parent


@dataclass
class CriticReport:
    categories: list = field(default_factory=list)          # list[CategoryFinding]
    depends: list = field(default_factory=list)             # list[DependsFinding]
    unknown_techniques: list = field(default_factory=list)
    kinds_without_checklist: list = field(default_factory=list)

    @property
    def gate_failures(self) -> list:
        return [d for d in self.depends if not d.linked]


def run_critic(inventory, checklists, screen, depth_report) -> CriticReport:
    cat_of = {}
    for entries in checklists.values():
        for e in entries:
            cat_of[e["technique"]] = e["category"]
    matrix_categories = set(cat_of.values())

    gaps_by_cat: dict = {}
    for eid, tech in depth_report.gaps:
        cat = cat_of.get(tech)
        if cat is not None:
            gaps_by_cat.setdefault(cat, []).append((eid, tech))

    categories = []
    for cat in CATEGORY_ORDER:
        in_matrix = cat in matrix_categories
        case_count = sum(1 for tc in screen.testcases if tc.category == cat)
        categories.append(CategoryFinding(
            category=cat,
            in_matrix=in_matrix,
            case_count=case_count,
            gaps=gaps_by_cat.get(cat, []),
            needs_judgment=not in_matrix,
        ))

    label_by_id = {el.id: el.label for el in inventory.elements}
    depends = []
    for el in inventory.elements:
        for parent_id in el.depends_on:
            needles = [parent_id.lower()]
            plabel = label_by_id.get(parent_id, "")
            if plabel:
                needles.append(plabel.lower())
            linked = False
            for tc in screen.testcases:
                if tc.target != el.id:
                    continue
                text = " ".join(
                    list(tc.steps) + list(tc.expected) + [tc.precondition]).lower()
                if any(n in text for n in needles):
                    linked = True
                    break
            depends.append(DependsFinding(
                element_id=el.id, depends_on=parent_id, linked=linked))

    return CriticReport(
        categories=categories,
        depends=depends,
        unknown_techniques=list(depth_report.unknown_techniques),
        kinds_without_checklist=list(depth_report.kinds_without_checklist),
    )
