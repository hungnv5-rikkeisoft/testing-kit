"""Stage 1 completeness lint — catches a forgotten element DIMENSION.

`tk-coverage`'s depth check only validates technique cells for elements that
EXIST in the inventory; it cannot flag a whole element kind that was never
listed. These deterministic, YAML-only rules close that blind spot:

- R1  request/redirect expected ⇒ inventory must have an `api` element
      (or declare `absent.api: "<reason>"`).
- R2  declared-absence registry: a kind in `inventory.absent` with a non-empty
      reason satisfies the "must have ≥1 of this kind" rules (escape hatch).
- R3  every testcase `target` must be `screen` or an existing element id.
"""
from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class LintViolation:
    rule: str
    message: str
    target: str = ""


@dataclass
class LintReport:
    violations: list = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.violations


def _declared_absent(inventory, kind: str) -> bool:
    return bool((inventory.absent.get(kind) or "").strip())


def check_completeness(inventory, screen) -> LintReport:
    violations: list = []
    element_ids = {el.id for el in inventory.elements}
    kinds = {el.kind for el in inventory.elements}

    # R1 (+ R2 escape hatch): a backend call is asserted via structured
    # request/redirect expected keys, so an `api` element must be inventoried.
    needs_api = any(
        isinstance(item, dict)
        and (item.get("request") is not None or item.get("redirect") is not None)
        for tc in screen.testcases
        for item in tc.expected
    )
    if needs_api and "api" not in kinds and not _declared_absent(inventory, "api"):
        violations.append(LintViolation(
            rule="R1",
            message=("Có testcase với assertion request/redirect nhưng inventory "
                     "thiếu element kind 'api'. Thêm 1 element api, hoặc khai báo "
                     "absent.api: \"<lý do>\" trong inventory."),
            target="api"))

    # R3: referential integrity of testcase target -> inventory element.
    for tc in screen.testcases:
        if tc.target and tc.target != "screen" and tc.target not in element_ids:
            violations.append(LintViolation(
                rule="R3",
                message=(f"testcase {tc.id}: target '{tc.target}' không tồn tại "
                         "trong inventory (thêm element hoặc sửa target)."),
                target=tc.target))

    return LintReport(violations=violations)
