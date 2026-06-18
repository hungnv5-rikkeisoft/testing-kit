# Handoff — Coverage-depth Phase 2 & 3

> Cập nhật: 2026-06-18. Tài liệu này để session/agent kế tiếp tiếp nối phần **Phase 2 & 3**
> của hướng "coverage-depth" (sinh test case có chiều sâu). Đọc file này trước, rồi mở
> spec/plan Phase 1 để biết nền đã có.
>
> **Trạng thái: TẤT CẢ Phase 1, 2, 3a, 3b ĐÃ XONG — đã merge `main`.** Hướng coverage-depth hoàn tất.
> Xem §2 cho Phase 2, §3 cho Phase 3 (3a structured expected + 3b critic linter). Không còn việc
> bắt buộc nào trong hướng này; phần "việc tiếp theo (tuỳ chọn)" còn lại ở cuối §3.

## 0. Bối cảnh — vì sao có Phase 2/3

Review tay trên test case sinh ra cho màn `basic-information-input` chấm độ phủ thực ~50–60%
dù tool báo 100%. Nguyên nhân: `coverage.check_coverage` chỉ đo **độ rộng** (mỗi `strategy_ref`
có ≥1 testcase là "covered"), nên generator viết 1 case/strategy object rồi dừng — không fan-out
mỗi field/button qua ma trận kỹ thuật (validation, boundary, API code, error, security, user-behavior).

**Phase 1 (ĐÃ XONG, đã merge `main`)** giải quyết phần *đo được chiều sâu*:
- Spec: `docs/superpowers/specs/2026-06-17-phase1-coverage-depth-design.md`
- Plan: `docs/superpowers/plans/2026-06-17-phase1-coverage-depth.md`
- Commits: `dccfc69..28fb3a1` (6 commit). Test: **70 passed**.

Đã có sẵn (Phase 1):
- `tcformat/schema.py` — 3 tag optional, YAML-only: `category` (validate theo `VALID_CATEGORIES`),
  `technique` (free-text), `target` (id element / `screen`). KHÔNG render ra xlsx.
- `tcformat/data/checklists.yaml` + `tcformat/checklists.py` (`load_checklists`) — ma trận kỹ thuật
  theo kind (`input/select/button/api/screen`), config-overridable qua `checklists_path`.
- `tcformat/inventory.py` (`load_inventory`, `Inventory`, `Element`) — đọc/validate
  `testcases/<screen>.inventory.yaml` (trục fan-out).
- `tcformat/coverage.py` `check_depth(inventory, checklists, screen)` → `DepthReport`
  (`expected`, `covered`, `gaps: list[(element_id, technique)]`, `depth_rate`). **Advisory** — chưa gate.
- `skills/generate-testcases/SKILL.md` — flow mới: inventory-first → fan-out (1 element/1 scenario
  mỗi case, gắn tag) → báo cáo kép (`check_coverage` + `check_depth`).

Ranh giới Phase 1 cố ý CHƯA làm (để lại cho 2/3):
- Chưa có **cổng cứng** (exit non-zero) theo depth → Phase 2.
- Chưa in **ma trận element × technique** ra output/report → Phase 2.
- `expected` vẫn là free-text (chưa assertion có cấu trúc) → Phase 3.
- Chưa có **critic linter** tự động soi nhóm còn thiếu → Phase 3.

## 1. Việc Phase 1 để lại (từ final review — đầu vào tốt cho 2/3)

Final review (opus, sạch, "ready to merge") nêu các điểm Minor — đều là *điểm mù của metric advisory*,
chấp nhận trong scope Phase 1, và là việc cụ thể cho Phase 2/3:

1. ✅ **(XONG Phase 2) `link` (và kind lạ) đóng góp 0 ô.** Nay `check_depth` trả `kinds_without_checklist`
   và CLI cảnh báo rõ "0 gaps ≠ đã kiểm". (Không thêm section `link:`; chọn hướng cảnh báo.)
2. ✅ **(XONG Phase 2) `technique` của testcase không được validate vs checklist.** Nay `check_depth`
   trả `unknown_techniques` (technique testcase gắn nhưng không thuộc checklist của kind) — cảnh báo,
   không fail gate.
3. ✅ **(XONG Phase 2) Test `test_tc_depth.py` assert trực tiếp `depth_rate == 0.25`** đã bổ sung
   (`test_depth_rate_partial_is_quarter`).
4. **Field `list` không có generic** (`inventory.elements: list`, `DepthReport.gaps: list`) — đúng theo
   convention `schema.py` hiện tại; để nguyên trừ khi team đổi convention chung.

## 2. Phase 2 — Depth GATE + ma trận trong output  ✅ ĐÃ XONG (merged `main`)

**Mục tiêu:** biến `DepthReport` từ advisory thành cổng cứng (như cổng exit-criteria ở Stage 3) và in
ma trận element × technique để người đọc thấy ô nào trống.

### Đã giao (2026-06-17)

- Spec: `docs/superpowers/specs/2026-06-17-phase2-depth-gate-design.md`
- Plan: `docs/superpowers/plans/2026-06-17-phase2-depth-gate.md`
- Commits: `e1cfa1d..83c04e4` (7 commit feat/fix/polish). Test: **83 passed** (70 nền + 13 mới).

Quyết định đã chốt với user và hiện thực:
- **Cổng ở Stage 1** qua CLI mới `tk-coverage` (`tcformat/coverage_cli.py`, console script
  `tk-coverage`) → exit non-zero khi còn ô element×technique chưa có case và chưa justify.
- **Ngưỡng PASS = 0 gap chưa-justify** (không phải `depth_rate >= X%`).
- **Justify qua `el.skip_techniques: [...]`** trong `inventory.yaml` (Phase-1 điểm mù #?, nay xử lý):
  `check_depth` trừ ô đó khỏi `expected`, ghi vào `DepthReport.skipped` (log rõ, không im lặng).
- **`unknown_techniques`** (điểm mù #2): testcase gắn technique không thuộc checklist của kind →
  liệt kê, **chỉ cảnh báo, KHÔNG fail gate**.
- **`kinds_without_checklist`** (điểm mù #1, vd `link`): element kind không có entry checklist →
  liệt kê, **chỉ cảnh báo, KHÔNG fail gate**.
- **Ma trận element × technique**: `tcformat/depth_matrix.py` `render_depth_matrix(...)` → markdown
  ✓/✗/– (KHÔNG đụng format team A–R); CLI in ra stdout + ghi file qua `--matrix-out`.
- **SKILL.md bước 4**: advisory → **bắt buộc** (chưa `tk-coverage` exit 0 thì chưa sang Stage 2).
- Điểm mù #3 (assert `depth_rate == 0.25`) đã bổ sung trong `test_tc_depth.py`.
- Bonus (từ smoke test): fix `UnicodeEncodeError` khi in ✓/✗/– trên console cp932 (Windows) bằng
  ép UTF-8 cho stdout/stderr trong CLI + regression test.

Smoke màn thật `basic-information-input`: expected 56, covered 40, **16 gaps, exit 1** — cổng chạy
đúng (phản ánh đúng độ phủ ~50–60% mà review tay đã thấy).

`config.py` KHÔNG đổi: ngưỡng "0 gap" không cần trường config số; `checklists_path` đã overridable sẵn.

### (Lưu lại — đề xuất phạm vi ban đầu, đã thực hiện theo các quyết định trên)
- **Cổng cứng:** thêm tham số/ngưỡng (vd `min_depth_rate`, mặc định từ config; hoặc "0 gap chưa justify").
  Quyết định: gate ở đâu? (a) trong `tk-report` Stage 3 cạnh cổng exit-criteria, hay (b) một CLI mới
  `tk-coverage`/bước Stage 1 chặn trước khi sang Stage 2. Khuyến nghị (b) vì depth là về *chất lượng case*,
  thuộc Stage 1, không phải kết quả chạy.
- **`unknown techniques`:** mở rộng `check_depth` trả thêm tập technique mà testcase gắn nhưng không có
  trong checklist của kind tương ứng (xử lý điểm mù #2 ở trên).
- **Cảnh báo kind không có checklist** (#1) — hoặc bổ sung `link:` vào `checklists.yaml`.
- **In ma trận:** một hàm render ma trận (text/markdown, hoặc 1 sheet xlsx phụ — KHÔNG đụng format
  team A–R). Cân nhắc cột: element id | kind | technique | có case? (✓/✗) | testcase id.
- **Cơ chế "justify gap":** cho phép đánh dấu ô không áp dụng (vd field read-only không cần boundary).
  Quyết định: justify ở đâu? Gợi ý: thêm khối optional trong `inventory.yaml` (vd `el.skip_techniques: [...]`)
  để `check_depth` trừ ra khỏi `expected`, có log rõ ràng (không im lặng — theo nguyên tắc dự án).

**File sẽ đụng (dự kiến):** `tcformat/coverage.py` (mở rộng DepthReport), `tcformat/inventory.py`
(thêm `skip_techniques` nếu chọn hướng đó), một module/CLI gate mới, `toolkit/config.py` (ngưỡng),
`SKILL.md` (đổi bước 4 từ advisory → bắt buộc), unit test tương ứng.

**Câu hỏi mở cần chốt với user trước khi code:**
- Gate ở Stage 1 (chặn case kém) hay Stage 3 (chặn lúc báo cáo)?
- Ngưỡng: "0 gap chưa justify" hay `depth_rate >= X%`?
- Cơ chế justify đặt ở inventory hay ở testcase?

## 3. Phase 3 — `expected` có cấu trúc + critic linter  ✅ ĐÃ XONG (merged `main`)

> **3a (structured expected) ĐÃ XONG** — spec `specs/2026-06-18-phase3a-structured-expected-design.md`,
> plan `plans/2026-06-18-phase3a-structured-expected.md`. Commits `082d77c..ac585bf` (3 feat) + doc skill
> `231c2e6`, merge `e71e7b0`. Test: **116 passed**.
> **3b (critic linter) ĐÃ XONG** — spec `specs/2026-06-17-phase3b-critic-linter-design.md`,
> plan `plans/2026-06-17-phase3b-critic-linter.md`. CLI `tk-critic` (advisory + cổng nhẹ depends_on).

**Mục tiêu:** Expected hết chung chung (review điểm #9) + tự động soi nhóm còn thiếu (đóng vai reviewer).

**3a. Structured expected (review #9) — ĐÃ GIAO:**
- Mỗi phần tử `expected` nay là `str` (như cũ) HOẶC dict assertion với đúng 7 key optional:
  `{field, value, enabled, required, button_state, request, redirect}`. Một dict = MỘT subject (`field`);
  nhiều field → nhiều phần tử list.
- **Validate fail-fast** trong `schema.py`: key lạ → `SchemaError`; dict phải có ≥1 key ngoài `field`
  với giá trị non-None (`{}` và `{field: "X"}` bị chặn; `enabled: false`/`required: false` hợp lệ).
- **`flatten_expected(item) -> str`** (module-level, thuần) là NGUỒN DUY NHẤT làm phẳng str/dict → text,
  dùng lại bởi `render_xlsx.py` (cột 8, giữ đánh số `1./2./3.`) và `critic.py` (keyword match depends_on).
  Render gộp clause bằng `"; "` theo thứ tự key cố định (vd "Field A = XXX; Field B disabled") → format
  team cột A–R KHÔNG đổi.
- **Back-compat:** YAML cũ `expected` toàn string chạy nguyên vẹn (roundtrip có test).
- **Quyết định đã chốt:** optional toàn bộ (KHÔNG ép category nào). SKILL.md Stage 1 (`generate-testcases`)
  + Stage 2 (`run-testcases`) đã được bổ sung mô tả dạng dict để generator phát/agent đọc nhất quán.
- File đụng: `tcformat/schema.py`, `tcformat/render_xlsx.py`, `tcformat/critic.py`, các test tương ứng,
  2 SKILL.md.

**3b. Critic linter (mã hoá lại chính bộ review tay):**
- Một bước/agent chạy trên YAML đã sinh, đối chiếu inventory + checklist + business rule, liệt kê nhóm
  còn thiếu (Validation/Boundary/BusinessRule/API/Error/Security/Permission/UserBehavior) — output dạng
  checklist như review gốc.
- Có thể là CLI `tk-critic` (tất định, dựa trên `check_depth` + heuristics) HOẶC một sub-skill AI.
  Khuyến nghị: phần tất định (depth gaps, unknown techniques, kind thiếu) bằng code; phần phán đoán
  (business rule phụ thuộc field, điều kiện required theo mode) để AI trong skill.
- Gắn vào `SKILL.md` như bước cuối trước khi chuyển Stage 2.

**Câu hỏi mở (đã chốt):**
- Structured expected: **optional toàn bộ** (không ép Function/Validation). Flatten gộp `"; "` theo key
  cố định; một dict = một subject (`field`).
- Critic: **hybrid** — phần tất định (depth gaps, unknown techniques, kind thiếu) bằng `tk-critic`; phần
  phán đoán (business rule, required-theo-mode) để AI trong skill.

**Việc tiếp theo (tuỳ chọn — ngoài hướng coverage-depth):**
- Để Stage 1 thực sự *phát* dạng dict expected khi sinh case (SKILL đã mô tả; cần thực hành trên màn thật).
- Tăng độ phủ thực thi Stage 2 / iPad-Safari rồi regenerate báo cáo (xem HANDOFF.md §6).

## 4. Cách chạy / kiểm chứng nhanh (đã có sau Phase 1)

```bash
# Toàn bộ unit test
./.venv/Scripts/pytest -q          # kỳ vọng: 116 passed (sau Phase 3a)

# Cổng depth Stage 1 (Phase 2) — exit non-zero nếu còn gap chưa justify
./.venv/Scripts/tk-coverage --screen testcases/<screen>.yaml --config config.yaml \
    [--inventory testcases/<screen>.inventory.yaml] [--matrix-out reports/<screen>_depth.md]

# Critic review Stage 1 (Phase 3b) — checklist review + cổng nhẹ depends_on chưa-liên-kết
./.venv/Scripts/tk-critic --screen testcases/<screen>.yaml --config config.yaml \
    [--out reports/<screen>_critic.md]

# Báo cáo depth thủ công cho 1 màn (cần inventory.yaml)
./.venv/Scripts/python.exe -c "
from tcformat.schema import load_screen
from tcformat.coverage import check_coverage, check_depth
from tcformat.inventory import load_inventory
from tcformat.checklists import load_checklists
from tcformat.strategy import list_objects
from tcformat.resources import default_strategy
sc  = load_screen('testcases/<screen>.yaml')
inv = load_inventory('testcases/<screen>.inventory.yaml')
refs = {o['ref'] for o in list_objects(default_strategy(),'2_IntergrationTesting') if o['ref']}
cov = check_coverage(sc, refs); dep = check_depth(inv, load_checklists(), sc)
print('missing refs', sorted(cov.missing), 'unknown', sorted(cov.unknown))
print('depth gaps', len(dep.gaps), 'rate', round(dep.depth_rate,2))
"
```

## 5. Quy ước (nhắc lại — theo CLAUDE.md/HANDOFF.md)

- Quy trình: brainstorming → writing-plans → subagent-driven-development. TDD, file nhỏ tập trung.
- **Git:** chỉ commit/add/push khi user xác nhận rõ ràng; KHÔNG trailer `Co-Authored-By`; message thuần.
- Dùng venv: `./.venv/Scripts/python.exe` / `./.venv/Scripts/pytest`.
- Tag mới là **YAML-only**; KHÔNG đổi format team xlsx (cột A–R). Mọi cấu hình overridable qua config
  (`checklists_path`, `strategy_path`, `template_path`) — đổi dự án không sửa code.
- Spec là tiếng Việt; giữ thuật ngữ nhất quán khi sinh case/báo cáo.
