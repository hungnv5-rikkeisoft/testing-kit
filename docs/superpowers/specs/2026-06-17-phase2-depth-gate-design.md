# Spec — Phase 2: Depth GATE + ma trận element × technique

> Ngày: 2026-06-17. Tiếp nối hướng "coverage-depth". Đọc trước:
> - Handoff: `docs/superpowers/2026-06-17-phase2-3-handoff.md`
> - Nền Phase 1: `docs/superpowers/specs/2026-06-17-phase1-coverage-depth-design.md`,
>   `docs/superpowers/plans/2026-06-17-phase1-coverage-depth.md`

## 1. Mục tiêu

Biến `DepthReport` (Phase 1, advisory) thành **cổng cứng ở Stage 1**: một CLI mới
`tk-coverage` exit non-zero khi test case sinh ra chưa phủ đủ chiều sâu, chặn trước
khi sang Stage 2. Đồng thời in **ma trận element × technique** để người đọc thấy ô nào
trống, và lộ 2 điểm mù của metric advisory (tag technique gõ sai; kind không có checklist)
dưới dạng **cảnh báo** thay vì im lặng.

Lý do gate ở Stage 1: depth là về *chất lượng test case* (sản phẩm của Stage 1), không
phải kết quả chạy (Stage 3). Tách khỏi cổng exit-criteria của `tk-report`.

## 2. Quyết định đã chốt (brainstorming 2026-06-17)

| Quyết định | Lựa chọn |
|---|---|
| Vị trí gate | **Stage 1** — CLI mới `tk-coverage`, exit non-zero |
| Ngưỡng PASS | **0 gap chưa-justify** (không phải `depth_rate >= X%`) |
| Cơ chế justify | **`el.skip_techniques: [...]`** trong `inventory.yaml` |
| `unknown_techniques` | **chỉ cảnh báo**, KHÔNG fail gate |
| `kinds_without_checklist` | **chỉ cảnh báo**, KHÔNG fail gate |
| Vị trí ma trận | module mới `tcformat/depth_matrix.py` |
| Config | **không thêm trường mới** (ngưỡng là "0 gap", không phải số %) |

## 3. Thay đổi model dữ liệu

### 3.1 `tcformat/inventory.py` — thêm `skip_techniques`

`Element` thêm field:
```python
skip_techniques: list = field(default_factory=list)
```
`_element()` đọc `list(d.get("skip_techniques") or [])`. Không validate giá trị technique
ở loader (free-text, giống `technique` tag) — việc soi technique lạ thuộc về `check_depth`
qua `unknown_techniques`/log. Một technique trong `skip_techniques` mà không thuộc checklist
của kind đó cũng vô hại (đơn giản là không khớp ô nào để trừ); không cần báo lỗi.

### 3.2 `tcformat/coverage.py` — mở rộng `DepthReport` + `check_depth`

`DepthReport` thêm 3 trường (giữ `expected`, `covered`, `gaps`, `depth_rate` như cũ):
```python
@dataclass
class DepthReport:
    expected: int
    covered: int
    gaps: list                  # list[(element_id, technique)] — ô trống, KHÔNG justify → fail gate
    skipped: list = field(default_factory=list)              # (element_id, technique) đã justify (trừ khỏi expected)
    unknown_techniques: list = field(default_factory=list)   # (element_id, technique) testcase gắn nhưng không có trong checklist của kind đó
    kinds_without_checklist: list = field(default_factory=list)  # (element_id, kind) kind không có entry checklist
```

`check_depth(inventory, checklists, screen)` đổi như sau:

1. `have = {(tc.target, tc.technique) for tc in screen.testcases if tc.target and tc.technique}`.
2. Với mỗi element (bỏ qua `kind == "screen"`):
   - Lấy `entries = checklists.get(el.kind)`. Nếu `el.kind` **không có key** trong checklists
     (vd `link`) → thêm `(el.id, el.kind)` vào `kinds_without_checklist`, bỏ qua element (0 ô kỳ vọng).
   - Với mỗi `entry`, ô `(el.id, entry["technique"])`:
     - Nếu `entry["technique"] in el.skip_techniques` → thêm vào `skipped`, KHÔNG đưa vào `expected_cells`.
     - Ngược lại → thêm vào `expected_cells`.
3. Ô screen-level (`checklists.get("screen", [])`) thêm vào `expected_cells` dưới target `"screen"`
   (giữ nguyên hành vi Phase 1; screen không có cơ chế skip ở Phase 2 — YAGNI, chưa cần justify cấp màn).
4. `gaps = [cell for cell in expected_cells if cell not in have]`.
5. **`unknown_techniques`**: với mỗi `(target, technique) in have` mà target khớp một element id
   (hoặc `"screen"`), nếu `technique` KHÔNG nằm trong tập technique hợp lệ của kind tương ứng
   → thêm `(target, technique)`. (Tập hợp lệ = technique trong `checklists[kind]`.) Bỏ qua target
   không khớp element nào (đó là vấn đề target sai, ngoài phạm vi metric này).
6. `covered = len(expected_cells) - len(gaps)`.

`depth_rate` giữ công thức cũ `covered / expected`.

## 4. CLI `tk-coverage`

Module mới `tcformat/coverage_cli.py`, theo mẫu `tcformat/report_cli.py`. Console script
đăng ký trong `pyproject.toml` `[project.scripts]`: `tk-coverage = "tcformat.coverage_cli:main"`.

```
tk-coverage --screen testcases/<screen>.yaml
            [--inventory testcases/<screen>.inventory.yaml]
            [--config config.yaml]
            [--matrix-out reports/<screen>_depth.md]
```

- `--inventory` mặc định: cạnh `--screen`, đổi đuôi `.yaml` → `.inventory.yaml`. Override được.
- `--config`: dùng để resolve `checklists_path` (qua `tcformat.resources.checklists_path`).
- Load: `load_screen(screen)`, `load_inventory(inventory)`, `load_checklists(config_path=config)`.
- Gọi `check_depth(...)` → in báo cáo ra stdout theo thứ tự:
  1. Tổng quan: `expected`, `covered`, `depth_rate` (làm tròn 2 chữ số).
  2. **GAPS** (nếu có): danh sách `(element_id, technique)` — đây là nguyên nhân fail.
  3. **SKIPPED** (nếu có): `(element_id, technique)` đã justify — log rõ ràng (không im lặng).
  4. **WARNING — unknown techniques** (nếu có).
  5. **WARNING — kinds without checklist** (nếu có).
- In ma trận (mục 5) ra stdout; nếu có `--matrix-out` ghi thêm file markdown đó (tạo thư mục cha nếu thiếu).
- **Exit code:** `1` nếu `len(gaps) > 0`, ngược lại `0`. Cảnh báo KHÔNG đổi exit code.
- Fail fast khi thiếu/không đọc được screen/inventory (đúng nguyên tắc dự án).

## 5. Ma trận element × technique — `tcformat/depth_matrix.py`

Hàm thuần, không I/O:
```python
def render_depth_matrix(inventory, checklists, depth_report) -> str: ...
```
Trả markdown table, KHÔNG đụng format team A–R (đây là output phụ, không phải deliverable):

```
| element id | kind  | technique   | có case? | trạng thái |
|------------|-------|-------------|----------|------------|
| field_name | input | empty       | ✓        | covered    |
| field_name | input | max-length  | ✗        | GAP        |
| field_name | input | boundary    | –        | skipped    |
```

Quy ước trạng thái mỗi ô `(element_id, technique)`:
- `–` / `skipped`: ô nằm trong `depth_report.skipped`.
- `✓` / `covered`: không skip và không thuộc `gaps`.
- `✗` / `GAP`: thuộc `depth_report.gaps`.

Hàng được sinh từ chính inventory + checklists (mọi ô kỳ vọng + skipped), thứ tự theo element
rồi theo thứ tự technique trong checklist; screen-level techniques ở cuối dưới element id `screen`.
Element có kind không-checklist không sinh hàng (đã phản ánh ở cảnh báo riêng).

## 6. SKILL.md — bước 4 từ advisory → bắt buộc

`skills/generate-testcases/SKILL.md`: sau khi sinh case, **chạy `tk-coverage`**. Nếu exit≠0
(còn gap chưa justify): bổ sung test case cho ô thiếu, HOẶC thêm `skip_techniques` (kèm lý do
rõ ràng) cho element trong `inventory.yaml`, rồi chạy lại. **Chưa sạch (exit 0) thì chưa chuyển
Stage 2.** Cảnh báo (unknown techniques / kind thiếu checklist) cần xem và xử lý nhưng không chặn.

## 7. Testing (TDD)

- `tests/unit/test_tc_depth.py` (mở rộng):
  - `skip_techniques` trừ đúng ô khỏi `expected` và đưa vào `skipped`.
  - `unknown_techniques` phát hiện testcase gắn technique không thuộc checklist của kind.
  - `kinds_without_checklist` phát hiện element kind `link` (không có entry).
  - Bổ sung assert trực tiếp `depth_rate == 0.25` ở case phủ một phần (điểm mù #3 handoff).
- `tests/unit/test_depth_matrix.py` (mới): render `✓`/`✗`/`–` đúng từng trạng thái; thứ tự hàng.
- `tests/unit/test_coverage_cli.py` (mới): exit 1 khi có gap; exit 0 khi sạch; justify (`skip_techniques`)
  làm gate chuyển từ fail → pass; cảnh báo không đổi exit code; `--matrix-out` ghi file.

Kỳ vọng: toàn bộ suite xanh (Phase 1 đang 70 passed; Phase 2 thêm test mới).

## 8. Files đụng (tổng kết)

| File | Thay đổi |
|---|---|
| `tcformat/inventory.py` | +`skip_techniques` trên `Element` + loader |
| `tcformat/coverage.py` | mở rộng `DepthReport` (+3 trường) + `check_depth` |
| `tcformat/depth_matrix.py` | **mới** — `render_depth_matrix` |
| `tcformat/coverage_cli.py` | **mới** — CLI gate `tk-coverage` |
| `pyproject.toml` | đăng ký console script `tk-coverage` |
| `skills/generate-testcases/SKILL.md` | bước 4: advisory → bắt buộc |
| `tests/unit/test_tc_depth.py` | mở rộng |
| `tests/unit/test_depth_matrix.py` | **mới** |
| `tests/unit/test_coverage_cli.py` | **mới** |

## 9. Ngoài phạm vi (để lại Phase 3)

- Structured `expected` (assertion có cấu trúc) + flatten khi render xlsx.
- Critic linter (`tk-critic` / sub-skill AI) soi nhóm còn thiếu.
- Justify ở cấp screen-level technique (chưa cần — YAGNI).
- Ngưỡng `depth_rate >= X%` dạng số (đã chọn semantic "0 gap" thay thế).

## 10. Quy ước (theo CLAUDE.md / handoff)

- Tag/khối inventory mới là **YAML-only**; KHÔNG đổi format team xlsx (cột A–R).
- Cấu hình overridable qua config (`checklists_path`, ...) — đổi dự án không sửa code.
- venv: `./.venv/Scripts/python.exe` / `./.venv/Scripts/pytest`.
- Git: chỉ commit/add/push khi user xác nhận; message thuần, KHÔNG trailer `Co-Authored-By`.
- Spec tiếng Việt; giữ thuật ngữ nhất quán.
