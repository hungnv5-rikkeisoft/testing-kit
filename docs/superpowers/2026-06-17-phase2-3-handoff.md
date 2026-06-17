# Handoff — Coverage-depth Phase 2 & 3

> Cập nhật: 2026-06-17. Tài liệu này để session/agent kế tiếp tiếp nối phần **Phase 2 & 3**
> của hướng "coverage-depth" (sinh test case có chiều sâu). Đọc file này trước, rồi mở
> spec/plan Phase 1 để biết nền đã có.

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

1. **`link` (và kind lạ) đóng góp 0 ô.** `check_depth` dùng `checklists.get(el.kind, [])` → kind không
   có entry trong `checklists.yaml` (vd `link`) lặng lẽ không sinh ô kỳ vọng. "0 gaps" ≠ "đã kiểm link".
   → Phase 2: hoặc thêm section `link:` vào checklist, hoặc cảnh báo khi inventory có kind không có
   checklist entry.
2. **`technique` của testcase không được validate vs checklist.** Gõ sai technique → ô đúng vẫn "gap",
   ô gõ sai bị bỏ qua, im lặng. → Phase 2: thêm khái niệm `unknown techniques` (tương tự `unknown` refs
   trong `check_coverage`) để lộ tag sai.
3. **Test `test_tc_depth.py` không assert trực tiếp `depth_rate == 0.25`** ở case phủ một phần (2 biên
   0.0 và 1.0 đã có). → bổ sung khi đụng tới (nhỏ).
4. **Field `list` không có generic** (`inventory.elements: list`, `DepthReport.gaps: list`) — đúng theo
   convention `schema.py` hiện tại; để nguyên trừ khi team đổi convention chung.

## 2. Phase 2 — Depth GATE + ma trận trong output

**Mục tiêu:** biến `DepthReport` từ advisory thành cổng cứng (như cổng exit-criteria ở Stage 3) và in
ma trận element × technique để người đọc thấy ô nào trống.

**Đề xuất phạm vi:**
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

## 3. Phase 3 — `expected` có cấu trúc + critic linter

**Mục tiêu:** Expected hết chung chung (review điểm #9) + tự động soi nhóm còn thiếu (đóng vai reviewer).

**3a. Structured expected (review #9):**
- Hiện `expected: list[str]` (free-text). Đề xuất cho phép phần tử là assertion có cấu trúc:
  `{field, value, enabled, required, button_state, request, redirect}` (mọi key optional).
- **Ràng buộc cứng:** template team cột A–R cố định → khi render xlsx phải *làm phẳng* assertion về
  text (vd "Field A = XXX; Field B disabled; POST /api/x; redirect /home") để không đổi format deliverable.
  Tức schema/loader nhận cả 2 dạng (str hoặc dict), render gộp thành chuỗi người đọc được.
- File đụng: `tcformat/schema.py` (parse expected hỗn hợp), `tcformat/render_xlsx.py` (flatten khi ghi
  cột 8), test.
- Lưu ý back-compat: YAML cũ `expected` toàn string phải vẫn chạy.

**3b. Critic linter (mã hoá lại chính bộ review tay):**
- Một bước/agent chạy trên YAML đã sinh, đối chiếu inventory + checklist + business rule, liệt kê nhóm
  còn thiếu (Validation/Boundary/BusinessRule/API/Error/Security/Permission/UserBehavior) — output dạng
  checklist như review gốc.
- Có thể là CLI `tk-critic` (tất định, dựa trên `check_depth` + heuristics) HOẶC một sub-skill AI.
  Khuyến nghị: phần tất định (depth gaps, unknown techniques, kind thiếu) bằng code; phần phán đoán
  (business rule phụ thuộc field, điều kiện required theo mode) để AI trong skill.
- Gắn vào `SKILL.md` như bước cuối trước khi chuyển Stage 2.

**Câu hỏi mở:**
- Structured expected: bắt buộc cho case nào (vd chỉ Function/Validation) hay optional toàn bộ?
- Critic: CLI tất định, AI, hay hybrid?

## 4. Cách chạy / kiểm chứng nhanh (đã có sau Phase 1)

```bash
# Toàn bộ unit test
./.venv/Scripts/pytest -q          # kỳ vọng: 70 passed

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
