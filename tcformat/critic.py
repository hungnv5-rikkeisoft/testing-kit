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


def render_critic_md(report, screen_name) -> str:
    """Render a CriticReport as a grouped markdown review checklist.

    Markers: ✓ covered / ✗ gap / ⚠ outside the mechanical matrix (needs review).
    Output-only — does not touch the team xlsx (columns A–R).
    """
    lines = [f"## Critic review — {screen_name}", "", "### Theo nhóm (category)"]
    for cf in report.categories:
        if not cf.in_matrix:
            lines.append(
                f"- **{cf.category}** — ⚠ NGOÀI MA TRẬN — cần AI/người review "
                f"({cf.case_count} case hiện có)")
        elif cf.gaps:
            lines.append(f"- **{cf.category}** — {cf.case_count} case, {len(cf.gaps)} gap")
            for eid, tech in cf.gaps:
                lines.append(f"    ✗ {eid} / {tech}")
        else:
            lines.append(f"- **{cf.category}** — {cf.case_count} case, 0 gap ✓")

    lines += ["", "### Phụ thuộc field (depends_on)"]
    if report.depends:
        for d in report.depends:
            if d.linked:
                lines.append(f"    ✓ {d.element_id} depends_on {d.depends_on} — đã có case")
            else:
                lines.append(
                    f"    ✗ {d.element_id} depends_on {d.depends_on} "
                    f"— KHÔNG có case liên kết   (fail gate)")
    else:
        lines.append("    (không có phần tử depends_on)")

    if report.unknown_techniques or report.kinds_without_checklist:
        lines += ["", "### Cảnh báo (không chặn gate)"]
        if report.unknown_techniques:
            ut = ", ".join(f"{e}/{t}" for e, t in report.unknown_techniques)
            lines.append(f"- unknown techniques: {ut}")
        if report.kinds_without_checklist:
            kw = ", ".join(f"{e}({k})" for e, k in report.kinds_without_checklist)
            lines.append(f"- kinds without checklist: {kw}")

    return "\n".join(lines)
