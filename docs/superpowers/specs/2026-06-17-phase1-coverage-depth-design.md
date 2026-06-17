# Phase 1 — Coverage depth for generated test cases

**Date:** 2026-06-17
**Status:** Approved design (pre-plan)
**Area:** Stage 1 — `generate-testcases` skill + `tcformat/` backbone

## Problem

A human review of the test cases generated for the `basic-information-input`
screen rated real coverage at ~50–60%, despite the framework's coverage check
reporting 100%. Root cause: `tcformat/coverage.py` measures **breadth only** —
a strategy testing object (`strategy_ref`) counts as "covered" once **one**
testcase is tagged with its ref. The `generate-testcases` skill therefore writes
exactly one testcase per strategy object and stops when `missing` is empty.

The generated `testcases/basic-information-input.yaml` confirms this: 24 cases,
1:1 with the 24 strategy objects (UI_01–11 = `2.3.1#1..11`, FN_01–04 =
`2.3.2#1..4`, NF_01–09 = `2.3.3#1..9`). Consequences:

- `FN_02` is a single case for **all** validation — no fan-out across
  empty / null / space / min / max / over-max / boundary / special char /
  Japanese / Vietnamese / wrong-format / nonexistent-value.
- `UI_07` groups **every** button + dropdown + Submit into one case — buttons
  are not traceable individually, and not all are exercised.
- Pulldown data source / option order / default value are unverified.
- API HTTP-code cases (200/400/401/403/404/500, missing/invalid params, empty
  response) are absent — sheet `1_APITesting` is never pulled into IT screens.

The strategy sheet itself is **not** the gap (it already contains objects for
validation, business flow, no-server, permission, XSS, multi-click). The gap is
that the framework never fans each applicable object out across a
**element × technique** matrix, and has no way to measure that it did.

## Goal

Make Stage 1 produce **depth, not just breadth**: fan out each applicable screen
element across a technique matrix, with enough structure that depth is
measurable and auditable.

In scope for Phase 1 (maps to review points): #1 (one case per button), #2
(option source/order/default), #3 (validation matrix), #5 (API HTTP codes), #8
(user-behavior); partial #4/#6/#7 via cross-cutting techniques.

Out of scope for Phase 1: a hard non-zero exit gate on depth (Phase 2);
structured/assertion-style `expected` fields (Phase 3); an automated critic
linter (Phase 3); any change to Stage 2 (run) or Stage 3 (report); any change to
the team xlsx deliverable format.

## Non-negotiable constraints

- **Backward compatible.** New schema fields are optional with empty defaults;
  existing YAMLs continue to load and render unchanged.
- **Deliverable format untouched.** The team xlsx template has fixed columns
  A–R with no spare column. New tags are **YAML-only metadata**;
  `tcformat/render_xlsx.py` is not changed and the tags are not rendered.
- **Config-driven, no code edits to switch projects.** The checklist ships
  bundled and is overridable via config, mirroring `strategy_path` /
  `template_path`.

## Design

### 1. Schema tags — `tcformat/schema.py`

Add three optional fields to `Testcase` (default `""`), plumbed through
`_testcase()`; `asdict` handles serialization automatically:

- `category` — validated against
  `VALID_CATEGORIES = {UI, Function, Validation, Boundary, BusinessRule, API,
  ErrorHandling, Security, UserBehavior}`. Empty is allowed (back-compat).
- `technique` — free-text key matching a checklist entry (e.g. `empty`,
  `max-length`, `http-401`). Not enum-validated, to stay flexible per project.
- `target` — the element/endpoint id this case exercises (e.g.
  `usage_residential`, `api_submit`). Enables per-element matrix detection
  ("only 3 of 6 buttons covered").

Validation rule: if `category` is non-empty it must be in `VALID_CATEGORIES`,
else raise `SchemaError`. `technique`/`target` are free-text.

These fields are metadata for coverage/audit only. `render_xlsx.py` ignores
them.

### 2. Element inventory artifact — `testcases/<screen>.inventory.yaml`

A new reviewable file, generated **first** and human-checked before any case is
written. Parsed by a new module `tcformat/inventory.py` (load + light
validation; mirrors `schema.py` style).

Shape:

```yaml
screen: Basic Information Input
elements:
  - id: usage_residential
    kind: button            # button | input | select | link | api | screen
    label: "Usage: Residential"
  - id: usage_industrial
    kind: button
    label: "Usage: Industrial"
  - id: prefecture
    kind: select
    label: Prefecture
    options_source: "db:prefectures.name"   # db:table.col | hardcode:[a,b,c]
    default: ""
    depends_on: []
  - id: municipality
    kind: select
    label: Municipality
    options_source: "db:municipalities.name"
    depends_on: [prefecture]
  - id: api_submit
    kind: api
    method: POST
    path: /api/basic-info
    params: [usage, prefecture, municipality]
```

Field notes:

- `kind` is required and drives which checklist techniques apply.
- `options_source` (select only): `db:<table>.<col>` or `hardcode:[...]` —
  forces review #2 (DB vs hard-coded, which table/col, full option list).
- `default` (select/input): expected default on load — review #2.
- `depends_on`: element ids this element's state/value depends on — review #4.
- `params`/`method`/`path` (api only): drive the API technique fan-out.

The inventory is the fan-out axis. A missing element here means missing cases
downstream, so it is the single place a human verifies completeness (e.g. "all 6
preset buttons listed").

### 3. Checklist data — `tcformat/data/checklists.yaml`

Bundled default, resolved via new `resources.checklists_path(explicit, config)`
and `resources.default_checklists()`, overridable with a `checklists_path` key in
config — identical pattern to `template_path` / `strategy_path`. Loaded by a new
module `tcformat/checklists.py`.

Keyed by element `kind` → list of techniques; plus a `screen` group for
cross-cutting cases applied once per screen. Each entry carries `technique`,
`category`, `title`, and an optional `applies_when` hint.

Default content:

```yaml
input:
  - {technique: empty,            category: Validation, title: "Bỏ trống field bắt buộc"}
  - {technique: null-value,       category: Validation, title: "Giá trị null"}
  - {technique: only-space,       category: Validation, title: "Chỉ chứa khoảng trắng"}
  - {technique: min-length,       category: Boundary,   title: "Độ dài tối thiểu"}
  - {technique: max-length,       category: Boundary,   title: "Độ dài tối đa"}
  - {technique: over-max,         category: Boundary,   title: "Vượt độ dài tối đa"}
  - {technique: boundary,         category: Boundary,   title: "Giá trị biên (n-1/n/n+1)"}
  - {technique: special-char,     category: Validation, title: "Ký tự đặc biệt"}
  - {technique: jp-chars,         category: Validation, title: "Ký tự tiếng Nhật"}
  - {technique: vn-chars,         category: Validation, title: "Ký tự tiếng Việt có dấu"}
  - {technique: wrong-format,     category: Validation, title: "Sai định dạng"}
  - {technique: nonexistent-value,category: Validation, title: "Giá trị không tồn tại trong hệ thống"}
select:
  - {technique: option-source,    category: Function,   title: "Nguồn dữ liệu option (DB/hard-code)"}
  - {technique: option-list,      category: Function,   title: "Đủ danh sách option expected"}
  - {technique: option-order,     category: Function,   title: "Thứ tự hiển thị option"}
  - {technique: default-value,    category: Function,   title: "Giá trị mặc định khi load"}
button:
  - {technique: single-action,    category: Function,   title: "Thao tác chính của button (1 case/button)"}
  - {technique: state-after-click,category: Function,   title: "Trạng thái field/button sau khi click"}
  - {technique: double-click,     category: UserBehavior,title: "Double click"}
  - {technique: multi-click-pending,category: UserBehavior,title: "Multi-click khi request đang xử lý"}
api:
  - {technique: http-200,         category: API,        title: "HTTP 200 + body hợp lệ"}
  - {technique: http-400,         category: API,        title: "HTTP 400"}
  - {technique: http-401,         category: API,        title: "HTTP 401"}
  - {technique: http-403,         category: API,        title: "HTTP 403"}
  - {technique: http-404,         category: API,        title: "HTTP 404"}
  - {technique: http-500,         category: API,        title: "HTTP 500"}
  - {technique: missing-param,    category: API,        title: "Thiếu parameter"}
  - {technique: invalid-data,     category: API,        title: "Dữ liệu không hợp lệ"}
  - {technique: empty-response,   category: API,        title: "Response rỗng"}
screen:
  - {technique: url-tamper,            category: Security,     title: "Thay đổi URL trên browser"}
  - {technique: query-tamper,          category: Security,     title: "Thay đổi query parameter"}
  - {technique: direct-access-no-login,category: Security,     title: "Truy cập URL khi chưa login"}
  - {technique: lower-priv-user,       category: Security,     title: "Truy cập bằng user không đủ quyền"}
  - {technique: session-expired,       category: ErrorHandling,title: "Session hết hạn"}
  - {technique: network-down,          category: ErrorHandling,title: "Mất kết nối mạng"}
  - {technique: server-timeout,        category: ErrorHandling,title: "Server timeout"}
  - {technique: back-forward,          category: UserBehavior, title: "Back/Forward browser"}
  - {technique: refresh-during-submit, category: UserBehavior, title: "Refresh khi đang submit"}
```

Projects trim/extend by pointing `checklists_path` at their own file — no code
change. (`jp-chars` is on by default since the surveyed project is JP-oriented;
a non-JP project removes it via override.)

### 4. Advisory depth report — `tcformat/coverage.py`

Add `check_depth(inventory, checklists, screen)` alongside the existing
`check_coverage`. It computes the **expected matrix** — for each inventory
element, the techniques for its `kind`, plus the `screen`-level techniques once —
and reports **gap cells**: an (element, technique) pair with no testcase whose
`target` == element id and `technique` == that technique.

Return a small dataclass, e.g.:

```python
@dataclass
class DepthReport:
    expected: int           # total matrix cells
    covered: int            # cells with >= 1 matching case
    gaps: list              # [(element_id, technique), ...]
    @property
    def depth_rate(self) -> float: ...
```

`check_coverage` (strategy-ref breadth) is unchanged and still runs. The skill
prints both. **Non-gating in Phase 1** — Phase 2 turns `gaps` into a non-zero
exit.

### 5. Resources wiring — `tcformat/resources.py`

Add, mirroring the existing functions:

```python
CHECKLISTS_NAME = "checklists.yaml"
def default_checklists() -> str: ...          # tcformat/data/checklists.yaml
def checklists_path(explicit=None, config_path=None) -> str:
    return explicit or _from_config(config_path, "checklists_path") or default_checklists()
```

### 6. Skill flow — `skills/generate-testcases/SKILL.md`

Rewrite the process to:

1. **Build `testcases/<screen>.inventory.yaml`** from design docs / Figma, then
   pause for human review (catch missing elements before fan-out).
2. **Generate cases**: for every relevant strategy ref **and** every
   (element × technique) from the checklist (element kinds + screen-level),
   writing **one element / one scenario per case**, each tagged with
   `category` / `technique` / `target`. Keep `strategy_ref` where the case maps
   to a strategy object.
3. **Validate + render + report**: run `load_screen`, `render`, `check_coverage`
   (refs) and `check_depth` (matrix); print missing refs and depth gaps.
4. **Loop** until strategy refs are covered and depth gaps are empty or
   explicitly justified in the summary.

Pull `1_APITesting` strategy objects (and sheet 1.3.3 code rules) into the
inventory's `api` elements so HTTP-code techniques are generated.

## Components & boundaries

| Unit | Responsibility | Depends on |
|------|----------------|------------|
| `schema.py` (edit) | add `category`/`technique`/`target`, validate category | — |
| `inventory.py` (new) | load + validate `<screen>.inventory.yaml` | yaml |
| `checklists.py` (new) | load checklist data | resources, yaml |
| `resources.py` (edit) | resolve `checklists_path` | — |
| `coverage.py` (edit) | `check_depth` matrix report | inventory, checklists |
| `data/checklists.yaml` (new) | default technique matrix | — |
| `SKILL.md` (rewrite) | inventory-first, fan-out, dual report flow | all above |

## Testing

Unit tests under `tests/unit/` (no running app):

- `schema`: new fields round-trip; bad `category` raises `SchemaError`; old
  YAML without the fields still loads.
- `inventory`: valid file loads; missing `id`/`kind` raises; unknown `kind`
  raises.
- `checklists`: bundled default loads; `checklists_path` override is honored.
- `coverage.check_depth`: a hand-built inventory + checklist + screen yields the
  expected gap list; full coverage yields zero gaps; screen-level techniques are
  counted once.

## Success criteria

Running `generate-testcases` on `basic-information-input` produces:

- a reviewable `inventory.yaml` listing every button, field, select, and the
  submit API;
- separate cases per button and per (field × validation technique);
- API HTTP-code cases (200/400/401/403/404/500 + param/empty-response);
- a depth report showing 0 unjustified gaps,

replacing today's 24 one-per-ref cases — and `pytest` stays green.

## Phasing (context)

- **Phase 1 (this spec):** inventory + checklist + tags + advisory depth report.
- **Phase 2:** depth gate (non-zero exit) + element×technique matrix in output.
- **Phase 3:** structured/assertion `expected` fields + automated critic linter.
