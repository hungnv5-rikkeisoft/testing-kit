# Spec — Phase 3a: Structured `expected` assertions

> Ngày: 2026-06-18. Đây là phần **3a** còn lại của hướng "coverage-depth"
> (xem `docs/superpowers/2026-06-17-phase2-3-handoff.md` §3). Phase 1, 2, 3b đã merge `main`.
> Phase 3a cho phép mỗi phần tử `expected` là **assertion có cấu trúc** thay vì chỉ free-text,
> rồi *làm phẳng* về chuỗi khi render xlsx để KHÔNG đổi format deliverable (cột A–R).

## 1. Vấn đề

Hiện `Testcase.expected: list` chỉ chứa string tự do (review điểm #9: expected quá chung chung).
Người viết/generator mô tả kết quả mong đợi bằng câu chữ, nên:

- Khó kiểm tra nhất quán (mỗi case một cách diễn đạt).
- Không tách được "field nào = giá trị gì", "button bật/tắt", "gọi API nào", "redirect đâu".

Mục tiêu Phase 3a: cho phép expected là assertion có cấu trúc (key cố định) **mà vẫn**:

- Back-compat tuyệt đối với YAML cũ (expected toàn string).
- Không đổi format team xlsx (cột A–R) — render *làm phẳng* assertion về text ở cột 8.

## 2. Quyết định đã chốt (với user)

- **Optional toàn bộ.** Mỗi phần tử `expected` có thể là `str` (như cũ) HOẶC `dict` assertion.
  KHÔNG ép category nào (Validation/Function...) phải dùng dict — không thêm gate cứng.
- **Flatten gộp `"; "` theo key cố định.** Một dict render thành một dòng "1. …", các clause
  trong dict nối bằng `"; "`. Giữ nguyên đánh số `1. 2. 3.` hiện có ở cột 8.
- **Một dict = một subject (`field`).** Các thuộc tính `value/enabled/required/button_state`
  cùng mô tả về `field` đó. Nhiều field → nhiều phần tử trong list `expected`.
- **Tag YAML-only.** Không đụng template; mọi thứ chỉ ở YAML + lúc render flatten.

## 3. Bộ key assertion (đúng 7 key, mọi key optional)

| key | kiểu | ý nghĩa | clause flatten |
|-----|------|---------|----------------|
| `field` | str | subject của assertion (tên field/element người đọc) | (không tự sinh clause; là tiền tố cho `value/enabled/required/button_state`) |
| `value` | str/số | giá trị field | `"{field} = {value}"` (hoặc `"= {value}"` nếu thiếu field) |
| `enabled` | bool | field bật/tắt | `"{field} enabled"` / `"{field} disabled"` (bỏ tiền tố nếu thiếu field) |
| `required` | bool | bắt buộc/không | `"{field} required"` / `"{field} optional"` |
| `button_state` | str | trạng thái nút | `"{field} button {button_state}"` (hoặc `"button {button_state}"`) |
| `request` | str | lời gọi API | `"{request}"` (vd `"POST /api/x"`) |
| `redirect` | str | điều hướng | `"redirect {redirect}"` |

Quy tắc:

- **Unknown key → `SchemaError`** (fail fast, nêu rõ tc id và key lạ).
- **Dict không có key tạo-clause nào → `SchemaError`** (assertion vô nghĩa). Cụ thể: dict phải có
  ít nhất 1 key NGOÀI `field` (vì `field` đơn độc chỉ là tiền tố, không sinh clause). `{}` hay
  `{field: "X"}` đều bị chặn.
- String item: pass-through, không validate nội dung.

## 4. Thiết kế

### 4.1 `tcformat/schema.py`

- `expected: list` giữ nguyên (chứa hỗn hợp `str | dict`).
- Trong `_testcase`, khi build `expected`, validate từng phần tử:
  - `str` → giữ nguyên.
  - `dict` → mọi key phải thuộc tập 7 key, và phải có ít nhất 1 key ngoài `field`; nếu sai raise
    `SchemaError` (`testcase {id}: expected assertion has unknown key '{k}'` /
    `... has no assertion keys`).
  - kiểu khác (int/list...) → `SchemaError`.
- Hằng `EXPECTED_KEYS = {"field","value","enabled","required","button_state","request","redirect"}`.

- **`flatten_expected(item) -> str`** — hàm thuần, module-level (tái dùng được):
  - `str` → trả nguyên văn.
  - `dict` → dựng clause theo **thứ tự key cố định** `value, enabled, required, button_state, request, redirect`
    (subject `field` chỉ là tiền tố), bỏ qua key vắng mặt / `None`, nối `"; "`.
  - dict không sinh clause nào (về lý thuyết đã bị schema chặn) → trả `""`.

### 4.2 `tcformat/render_xlsx.py`

- Dòng 79–80: thay `f"{i + 1}. {e}"` → `f"{i + 1}. {flatten_expected(e)}"` (import từ `schema`).
- Không đổi gì khác (đánh số, cột 8 giữ nguyên).

### 4.3 `tcformat/critic.py`

- Dòng ~88: chỗ `" ".join(list(tc.steps) + list(tc.expected) + [tc.precondition or ""])`
  → flatten expected trước khi join: `... + [flatten_expected(e) for e in tc.expected] + ...`
  để dict item không làm `join` crash và keyword vẫn match được trên text đã phẳng.

### 4.4 Roundtrip

- `dump_screen`/`asdict`: dict item là dict thuần → YAML dump lại thành dict, load lại bằng nhau.
- YAML cũ (expected toàn string) → không đổi byte nào về mặt ngữ nghĩa; test roundtrip cũ vẫn xanh.

## 5. Test (TDD)

`tests/unit/test_tc_schema.py` (+ render/critic test tương ứng):

1. **Mixed load:** expected gồm cả string và dict hợp lệ → load OK, giữ đúng kiểu phần tử.
2. **Unknown key:** dict có key lạ (vd `foo`) → `SchemaError`.
3. **No-assertion dict:** `{}` và `{field: "X"}` (chỉ có `field`) → `SchemaError`.
4. **Wrong type:** phần tử là int/list → `SchemaError`.
5. **Flatten formatting:** từng key (value, enabled true/false, required true/false, button_state,
   request, redirect) ra đúng clause; nhiều key nối `"; "` đúng thứ tự; thiếu `field` xử lý đúng.
6. **Render:** screen có dict expected → cột 8 chứa text đã phẳng, đánh số `1. …` đúng.
7. **Critic:** testcase có dict expected → `run_critic` không crash, keyword (depends_on) vẫn match
   trên nội dung đã phẳng.
8. **Back-compat:** test roundtrip cũ (expected toàn string) vẫn pass.

Kỳ vọng: tổng suite vẫn xanh (hiện 83+ passed sau Phase 2/3b) + các test mới.

## 6. Ngoài phạm vi (YAGNI)

- KHÔNG ép buộc dùng dict theo category (đã chốt optional toàn bộ).
- KHÔNG thêm sheet/cột xlsx mới; KHÔNG đổi cột A–R.
- KHÔNG dùng assertion để *tự động so khớp* khi chạy Stage 2 (run-testcases vẫn đọc text/đánh giá
  như cũ) — assertion chỉ làm rõ expected cho người đọc + flatten. (Để mở cho phase sau nếu cần.)
- KHÔNG đổi `config.py` (không có ngưỡng mới).

## 7. Quy ước

- TDD, file nhỏ tập trung. Git: chỉ commit/add/push khi user xác nhận; message thuần, không trailer.
- Dùng venv `./.venv/Scripts/python.exe` / `./.venv/Scripts/pytest`.
- Spec tiếng Việt, giữ thuật ngữ nhất quán.
