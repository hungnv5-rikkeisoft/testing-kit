# Design — Inventory completeness gate (đóng "điểm mù inventory")

- **Ngày:** 2026-06-23
- **Trạng thái:** Đã duyệt thiết kế, chờ review spec → writing-plans
- **Phạm vi:** Stage 1 (generate-testcases). Không đụng Stage 2/3.

## 1. Vấn đề

Inventory (`testcases/<screen>.inventory.yaml`) do AI viết tay từ design doc, là trục
fan-out cho sinh test case. Cổng độ sâu `tk-coverage` (`tcformat/coverage.py::check_depth`)
chỉ kiểm các ô `element × technique` cho **những element ĐÃ có trong inventory**. Vì vậy
nếu quên cả một lớp element, cổng vẫn báo 100% — nó **không thể bắt một chiều chưa bao
giờ được liệt kê**.

Bằng chứng thực tế (màn `hows-renkei`): nút submit là một native form POST nhưng không
được liệt kê dạng `kind: api`, nên toàn bộ chiều HTTP-code (9 technique) vắng mặt. Testcase
IT-251 đã có assertion `request:`/`redirect:` (rõ ràng có lời gọi backend) mà `tk-coverage`
vẫn exit 0, depth 100%. Lỗ hổng chỉ lộ ra khi reviewer con người soi — đúng thứ ta muốn
tránh phải "sửa tay report".

Thêm hai biểu hiện phụ của cùng điểm mù:
- Một testcase có thể đặt `target` trỏ tới element **không tồn tại** trong inventory mà
  không gì cảnh báo (`coverage.py` dòng ~83 cố ý bỏ qua target không khớp element).
- Không có cơ chế khai báo "màn này không có lớp X (có lý do)", nên gate dù có cũng không
  phân biệt được *thiếu sót* với *chủ đích N/A*.

## 2. Mục tiêu / Phi mục tiêu

**Mục tiêu**
- Làm cho việc thiếu nguyên một chiều element trở thành **lỗi cổng (hard gate)**, trừ khi
  được khai báo vắng-mặt có lý do.
- Cung cấp một lớp **đối chiếu với app thật** (DOM snapshot) để phát hiện element bị quên
  mà luật tất định không thấy — nhưng ở mức **advisory** (không chặn).
- Không thêm phụ thuộc Python-Playwright (giữ DoD: Stage 2 dùng Playwright MCP).

**Phi mục tiêu (YAGNI)**
- KHÔNG làm phần "skip có cấu trúc + lý do bắt buộc" và "coverage surface trong deliverable
  xlsx" (đã cân nhắc, người dùng *không* chọn lần này; để spec khác).
- KHÔNG parse source theo từng công nghệ app (Vue/JSON) — tránh app-coupling.
- KHÔNG đụng `tk-critic` rule `depends_on` (giữ nguyên ở critic, không nhân đôi).

## 3. Quyết định kiến trúc (đã chốt)

1. **Hai lớp:** lint heuristic (tất định, app-agnostic) + DOM audit (khi app chạy).
2. **Enforcement:** lint = **hard gate**; DOM audit = **advisory** (matching DOM↔inventory
   là heuristic, dễ false-positive với element ẩn/điều kiện → không nên chặn build).
3. **Đóng gói:** logic ở module riêng `tcformat/inventory_lint.py`, **lộ ra qua
   `tk-coverage`** để Stage 1 vẫn một cổng, một exit code (workflow skill không đổi số bước
   bắt buộc).

## 4. Thiết kế chi tiết

### 4.1 Lớp lint heuristic (hard gate)

Module mới `tcformat/inventory_lint.py`:

```python
@dataclass
class LintViolation:
    rule: str          # "R1" | "R2" | "R3"
    message: str       # mô tả người đọc được
    target: str = ""   # element id / technique / kind liên quan (nếu có)

@dataclass
class LintReport:
    violations: list   # list[LintViolation]
    @property
    def ok(self) -> bool: return not self.violations

def check_completeness(inventory, screen) -> LintReport: ...
```

**Bộ luật tối thiểu (chỉ suy từ YAML, tất định):**

- **R1 — Endpoint presence.** Nếu **bất kỳ** testcase có một phần tử `expected` là dict
  chứa key `request` hoặc `redirect` ⇒ inventory phải có ≥1 element `kind == "api"`.
  Nếu không có và cũng không khai báo `absent.api` ⇒ vi phạm.
  *(Dùng key cấu trúc `request`/`redirect` làm tín hiệu — tất định, không NLP. Xem
  `schema.py::flatten_expected` để biết hình dạng dict expected.)*

- **R3 — Target ↔ element integrity.** Với mọi testcase có `target`, `target` phải bằng
  `"screen"` hoặc là `id` của một element trong inventory. Trỏ tới id không tồn tại ⇒ vi phạm.
  *(Đảo ngược hành vi "bỏ qua âm thầm" hiện tại thành lỗi cổng.)*

- **R2 — Declared-absence registry.** Thêm map cấp inventory:
  ```yaml
  absent:
    api: "Màn chỉ hiển thị, không gọi backend nào."
  ```
  Một kind có mặt trong `absent` với lý do **non-empty** thì *thỏa* các luật "phải có ≥1
  kind này" (hiện chỉ R1 dùng, cho `api`). Lý do rỗng/thiếu ⇒ coi như không khai báo.
  `absent` cũng được in ra trong output cổng để truy vết.

*Ghi chú mở rộng (KHÔNG làm v1):* có thể tổng quát R1 thành luật `expected_kinds` cấu hình
được (vd "màn tương tác mặc định phải có button + api, thiếu thì justify qua `absent`").
Để lại làm điểm mở rộng; v1 chỉ cần R1 vì `api` là chiều thực sự hay bị quên.

### 4.2 Mô hình dữ liệu & tích hợp CLI

- `tcformat/inventory.py`:
  - `Element` giữ nguyên.
  - `Inventory` thêm field `absent: dict = field(default_factory=dict)`.
  - `load_inventory` parse khóa `absent` (validate: value phải là chuỗi; key nên thuộc
    `VALID_KINDS`, key lạ → cảnh báo nhẹ chứ không lỗi).
- `tcformat/coverage_cli.py` (lệnh `tk-coverage`):
  - Trước depth pass, gọi `check_completeness(inventory, screen)`.
  - In section "INVENTORY COMPLETENESS": liệt kê violations (rule + message) và `absent`
    đã khai báo.
  - **Exit≠0 nếu có violation** (gộp với điều kiện fail hiện tại của depth). Thông điệp
    hướng dẫn: thêm element, hoặc khai báo `absent.<kind>: "<lý do>"`.

### 4.3 Lớp DOM audit (advisory)

- Snapshot do **Playwright MCP** (hạ tầng Stage 2) tạo ra — KHÔNG import python-playwright.
  Agent chạy `browser_snapshot` trên màn đang chạy, lưu cây accessibility/DOM thành file
  (vd `evidence/<screen>/inventory-snapshot.json` hoặc `.yaml`).
- Module mới `tcformat/inventory_audit.py` + CLI `tk-inventory-audit`:
  ```
  tk-inventory-audit --inventory testcases/<screen>.inventory.yaml \
                     --snapshot <snapshot-file> [--out reports/<screen>_inventory-audit.md]
  ```
  - Trích từ snapshot: input/select theo thuộc tính `name`; button theo text/label chuẩn hóa;
    `<form action method>`.
  - Diff vs inventory:
    - DOM có, inventory không có (theo name/label) → **SUSPECTED MISSING** (warn).
    - Inventory có (non-api, non-screen), DOM không có → **SUSPECTED STALE/typo** (warn).
    - Có `<form action/method>` nhưng inventory thiếu element `api` → nhắc lại R1.
  - **Luôn exit 0.** In báo cáo; tuỳ chọn ghi `--out`.
  - Định danh khớp lợi thế ở project này: `id` inventory == `name` field == `name` DOM
    (vd `mode`, `userId`). Khớp bằng so khớp chuẩn hóa (lower/trim); không khớp → liệt kê
    để người/AI đối chiếu (không đoán mò tự sửa).
- **Parser snapshot:** thuần Python, đọc định dạng output của `browser_snapshot`. Cần chốt
  định dạng snapshot ở bước implementation (xem Rủi ro).

### 4.4 Cập nhật skill `generate-testcases`

- Bước 4 (cổng độ sâu): ghi rõ `tk-coverage` nay kiểm **cả** inventory-completeness
  (hard gate) trước depth; mô tả cách sửa (thêm element hoặc `absent`).
- Bước 1 (xây inventory): thêm bước **advisory** — "nếu app đang chạy: agent chụp
  `browser_snapshot`, chạy `tk-inventory-audit`, đối chiếu các cảnh báo MISSING/STALE
  trước khi chốt inventory."

## 5. Thành phần bàn giao

| File | Loại | Nội dung |
|---|---|---|
| `tcformat/inventory.py` | sửa | thêm `Inventory.absent` + parse |
| `tcformat/inventory_lint.py` | mới | `check_completeness` + R1/R2/R3 |
| `tcformat/coverage_cli.py` | sửa | chạy lint trước depth, in section, gộp exit code |
| `tcformat/inventory_audit.py` | mới | diff snapshot ↔ inventory (advisory) |
| `pyproject`/entry points | sửa | console script `tk-inventory-audit` |
| `tests/unit/test_inventory_lint.py` | mới | R1/R2/R3 + absent (không cần app) |
| `tests/unit/test_inventory_audit.py` | mới | diff trên snapshot mẫu cố định |
| skill `generate-testcases/SKILL.md` | sửa | bước 4 + bước 1 advisory |

## 6. Chiến lược test (TDD)

- **inventory_lint:** bảng case —
  - R1: có `request`/`redirect` + không api + không absent → 1 violation; + có api → ok;
    + có `absent.api="..."` → ok; `absent.api=""` → vẫn violation.
  - R3: target trỏ id tồn tại → ok; target="screen" → ok; target id lạ → violation.
  - Regression: chạy lint trên `hows-renkei` *bản trước khi thêm submit-api* phải FAIL R1;
    bản sau phải PASS (lấy snapshot YAML làm fixture).
- **inventory_audit:** snapshot mẫu cố định (JSON/YAML) + inventory mẫu → kỳ vọng đúng danh
  sách MISSING/STALE; luôn exit 0.
- **coverage_cli:** integration — exit≠0 khi có violation, exit 0 khi sạch.

## 7. Rủi ro & cách giảm

- **Định dạng snapshot của Playwright MCP** chưa chốt → để `inventory_audit` nhận một
  schema snapshot tối giản, tài liệu hóa rõ; nếu MCP đổi format chỉ sửa lớp parser. Viết
  parser tách rời khỏi logic diff.
- **DOM audit false-positive** (element ẩn theo điều kiện, render động theo preset) → vì là
  advisory nên không chặn; báo cáo ghi rõ "nghi ngờ, cần đối chiếu".
- **R1 quá hẹp/rộng:** chỉ kích hoạt theo key `request`/`redirect` (đã có trong structured
  expected) — nếu testcase mô tả submit bằng prose thuần sẽ lọt; chấp nhận ở v1, DOM audit
  (form action) là lưới thứ hai.

## 8. Tiêu chí hoàn thành

- `tk-coverage` exit≠0 trên inventory thiếu `api` mà có testcase `request`/`redirect`, và
  hướng dẫn cách sửa; exit 0 sau khi thêm element hoặc `absent.api`.
- `tk-inventory-audit` chạy trên snapshot mẫu, in MISSING/STALE đúng, luôn exit 0.
- `pytest tests/unit` xanh (lint + audit + coverage_cli).
- Skill `generate-testcases` phản ánh cổng mới + bước audit advisory.
