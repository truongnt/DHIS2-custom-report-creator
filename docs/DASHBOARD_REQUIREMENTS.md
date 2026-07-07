# Dashboard Builder — Requirements

Đặc tả phần **tạo dashboard**. Khi vào tab Dashboard, người dùng **chọn 1 trong 2 cách tạo**
(fork cứng — chọn một lần cho mỗi dashboard, **không trộn lẫn**):

1. **Manual** — workspace **kéo-thả lưới 12 cột** kiểu Apache Superset: kéo chart đã lưu từ
   sidebar vào canvas, snap vào lưới, resize và sắp xếp tự do.
2. **AI** — workspace **chat hội thoại nhiều lượt** với AI: mô tả nhu cầu, AI đề xuất/thêm chart,
   tinh chỉnh qua nhiều lượt.

Hai cách dùng chung phần cuối: Save/Load, Export HTML, Deploy to DHIS2.

> Code nguồn (baseline hiện tại):
> [ui/dashboard_builder_panel.py](../ui/dashboard_builder_panel.py),
> [ui/ai_dashboard_dialog.py](../ui/ai_dashboard_dialog.py),
> [ui/load_dashboard_dialog.py](../ui/load_dashboard_dialog.py),
> [llm/ai_dashboard_planner.py](../llm/ai_dashboard_planner.py),
> [config/dashboard_library.py](../config/dashboard_library.py),
> [config/chart_library.py](../config/chart_library.py),
> [charts/fixed_templates.py](../charts/fixed_templates.py) (`assemble_dashboard`, `generate_card_fragment`),
> wiring trong [ui/app_window.py](../ui/app_window.py) (`_on_export`, `_on_deploy_dashboard`, `_deploy_worker`).
> Tham chiếu thiết kế Superset: sidebar 320px (tab **Charts** + **Layout Elements**), lưới **12 cột**,
> kéo-thả `DragDroppable`, resize bằng **góc dưới-phải**, component types ROW/COLUMN/TAB/HEADER/MARKDOWN/DIVIDER/CHART
> (xem Sources cuối file).
> Liên quan: [METADATA_FILTER_REQUIREMENTS.md](METADATA_FILTER_REQUIREMENTS.md) (descriptions làm ngữ cảnh AI),
> [docs/charts/](charts/) (cấu hình từng chart).

> ⚠️ **Trạng thái**: phần lớn doc mô tả **thiết kế mục tiêu** (grid kéo-thả + chat). Baseline code
> hiện tại là: Manual = danh sách card có nút `+ Add` (chưa kéo-thả/lưới), AI = `AiDashboardDialog`
> sinh-một-lần (chưa hội thoại). Khoảng cách giữa hiện tại và mục tiêu xem **PART J — Migration / TO-DO**.

---

## PART A — Điểm vào & chọn chế độ (Mode selection)

```
Vào tab Dashboard
        │
        ▼
┌──────────── Chọn cách tạo dashboard ────────────┐
│   ┌────────────────┐      ┌────────────────┐    │
│   │  🖱  Manual      │      │  🤖  AI Chat    │    │
│   │  Kéo-thả chart  │      │  Mô tả → AI    │    │
│   │  vào lưới       │      │  dựng giúp     │    │
│   └────────────────┘      └────────────────┘    │
└──────────────────────────────────────────────────┘
   chọn Manual ─────────┐         └───────── chọn AI
        ▼                                    ▼
  Workspace LƯỚI (PART C)            Workspace CHAT (PART D)
```

- **REQ-DASH-01** — Vào Dashboard Builder lần đầu (hoặc bấm **New dashboard**) → hiện **màn chọn chế độ** với 2 thẻ: **Manual** và **AI Chat**.
- **REQ-DASH-02** — Chọn chế độ → UI **rẽ nhánh** sang workspace tương ứng. Đây là **fork cứng**: một dashboard chỉ thuộc **một** chế độ; **không trộn** card manual và AI trong cùng dashboard.
- **REQ-DASH-03** — Chế độ được **ghi vào dashboard** (`mode: "manual" | "ai"`). Nạp lại dashboard (PART E) → tự mở đúng workspace theo `mode`.
- **REQ-DASH-04** — **Đổi chế độ** = tạo dashboard mới (sau xác nhận nếu canvas/chat hiện có nội dung chưa lưu); không có nút trộn hai luồng.
- **REQ-DASH-05** — Panel nhận `callbacks`: `on_export(cards)`, `on_deploy(name, cards)`, `on_switch_to_editor()`; và `set_context(metadata, descriptions, base_url)` cấp ngữ cảnh cho AI. Trước khi set context, AI vẫn chạy được ở **mock mode**.

---

## PART B — Chart source (sidebar trái, dùng cho Manual)

> Tương đương BuilderComponentPane của Superset, nhưng nguồn là **chart đã lưu** của app
> (`config.chart_library.load_charts()`), không phải tạo chart inline.

- **REQ-DASH-LIB-01** — Sidebar **cố định ~240–320px**, có **tab Charts** liệt kê chart đã lưu; mỗi item hiển thị **tên** (`name`/`title`) + **nhãn template** (`template_label`/`template_id`).
- **REQ-DASH-LIB-02** — (Tùy chọn, theo Superset) **tab Layout Elements**: Header / Markdown / Divider có thể kéo vào canvas để chèn tiêu đề/ghi chú/đường kẻ.
- **REQ-DASH-LIB-03** — Ô **search** lọc chart theo tên (realtime, không phân biệt hoa thường).
- **REQ-DASH-LIB-04** — Mỗi item là **nguồn kéo** (`DragDroppable`): kéo vào canvas để thêm. Vẫn giữ nút **`+ Add`** như lối tắt (thêm vào ô trống kế tiếp).
- **REQ-DASH-LIB-05** — Nút **`✕`** trên item xóa chart khỏi **library** (có xác nhận) → `delete_chart(id)` + refresh. Xóa trong library **không** ảnh hưởng card đã đặt trên canvas (canvas giữ **bản sao** config).
- **REQ-DASH-LIB-06** — Library trống → placeholder "No saved charts yet. Build a chart in Chart Editor and click 'Save to Library'." Nút **`↺ Refresh`** và **`← Chart Editor`**.

---

## PART C — Manual mode: lưới kéo-thả 12 cột (Superset-style)

### C.1 Canvas & lưới

- **REQ-DASH-GRID-01** — Canvas là **lưới 12 cột** đáp ứng (responsive). Mỗi card chiếm `w` cột (1–12) và có chiều cao `h` (theo hàng lưới); vị trí xác định bởi `(x, y, w, h)`.
- **REQ-DASH-GRID-02** — **Kéo chart từ sidebar** thả vào canvas → card snap vào ô lưới gần nhất; hiện **placeholder/đường gióng** trong lúc kéo (drop indicator).
- **REQ-DASH-GRID-03** — **Resize**: kéo **góc dưới-phải** của card để đổi `w`/`h`; card snap theo bước lưới (không cho `w` < 1 hoặc > 12).
- **REQ-DASH-GRID-04** — **Reposition**: kéo thân card sang vị trí khác; các card khác **dịch chỗ** (reflow) để nhường ô, không chồng đè.
- **REQ-DASH-GRID-05** — Mỗi card có nút **`✕`** để gỡ khỏi canvas; gỡ xong lưới reflow lấp khoảng trống.
- **REQ-DASH-GRID-06** — Card hiển thị (chế độ edit) **viền nét đứt** + tiêu đề + dòng meta `"{template_label} • {w}col • {N} src • {mode_lbl}"` (theo card hiện có). Trong chế độ xem (preview/export) là chart thật.
- **REQ-DASH-GRID-07** — **Empty state**: "Drag and drop charts from the left to build your dashboard."

### C.2 Header & trạng thái

- **REQ-DASH-GRID-08** — Header canvas: ô **Report name** (sửa được), bộ đếm `"{n} chart(s)"`, các nút Save/Load/Export/Deploy/Clear all.
- **REQ-DASH-GRID-09** — `Export HTML` & `Deploy to DHIS2` **disabled** khi canvas rỗng; **enabled** khi có ≥1 card. **Clear all** xóa toàn bộ (có xác nhận).
- **REQ-DASH-GRID-10** — `get_cards()` trả **bản sao** danh sách card kèm `layout` (vị trí lưới) của từng card, đúng thứ tự hiển thị.

---

## PART D — AI mode: chat hội thoại nhiều lượt

> Thay `AiDashboardDialog` sinh-một-lần bằng **khung chat** trong workspace; dùng cùng
> `llm.ai_dashboard_planner` làm backend.

### D.1 Khung chat

```
┌──────────────── AI Dashboard Chat ─────────────────┐
│ 🧑 Làm dashboard sốt rét theo tháng + bản đồ        │
│ 🤖 Đề xuất 4 chart:                                 │
│      ▸ Monthly Cases (bar)        [+ Thêm]          │
│      ▸ District Map (area)        [+ Thêm]          │
│      [Thêm tất cả]                                  │
│ 🧑 Đổi chart 2 thành line, thêm bảng xếp hạng cơ sở │
│ 🤖 Đã cập nhật. [+ Thêm Facility Ranking]           │
├─────────────────────────────────────────────────────┤
│ [nhập tin nhắn .............................] [ ➤ ] │
└─────────────────────────────────────────────────────┘
```

- **REQ-DASH-AI-01** — Workspace AI có **lịch sử hội thoại** (bong bóng user/assistant) + ô nhập + nút gửi. Giữ ngữ cảnh qua **nhiều lượt** trong cùng phiên dashboard.
- **REQ-DASH-AI-02** — **Quick start** (preset intents) đặt sẵn lượt đầu; chọn preset → điền sẵn ô nhập.
- **REQ-DASH-AI-03** — Mỗi lượt assistant có thể kèm **đề xuất chart** dạng thẻ có nút **`+ Thêm`** / **`Thêm tất cả`**; bấm → card được thêm vào dashboard AI (kèm rationale).
- **REQ-DASH-AI-04** — Lượt sau có thể **tinh chỉnh**: đổi loại chart, thêm/bớt chart, đổi tiêu đề… AI nhận **trạng thái dashboard hiện tại + lịch sử** làm ngữ cảnh.
- **REQ-DASH-AI-05** — Gọi AI chạy **thread nền** (QThread); trong lúc chờ hiện trạng thái "Generating…", khóa ô gửi. Lỗi → hiện thông báo lỗi trong khung chat, không crash.
- **REQ-DASH-AI-06** — Dashboard AI hiển thị **preview/danh sách card** mà AI đã thêm (sắp xếp tự động, mặc định 2 card/hàng ~ col-6); người dùng có thể **gỡ** card. Không có kéo-thả lưới ở chế độ AI (đó là đặc quyền Manual).

### D.2 Backend planner (khớp `llm/ai_dashboard_planner.py`)

- **REQ-DASH-AI-07** — Không có `ai_client` → **mock mode**: chọn `mock_key` theo preset (1→`malaria_overview`, 2→`supply_chain`, 3→`performance_review`, mặc định `malaria_overview`). Header hiển thị "Mock mode" vs "Model: {model}".
- **REQ-DASH-AI-08** — `recommend_charts()` ưu tiên `mock_response` > `mock_key` > `ai_client`; không có cái nào → `ValueError`. Real mode mặc định `claude-haiku-4-5-20251001`; parse JSON chịu được markdown fences.
- **REQ-DASH-AI-09** — Mock dùng placeholder `__FIRST__`/`__SECOND__` → `_resolve_placeholders` thay bằng 2 UID đầu của `de_list`; rec không resolve được UID bị loại.
- **REQ-DASH-AI-10** — `_validate` chỉ giữ rec có `chart_type` ∈ catalog, `de_uid` ∈ `de_list`, `title` không rỗng.
- **REQ-DASH-AI-11** — `recs_to_chart_configs` ánh xạ `kind` → `metrics[0].type` (indicator/program_indicator→`indicator`; data_element→`aggregate`; tracker_de/tracked_attr→`tracker_numeric`; khác→`aggregate`) và sinh config: `template_id`, `title`, `metrics=[{dx_uid,label,type}]`, `dims={ou_uid}`, `options={}`, cờ `_ai_generated=True`, `_ai_rationale`.
- **REQ-DASH-AI-12** — Ngữ cảnh AI build từ `metadata` + `descriptions` cục bộ (≤ `max_items=80`); descriptions **không** gửi lên DHIS2.
- **REQ-DASH-AI-13** — Card sinh bởi AI **phải đánh dấu `mode="ai"`** để export/deploy phân loại đúng (xem REQ-DASH-EXP-02). *(Lưu ý: baseline hiện tại chỉ set `_ai_generated`, chưa set `mode` — xem PART J.)*

---

## PART E — Save / Load dashboard (chung cả 2 chế độ)

> Khớp `config/dashboard_library.py` → `config/dashboard_library.json`.

- **REQ-DASH-SAVE-01** — **Save**: bắt buộc **Report name** (rỗng → cảnh báo + focus); canvas/chat rỗng → "Add at least one chart before saving".
- **REQ-DASH-SAVE-02** — `save_dashboard(name, cards)` **upsert theo `name`** (trùng tên → ghi đè, giữ `id` + `created_at`, cập nhật `updated_at`). Entry: `id` (uuid 10 ký tự), `name`, `cards`, `created_at`, `updated_at` (ISO, giây).
- **REQ-DASH-SAVE-03** — Entry **phải lưu thêm** `mode` (manual|ai) và — với Manual — `layout` lưới của từng card; với AI có thể lưu `chat_history`. *(Mở rộng schema so với baseline — PART J.)*
- **REQ-DASH-SAVE-04** — **Load**: không có dashboard nào → "No saved dashboards found". Có → `LoadDashboardDialog` liệt kê `"{name} · {N} charts · {updated:10}"`; chọn (OK/double-click) → trả dashboard; OK khi chưa chọn → "Select a dashboard first".
- **REQ-DASH-SAVE-05** — Nạp → **xóa workspace hiện tại không hỏi**, mở đúng `mode`, phục dựng card (+ vị trí lưới nếu manual), set Report name = tên dashboard.
- **REQ-DASH-SAVE-06** — Dialog có **Delete selected** (xác nhận) → `delete_dashboard(id)` + gỡ khỏi danh sách.
- **REQ-DASH-SAVE-07** — `load_dashboards()` chịu lỗi: file thiếu/JSON hỏng → trả `[]` (không crash).

---

## PART F — Export HTML

> Khớp `app_window._on_export` + `charts.fixed_templates.assemble_dashboard`.

- **REQ-DASH-EXP-01** — Không có card → "No cards to export".
- **REQ-DASH-EXP-02** — Tách card: **fixed** (`mode != "ai"`) → `assemble_dashboard(fixed, title)`; card **AI** (`mode=="ai"` có `html_path`) → mở file riêng.
- **REQ-DASH-EXP-03** — `assemble_dashboard` ghép từng card qua `generate_card_fragment(n, cfg)`, nối các `initChartN(ou,pe)` vào `_SHARED_SCRIPT`, trả trang HTML hoàn chỉnh (`_PAGE_SHELL`). **Manual mode**: bố cục HTML nên phản ánh `layout` lưới (col-width của từng card).
- **REQ-DASH-EXP-04** — Ghi `debug/{YYYYMMDD_HHMMSS}_dashboard.html` (UTF-8) rồi mở trình duyệt; status hiện tên file.
- **REQ-DASH-EXP-05** — `generate_card_fragment` định tuyến: `plugin_id` → plugin; `template_id` → `migrate_old_config` → plugin; fallback `_build_per_card_js`. Lỗi route trên → rơi xuống route dưới, không crash.

---

## PART G — Deploy to DHIS2

> Khớp `app_window._on_deploy_dashboard` + `_deploy_worker` + `dhis2.report_api`.

- **REQ-DASH-DEP-01** — Bắt buộc **Report name**; chưa connect (`self._client` None) → "Connect to DHIS2 first"; không có card → "No cards to deploy".
- **REQ-DASH-DEP-02** — Chỉ deploy card **fixed**; HTML qua `fix_cdn_links()` trước khi gửi.
- **REQ-DASH-DEP-03** — Chạy **thread nền** (`_deploy_worker`); progress indeterminate; tạo report qua `create_report(client, name, html)`.
- **REQ-DASH-DEP-04** — Thành công → `uid`, `report_url(base, uid)`, `record_usage`, hỏi "Open in DHIS2 now?". Thất bại → "Deploy failed: {msg}".

---

## PART H — Data model

- **REQ-DASH-MODEL-01** — **Card config** = chart config dict (`template_id`/`plugin_id`, `title`, `metrics`, `dims`, `options`, `chart_color`, `col_width`, …) như Chart Editor sinh ra; AI card thêm `_ai_generated`, `_ai_rationale`, và `mode="ai"`.
- **REQ-DASH-MODEL-02** — **Dashboard entry** (`dashboard_library.json`):
  ```json
  {
    "id": "ab12cd34ef", "name": "…",
    "mode": "manual" | "ai",
    "cards": [ {<chart config>, "layout": {"x":0,"y":0,"w":6,"h":4}} ],
    "chat_history": [ {"role":"user|assistant","text":"…"} ],   // chỉ mode ai
    "created_at": "…", "updated_at": "…"
  }
  ```
  `layout` chỉ bắt buộc với `mode="manual"`; `chat_history` chỉ với `mode="ai"`.

---

## PART I — Acceptance / Test

- **Backend planner & library** (tự động):
  ```
  python -m pytest tests/test_ai_planner.py -v   →  all pass (gồm TestDashboardLibrary)
  python -m pytest tests/ -v                     →  all pass
  ```
  Mapping: REQ-PLANNER-13/14 ↔ REQ-DASH-SAVE-02/06; REQ-PLANNER-04/05 ↔ REQ-DASH-AI-07/09;
  REQ-PLANNER-06/07/08 ↔ REQ-DASH-AI-10; REQ-PLANNER-09 ↔ REQ-DASH-AI-08;
  REQ-PLANNER-12 ↔ REQ-DASH-AI-08; REQ-PLANNER-10 ↔ REQ-DASH-AI-11.
- **UI tích hợp**: [scripts/manual/test_ui.py](../scripts/manual/test_ui.py).

### Checklist thủ công

1. Vào tab Dashboard → thấy **màn chọn chế độ** (Manual / AI).
2. **Manual**: kéo 2–3 chart từ sidebar vào lưới → snap đúng; resize góc → đổi col-width; kéo đổi chỗ → reflow; `✕` gỡ → lấp khoảng trống.
3. **Manual**: Save → Clear all → Load → lưới (vị trí + col-width) khôi phục đúng.
4. **AI**: nhập intent → AI đề xuất → `+ Thêm` → card xuất hiện; gửi lượt 2 ("đổi chart 2 thành line") → cập nhật đúng; lịch sử chat giữ nguyên.
5. **AI**: Save → Load → mở lại đúng chế độ AI (và lịch sử chat nếu có).
6. **Export HTML** (cả 2 mode) → trang dashboard render đúng bố cục.
7. (Đã connect) **Deploy** → report tạo thành công, mở URL DHIS2.

---

## PART K — Dashboard filters (shared OU + Period)

> **Tham chiếu Superset Native Filters** (xem Sources): Superset có thanh filter áp cho **tất cả chart**
> với các loại **Value** (chọn giá trị), **Time range** (khoảng thời gian), **Time grain** (độ mịn thời gian),
> hỗ trợ **default values** và **scope** (all charts / subset). Khi đổi filter, giá trị merge vào query của chart.
>
> **Ánh xạ sang DHIS2**: chart DHIS2 luôn truy vấn theo 3 chiều `dx`/`pe`/`ou`. Hai chiều `pe` và `ou`
> **dùng chung** cho mọi chart → là ứng viên tự nhiên cho dashboard filter:
> - **Value filter → Org Unit (`ou`)**: chọn đơn vị/cấp tổ chức.
> - **Time range → Period (`pe`)**: relative (LAST_12_MONTHS, THIS_YEAR…) hoặc cố định.
> - **Time grain → period type** (tháng/quý/năm) — đã có trong dropdown period.
> Scope = **tất cả chart** (vì `pe`/`ou` vốn dùng chung) — không cần scope-subset như Superset.

- **REQ-DASH-FILTER-01** — Dashboard có **filter dùng chung**: Period + Org Unit, áp cho **mọi chart**.
  Builder có nút **🎚 Filters** mở `DashboardFilterDialog` để đặt **giá trị mặc định**.
- **REQ-DASH-FILTER-02** — Dialog: combo **Default period** (8 relative options) + **Default org unit**
  (User OU / sub-units / sub-x2-units) — khớp options thanh filter trong HTML sinh ra.
- **REQ-DASH-FILTER-03** — Thanh filter **đã có sẵn** trong `_PAGE_SHELL` (`ouSelect`/`peSelect` + nút "↻ Load data"
  = Apply). `assemble_dashboard(..., filters=)` / `generate_preview_page` **inject default** qua
  `DEFAULT_PE`/`DEFAULT_OU`; đổi filter → `loadData()` gọi lại `initChartN(ou,pe)` cho **tất cả** chart.
- **REQ-DASH-FILTER-04** — Preview/Export/Deploy đều truyền `filters` hiện tại vào `assemble_dashboard`.
- **REQ-DASH-FILTER-05** — `filters` được **lưu cùng dashboard** (`save_dashboard(..., filters=)`) và **khôi phục** khi load.

### Filter V2 — áp Superset Value (phân cấp) + Time Range vào DHIS2

> **Value filter của Superset là phân cấp** (cascading: child phụ thuộc parent). DHIS2 OU vốn là cây
> (Quốc gia → Tỉnh → Huyện → Xã) nên ánh xạ tự nhiên sang **chọn theo CẤP**: thay vì 1 đơn vị, chọn
> "tất cả đơn vị ở Level N". DHIS2 analytics nhận `ou:LEVEL-N` → trả mọi OU ở cấp đó.
> **Time Range filter** của Superset → DHIS2 cho chọn **khoảng tháng từ→đến**, mở rộng thành danh sách `pe`.

- **REQ-DASH-FILTER-06** — **OU theo cấp**: thanh filter có nhóm **"By level"** với Level 1–4
  (value `LEVEL-1..LEVEL-4`). Chọn → mọi chart truy vấn `ou=LEVEL-N` (vd Level 2 = tất cả tỉnh).
  Hoạt động interactive (viewer đổi được), và đặt được làm **default** trong dialog.
- **REQ-DASH-FILTER-07** — **Khoảng thời gian tùy chỉnh** (Time Range): option **"Custom range…"** trong
  period; chọn → hiện 2 dropdown **From / To** (tháng). `loadData()` mở rộng thành `pe=YYYYMM;…;YYYYMM`
  cho mọi chart. Hàm `expandMonths(from,to)` lo việc liệt kê tháng (bao gồm cả 2 đầu).
- **REQ-DASH-FILTER-08** — `loadData()` **fallback** về `DEFAULT_OU`/`DEFAULT_PE` khi select rỗng; default
  không khớp option có sẵn thì được **chèn thành option** và chọn (vd range default → option "Selected range").
- **REQ-DASH-FILTER-09** — Filter model V2 (lưu/đọc): `{"period": {...}, "ou": {...}}` (dạng cũ
  `{"period": str, "ou": str}` vẫn **đọc ngược tương thích**). `_apply_filter_defaults` chấp nhận cả hai.

### Filter V3 — danh sách filter động (Superset Native Filters đầy đủ hơn)

> Superset cho **thêm nhiều filter**, mỗi filter chọn **nguồn data + loại + value + alias + scope**
> (chart nào áp dụng). V3 đưa mô hình đó vào: filter là một **DANH SÁCH** thay vì cố định OU+Period.

- **REQ-DASH-FILTER-10** — **Filters Manager** ([ui/dashboard_filters_manager.py](../ui/dashboard_filters_manager.py)):
  thêm/xoá nhiều filter; mỗi filter có **alias**, **type** (Org unit / Period / Dimension),
  **value/default**, và **scope** = *All charts* hoặc *chọn từng chart*. Mở từ nút **🎚 Filters**.
- **REQ-DASH-FILTER-11** — Model V3 = `list[{id, alias, type, default, from, to, scope}]`
  (`scope` = `"all"` hoặc `[chart_index…]`). `_normalize_filters` đọc ngược V1/V2 (flat dict) → list,
  và luôn đảm bảo có ≥1 filter **ou** + **period** (mọi chart cần `ou`/`pe`).
- **REQ-DASH-FILTER-12** — HTML inject `DASH_FILTERS` (JSON) + `CHART_COUNT`. `applyFilterMeta()` gán
  alias cho 2 control chính (OU/Period) và render các filter **phụ** vào `#filterBarExtra`.
  `loadData()` **định tuyến theo scope**: chart `n` nhận `ou`/`pe` của filter in-scope (override sau cùng thắng),
  gọi `window['initChart'+n](ouForChart(n), peForChart(n))`.
- **REQ-DASH-FILTER-13** — **Dimension filter áp vào query chart**: filter type *Dimension* có **source**
  (UID chiều DHIS2) + **value**; `dimExtraFor(n)` dựng `&filter=<source>:<value>` cho mọi chart in-scope,
  `initChartScoped(n)` tạm patch `dhis2Get` để **nối filter vào URL analytics** của chart đó. Khi có dimension
  filter, `loadData()` chạy **tuần tự** (tránh race khi patch `dhis2Get` toàn cục dưới `Promise.all`).
  Control hiển thị là ô nhập value (viewer đổi được).

Code: [ui/dashboard_filters_manager.py](../ui/dashboard_filters_manager.py),
[ui/dashboard_filter_dialog.py](../ui/dashboard_filter_dialog.py) (options + month helper),
`charts/fixed_templates.py::_normalize_filters`/`_apply_filter_defaults`, bar trong `_PAGE_SHELL`/`_SHARED_SCRIPT`.
Test: [tests/integration/test_dashboard_filters.py](../tests/integration/test_dashboard_filters.py) (22),
[tests/test_preview.py::TestFilterBarV2], e2e `test_filter_bar_v3_dynamic` (+ screenshot).

- **REQ-DASH-FILTER-14** — **Chọn nguồn từ metadata**: với filter *Dimension*, manager hiện picker
  **Program → DE/PA → Value** dựng từ metadata đã load (`program_stage_data_elements` = DE tracker,
  `tracked_entity_attributes` = program attribute). `source` = `<stageId>.<uid>` (DE tracker) hoặc `<uid>` (PA);
  **Default** lấy từ `optionSet.options` của DE/PA (tùy chọn). Chưa load metadata → fallback ô nhập UID tự do.
  `_build_dim_sources(metadata)` dựng danh sách nguồn.
- **REQ-DASH-FILTER-15** — **Control theo kiểu dữ liệu** (không cố định value lúc config): thanh dashboard
  render control cho **người xem chọn** tùy `value_type` của DE/PA (`_control_type`):
  optionSet → **dropdown** (kèm mục "(all)" = bỏ lọc); số → ô **number**; ngày → **date**; còn lại → **text**.
  "Default" ở manager chỉ là giá trị khởi tạo (tùy chọn). `value_type` + `options` được lưu trong filter
  để bar render đúng mà không cần metadata lúc sinh HTML.

> **Mở rộng tương lai** (chưa làm): **multi-select** (Superset multiSelect); **cross-filter**
> (click chart để lọc chart khác); **cascading** (filter con phụ thuộc cha); thêm DE aggregate/category combo
> làm nguồn dimension.

---

## PART J — Trạng thái triển khai

Hầu hết thiết kế mục tiêu **đã được code + test** (291 pass toàn suite, có screenshot evidence). Code mới:
[ui/dashboard_grid.py](../ui/dashboard_grid.py) (GridCanvas) +
[ui/dashboard_builder_panel.py](../ui/dashboard_builder_panel.py) (chooser, AI chat, mode fork).
Test: `tests/integration/test_dashboard_*.py`.

1. ✅ **Mode selection (REQ-DASH-01..05)** — `QStackedWidget` 3 trang (chooser/manual/ai), "⇄ Change mode"
   (xác nhận nếu chưa lưu), `mode` lưu/khôi phục qua `save_dashboard`/`load_dashboard_entry`.
2. ✅ **Manual grid (REQ-DASH-GRID-01..10)** — `GridCanvas`: lưới 12 cột auto-flow, reflow khi resize/remove/reorder,
   nút ⊟/⊞ + **3 grip resize**: cạnh phải (↔ width), cạnh dưới (↕ height), góc (↘ cả hai) — đặt là **ô layout thật**
   nên không bị che. **Chiều cao độc lập**: card dùng `setFixedHeight` + `AlignTop`, rowSpan=1 → kéo cao 1 card
   không ép card cùng hàng cao theo (khắc phục hạn chế hàng đồng-cao của `QGridLayout`). Card **bền** (cache theo item).
   Lưu `(x,y,w,h)`. *Gesture chuột thô verify thủ công; math (`set_width`/`set_height`/`move`/`external_drop`) có test.*
3. ✅ **Preview button (REQ-DASH-EXP Preview)** — nút **👁 Preview** (manual + AI) assemble dashboard hiện tại và
   mở trong browser qua `preview_server` (giống Chart Editor). *(Thay cho ý tưởng nhúng web view mỗi card — bỏ vì
   QWebEngineView native surface che mất grip resize và nặng; card giờ là tile cấu hình nhẹ + nút Preview.)*
3. ✅ **AI chat (REQ-DASH-AI-01..06)** — khung chat nhiều lượt: history, presets, gợi ý có `+ Add`/`Add all`,
   strip "Added" gỡ được, refine truyền trạng thái dashboard hiện tại làm ngữ cảnh. Chạy planner trên thread nền.
4. ✅ **`mode="ai"` cho card AI (REQ-DASH-AI-13)** — `_ai_add_card` set `mode="ai"`; `app_window` export/deploy chỉ
   loại card AI **có `html_path`** (pre-rendered cũ), còn card AI-chat được assemble như card thường.
5. ✅ **Schema mở rộng (REQ-DASH-SAVE-03 / REQ-DASH-MODEL-02)** — `save_dashboard` lưu `mode` (+ `chat_history`);
   manual lưu kèm `layout`; đọc ngược tương thích (thiếu `mode`→`manual`).
6. ✅ **Export theo layout (REQ-DASH-EXP-03)** — col-width của từng card trên grid được stamp vào cfg → `assemble_dashboard`
   tôn trọng độ rộng cột.

### Còn lại (GAP trong traceability — có lý do, KHÔNG fake-pass)

- **REQ-DASH-AI-09..12** — logic planner thuần (resolve placeholder, validate, recs→config, parse JSON). Đã test
  đầy đủ trong [tests/test_ai_planner.py](../tests/test_ai_planner.py) dưới **REQ-PLANNER-04..12**; chat gọi đúng các hàm này.
- **REQ-DASH-DEP-02..04** — deploy thật lên DHIS2 (`fix_cdn_links`, thread nền, `create_report`). Cần instance thật →
  verify thủ công / E2E; guard (DEP-01) đã test.
- **REQ-DASH-EXP-04** — ghi file `debug/*.html` + mở trình duyệt (side-effect) → verify thủ công.
- **REQ-DASH-EXP-05** — routing `generate_card_fragment` (plugin/template/fallback) đã phủ trong `tests/test_preview.py`.
- **REQ-DASH-LIB-02** — tab "Layout Elements" (Header/Markdown/Divider) là **tùy chọn** trong spec; chưa build.

---

## PART L — Custom CSS chung cho dashboard

> Superset cho phép mỗi dashboard đính kèm **CSS tùy chỉnh** (Edit dashboard → Edit CSS) áp cho toàn trang. Ta làm tương tự: một khối CSS **cấp dashboard** áp cho tất cả card khi Preview / Export / Deploy.

- **REQ-DASH-CSS-01** — Dashboard có một trường **`custom_css`** (string, mặc định `""`) — CSS thô do người dùng nhập, áp chung cho cả trang.
- **REQ-DASH-CSS-02** — Nút **"🎨 CSS"** trên thanh công cụ (cả Manual và AI) mở dialog soạn CSS (`ui/dashboard_css_dialog.py`): ô `QPlainTextEdit` monospace, có placeholder ví dụ selector (`.card-header`, `body`, `.chart-wrapper`…), nút OK/Cancel. OK lưu vào `self._dash_custom_css`.
- **REQ-DASH-CSS-03** — `assemble_dashboard(..., custom_css=...)` chèn CSS người dùng vào **cuối `<head>`** trong một khối `<style id="dashboard-custom-css">…</style>` — đặt **sau** khối style mặc định để nó **override** được style mặc định. CSS rỗng → không chèn thẻ style thừa.
- **REQ-DASH-CSS-04** — `custom_css` được **lưu/nạp** cùng dashboard entry (`dashboard_library.save_dashboard(..., custom_css=...)`; `load_dashboard_entry` khôi phục). Chỉ ghi khoá khi khác rỗng.
- **REQ-DASH-CSS-05** — Preview, Export, và Deploy đều truyền `custom_css` xuống `assemble_dashboard` (đồng nhất một nguồn).
- **REQ-DASH-CSS-06** — Dialog có **danh sách mẫu style** (`STYLE_TEMPLATES` trong `ui/dashboard_css_dialog.py`): `Base (mặc định hiện tại)` + các theme (`Dark`, `Compact`, `Rounded / soft`, `Health green`, `Print / report`). Chọn mẫu → nạp CSS vào ô soạn (hỏi xác nhận nếu đang có nội dung). Mẫu **Base** phải nhắm đúng các selector mà trang thật sự dùng (`.card-header`, `#controls`, `.chart-wrapper`…) để sửa là ghi đè được style mặc định (không phải CSS "chết").
- **REQ-DASH-CSS-07** — Nút **"🎨 Chèn màu…"** mở `QColorDialog`; chọn màu → chèn mã hex (`#rrggbb`) vào vị trí con trỏ trong ô soạn (`insert_at_cursor`).
- **REQ-DASH-CSS-08** — Khoảng cách giữa các card điều khiển bằng gutter lưới Bootstrap: `card_spacing_css(px)` → `.container-fluid .row { --bs-gutter-x/-y: {px}px }` **và** vô hiệu `mb-4` (`margin-bottom:0 !important`) để khoảng cách đúng bằng `px`. Mẫu **Base** có sẵn dòng gutter 24px để sửa trực tiếp trong editor (không cần control riêng trên thanh công cụ).
- **REQ-DASH-CSS-09** — Sau khi **Apply**, nếu đang mở preview (`preview_server.is_preview_open()`), tự **đẩy HTML mới** để tab preview **tự reload** (không mở tab mới). Không có preview mở → không ép mở.
- **REQ-DASH-CSS-10** — Người dùng **lưu template riêng**: nếu sửa một template rồi Apply mà CSS khác mọi template đã biết, dialog hỏi **tên** để lưu thành template mới (`config/css_template_library.py` → `css_templates.json`). Template người dùng được **gộp vào dropdown** (built-in + user) và chọn lại được lần sau. Gõ CSS từ đầu (không xuất phát từ template) thì **không hỏi**.
- **REQ-DASH-CSS-11** — Mở dialog: dropdown **tự chọn đúng tên template** khớp với `custom_css` hiện tại (so khớp nội dung); nếu không khớp template nào → về dòng gợi ý. Chèn khoảng cách card **thêm vào cuối** editor (không nhảy lên đầu).
- **REQ-DASH-CSS-12** — Mọi template trong `STYLE_TEMPLATES` viết **mỗi rule một dòng, kèm comment** nói rõ style đó làm gì (dễ đọc/sửa).
- **REQ-DASH-CSS-13** — Dropdown **"Filter bar"** (`FILTER_LAYOUTS`) chèn CSS bố cục cho `#controls`. Mỗi vị trí có **cả sticky lẫn scroll**: `Top bar · sticky/scroll`, `Left sidebar · sticky/scroll`, `Right sidebar · sticky/scroll` (6 kiểu). **sticky** = `position:fixed/sticky` (dính, luôn thấy); **scroll** = `position:static`/`float` (cuộn trôi theo trang). Các snippet **chỉ đổi bố cục** (không đặt màu) nên **tương thích mọi theme**; dùng `!important` để thắng style inline của `#controls` (position/top/align-items…). Chọn bố cục → **thêm vào cuối** editor, combo reset về gợi ý. Nhãn UI đều tiếng Anh cho khớp app.

---

## Sources

- [Creating Your First Dashboard — Apache Superset](https://superset.apache.org/user-docs/using-superset/creating-your-first-dashboard/)
- [Dashboard System — apache/superset (DeepWiki)](https://deepwiki.com/apache/superset/3.3-dashboard-system)
- [Native Filters — apache/superset (DeepWiki)](https://deepwiki.com/apache/superset/3.4-native-filters)
