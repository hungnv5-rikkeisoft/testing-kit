# Spec — Phase 3b: Critic linter (hybrid)

> Ngày: 2026-06-17. Tiếp nối hướng "coverage-depth" (Phase 1 đo chiều sâu, Phase 2
> cổng cứng + ma trận). Phase 3b mã hoá lại **bộ review tay** thành một bước critic
> bán-tự-động đóng vai reviewer. Phase 3a (structured expected) là spec riêng, làm sau.

## 0. Bối cảnh & vấn đề

Review tay màn `basic-information-input` chấm độ phủ thực ~50–60% dù tool báo cao. Phase 2
đã thêm cổng cứng `tk-coverage` đo **ma trận element × technique** (mỗi ô phải có case hoặc
được justify). Nhưng ma trận cơ học vẫn có **điểm mù cố hữu**:

- `checklists.yaml` **không có technique nào** cho category `UI` và `BusinessRule`. Hai nhóm
  này không bao giờ bị cổng cơ học bắt — đúng phần review tay phải tự soi.
- Quan hệ phụ thuộc field (`depends_on` trong inventory) không có technique trong ma trận →
  không ai kiểm "field B phụ thuộc field A" có được test tương tác hay chưa.
- `unknown_techniques` / `kinds_without_checklist` đã được `check_depth` phát hiện nhưng chỉ
  in rời rạc, chưa gom thành checklist review theo nhóm như bản review tay.

**Mục tiêu Phase 3b:** một bước **critic** đóng vai reviewer — gom phát hiện theo *category*
(đúng định dạng checklist review tay), chỉ ra nhóm nằm ngoài ma trận cần phán đoán, và bắt
quan hệ `depends_on` chưa có case liên kết.

## 1. Quyết định đã chốt (brainstorming)

| Câu hỏi | Quyết định |
|---|---|
| Phạm vi Phase 3 | Làm **3b critic linter trước**; 3a structured expected là spec riêng, sau. |
| Kiểu critic | **Hybrid**: phần tất định = CLI `tk-critic`; phần phán đoán = bước AI trong `SKILL.md`. |
| Gate | **Advisory + gate nhẹ `depends_on`**. Chỉ depends_on chưa-liên-kết làm exit non-zero. Nhóm cần phán đoán KHÔNG fail gate. |
| Tín hiệu "liên kết" depends_on | 1 chiều con→cha: có case `target == el.id` và text (steps+expected+precondition) chứa `parent_id` HOẶC `label` cha (substring, case-insensitive). |

Ranh giới CỐ Ý chưa làm (để Phase 3a / sau):
- Structured `expected` (assertion có cấu trúc) — spec riêng 3a.
- Không phát minh nhóm "Permission" riêng: các technique permission (`lower-priv-user`,
  `direct-access-no-login`) đã thuộc category `Security` trong checklist → giữ trục
  `VALID_CATEGORIES` chuẩn của schema.
- Critic KHÔNG cố phán đoán business rule bằng code (để AI trong skill).

## 2. Kiến trúc

`tk-critic` là **lớp trên** `tk-coverage`, không thay thế. Tái dùng `check_depth` (Phase 1/2)
làm nguồn ma trận, rồi tổ chức lại theo nhóm review + thêm heuristic mới.

```
testcases/<screen>.yaml + <screen>.inventory.yaml + checklists.yaml
  │ check_depth() → DepthReport            (đã có — Phase 1/2)
  ▼ run_critic(inventory, checklists, screen, depth_report) → CriticReport
  │   - gom gap theo category
  │   - đánh dấu category ngoài ma trận (UI/BusinessRule) → needs_judgment
  │   - heuristic depends_on (cổng nhẹ)
  │   - chuyển tiếp unknown_techniques / kinds_without_checklist
  ▼ render_critic_md() → markdown checklist review (output-only, KHÔNG đụng cột A–R)
  ▼ tk-critic CLI: in stdout + --out; exit non-zero iff có depends_on chưa liên kết
  ▼ SKILL.md bước cuối: AI đọc nhóm needs_judgment + design doc → bổ sung case
```

**Module mới (file nhỏ, một mục đích):**
- `tcformat/critic.py` — thuần logic + render markdown. Không I/O ngoài nhận object đã load.
- `tcformat/critic_cli.py` — console script `tk-critic`; tái dùng `run_depth_check` từ
  `coverage_cli.py` để load input, ép UTF-8 stdout/stderr (như `coverage_cli.py`).
- `pyproject.toml` `[project.scripts]` — thêm `tk-critic = "tcformat.critic_cli:main"`.

## 3. Data model (`tcformat/critic.py`)

```python
@dataclass
class CategoryFinding:
    category: str            # 1 trong VALID_CATEGORIES (schema.py)
    in_matrix: bool          # checklist có technique nào map về category này?
    case_count: int          # số testcase tag category này
    gaps: list               # [(element_id, technique)] depth gap thuộc category này
    needs_judgment: bool     # True khi not in_matrix (UI/BusinessRule) → AI/người review

@dataclass
class DependsFinding:
    element_id: str          # phần tử con (có depends_on)
    depends_on: str          # id phần tử cha
    linked: bool             # có case liên kết con→cha không

@dataclass
class CriticReport:
    categories: list                 # list[CategoryFinding], thứ tự cố định VALID_CATEGORIES
    depends: list                    # list[DependsFinding]
    unknown_techniques: list         # chuyển tiếp từ DepthReport
    kinds_without_checklist: list    # chuyển tiếp từ DepthReport

    @property
    def gate_failures(self) -> list:
        return [d for d in self.depends if not d.linked]
```

`list` không generic — theo convention `schema.py`/`coverage.py` hiện tại.

## 4. Logic `run_critic(inventory, checklists, screen, depth_report)`

1. **technique → category**: build map từ `checklists` (mỗi entry `{technique, category, title}`).
2. **Nhóm theo category** — `VALID_CATEGORIES` trong `schema.py` là `set` (không thứ tự), nên
   `critic.py` định nghĩa hằng `CATEGORY_ORDER` (tuple liệt kê 9 category theo đúng thứ tự
   schema) để output ổn định; có assert `set(CATEGORY_ORDER) == VALID_CATEGORIES` chống lệch.
   Duyệt theo `CATEGORY_ORDER`:
   - `in_matrix` = category xuất hiện trong map ở (1). → `UI`, `BusinessRule` = `False`.
   - `gaps` = `[(eid, tech) for (eid, tech) in depth_report.gaps if cat_of(tech) == category]`.
   - `case_count` = `sum(1 for tc in screen.testcases if tc.category == category)`.
   - `needs_judgment = not in_matrix`.
3. **`depends_on` heuristic (cổng nhẹ)** — với mỗi `el` có `depends_on`, mỗi `parent_id`:
   - tra `label` cha qua `{e.id: e.label for e in inventory.elements}`.
   - `needles = [parent_id]` + (`[parent_label]` nếu có), lower-case.
   - `linked = any(` case `tc.target == el.id` và một `needle` là substring của
     `" ".join(tc.steps + tc.expected + [tc.precondition]).lower()` `)`.
   - thêm `DependsFinding(el.id, parent_id, linked)`.
   - `parent_id` không tồn tại trong inventory → vẫn ghi finding với `linked=False`
     (dấu hiệu inventory sai — surface, không im lặng).
4. **Chuyển tiếp** `depth_report.unknown_techniques`, `depth_report.kinds_without_checklist`.

Hàm thuần (không in, không exit). Toàn bộ quyết định gate nằm ở property `gate_failures`.

## 5. Render `render_critic_md(report, screen_name)`

Markdown grouped, output-only — KHÔNG đụng template team (cột A–R). Ép Unicode an toàn vì CLI
đã reconfigure UTF-8. Hình dạng:

```
## Critic review — <screen>

### Theo nhóm (category)
- **Validation** — 5 case, 2 gap
    ✗ field_name / max-length
    ✗ field_name / over-max
- **BusinessRule** — ⚠ NGOÀI MA TRẬN — cần AI/người review (3 case hiện có)
- **UI** — ⚠ NGOÀI MA TRẬN — cần AI/người review (0 case)
- **Security** — 4 case, 0 gap ✓
...

### Phụ thuộc field (depends_on)
    ✗ field_b depends_on field_a — KHÔNG có case liên kết   (fail gate)
    ✓ field_d depends_on field_c — đã có case

### Cảnh báo (không chặn gate)
- unknown techniques: ...
- kinds without checklist: ...
```

Quy ước marker: `✓` covered / `✗` gap / `⚠` ngoài ma trận cần phán đoán. Khi không có gap và
không depends_on/cảnh báo, in dòng "Không có phát hiện chặn — vẫn cần AI review nhóm ⚠".

## 6. CLI `tk-critic` (`tcformat/critic_cli.py`)

```bash
./.venv/Scripts/tk-critic --screen testcases/<screen>.yaml --config config.yaml \
    [--inventory testcases/<screen>.inventory.yaml] [--out reports/<screen>_critic.md]
```

- Args giống `tk-coverage` (`--screen`, `--inventory` default `<screen>.inventory.yaml`,
  `--config`, `--out` thay cho `--matrix-out`).
- Ép UTF-8 stdout/stderr (copy pattern `coverage_cli.py`, tránh `UnicodeEncodeError` cp932).
- Tái dùng `run_depth_check(...)` để load → có `DepthReport`; gọi `run_critic` → `render_critic_md`.
- In ra stdout; nếu `--out` thì ghi file.
- **`raise SystemExit(1 if report.gate_failures else 0)`** — chỉ depends_on chưa-liên-kết chặn.

## 7. Gắn vào `SKILL.md` (phần AI hybrid)

Thêm **bước 5** sau bước 4 (`tk-coverage`):

> **5. Critic review (bán-tự-động — bước cuối Stage 1):** Chạy
> `./.venv/Scripts/tk-critic --screen ... --config config.yaml`.
> - Nếu có `depends_on` chưa-liên-kết (exit 1): bổ sung case kiểm tương tác field con↔cha rồi chạy lại.
> - Với mỗi nhóm `⚠ NGOÀI MA TRẬN` (đặc biệt `BusinessRule`, `UI`) và các ràng buộc
>   required-theo-mode / liên field: **AI tự đối chiếu design doc** và bổ sung case còn thiếu
>   (ma trận cơ học không bắt được nhóm này). Đây là phần phán đoán, không có cổng cứng.
> - Chỉ kết thúc Stage 1 khi `tk-coverage` exit 0 **và** đã review xong các nhóm `⚠` của critic.

Cập nhật mục Output: thêm `reports/<screen>_critic.md` (tuỳ chọn) + tóm tắt nhóm cần phán đoán.

## 8. Testing (TDD, `tests/unit/`)

File mới `tests/unit/test_critic.py` (theo mẫu `test_tc_depth.py`), dùng fixture inventory +
screen + checklists nhỏ. Ca kiểm:

1. **Category ngoài ma trận**: checklist không có `UI`/`BusinessRule` → `CategoryFinding` của 2
   nhóm này có `in_matrix=False`, `needs_judgment=True`.
2. **Gap gom đúng category**: depth gap `field/max-length` (Boundary) rơi vào nhóm `Boundary`.
3. **`case_count`** đếm đúng theo `tc.category`.
4. **depends_on linked**: case target con + text chứa id cha → `linked=True`, không vào gate.
5. **depends_on chưa liên kết**: không có case nào → `linked=False`, `gate_failures` non-empty.
6. **depends_on khớp qua `label` cha** (id không xuất hiện nhưng label có) → `linked=True`.
7. **parent_id không tồn tại trong inventory** → finding `linked=False` (surface inventory sai).
8. **Chuyển tiếp warnings**: `unknown_techniques`/`kinds_without_checklist` xuất hiện nguyên trong report.
9. **render_critic_md**: chứa marker `⚠` cho nhóm ngoài ma trận và `✗ ... (fail gate)` cho depends_on hỏng.
10. **CLI exit code**: smoke `main(argv)` — exit 1 khi có depends_on hỏng, exit 0 khi sạch
    (dùng `pytest.raises(SystemExit)`), và không `UnicodeEncodeError`.

Kỳ vọng: toàn bộ suite vẫn xanh (83 cũ + ca mới).

## 9. File sẽ đụng

| File | Thay đổi |
|---|---|
| `tcformat/critic.py` | MỚI — `CategoryFinding`/`DependsFinding`/`CriticReport`, `run_critic`, `render_critic_md`. |
| `tcformat/critic_cli.py` | MỚI — console script `tk-critic`. |
| `pyproject.toml` | thêm `tk-critic` vào `[project.scripts]`. |
| `skills/generate-testcases/SKILL.md` | thêm bước 5 (critic review) + cập nhật Output. |
| `tests/unit/test_critic.py` | MỚI — ca kiểm trên. |
| `docs/superpowers/2026-06-17-phase2-3-handoff.md` | đánh dấu 3b XONG, trỏ Phase 3a còn lại (khi hoàn tất). |

KHÔNG đụng: `config.py` (ngưỡng "0 gate-failure" không cần config số), format team xlsx (A–R),
`check_depth`/`coverage.py` (chỉ đọc `DepthReport`, không sửa).

## 10. Definition of Done

- `pytest` xanh (83 cũ + ca `test_critic.py` mới).
- `tk-critic` chạy được trên màn thật, in checklist review theo nhóm, exit non-zero khi có
  `depends_on` chưa-liên-kết, exit 0 khi sạch — không `UnicodeEncodeError` trên cp932.
- `SKILL.md` có bước 5 critic là bước cuối Stage 1.
- Mọi cấu hình vẫn overridable (`checklists_path`); đổi dự án không sửa code.
