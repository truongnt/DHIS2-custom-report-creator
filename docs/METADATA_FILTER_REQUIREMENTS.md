# Metadata Config, Filter & Descriptions — Requirements

Đặc tả phần **cấu hình metadata**: chọn phạm vi (filter) để tải metadata, và **viết/lưu mô tả
(description)** cho từng Data Element / Program Attribute / Indicator.

> Code nguồn: [ui/filter_config_dialog.py](../ui/filter_config_dialog.py),
> [ui/metadata_editor_dialog.py](../ui/metadata_editor_dialog.py),
> [config/descriptions.py](../config/descriptions.py),
> [dhis2/metadata.py](../dhis2/metadata.py),
> flow trong [ui/app_window.py](../ui/app_window.py) (`_on_open_filter_config`, `_load_metadata_worker`, `_open_metadata_editor`).
> Liên quan: [DATA_EXPORT_REQUIREMENTS.md](DATA_EXPORT_REQUIREMENTS.md) (tải dữ liệu mẫu theo scope đã chọn).

---

## PART A — Filter / Scope (cấu hình metadata)

### A.1 Điểm vào

- **REQ-FILTER-01** — Nút **`⚙ Filters && Load Metadata`** ở Config panel, **disabled** đến khi kết nối DHIS2 thành công.
- **REQ-FILTER-02** — Nhấn nút → mở `FilterConfigDialog` (modal). Hủy → không thay đổi gì. Apply → lưu `filter_cfg` và tải lại metadata.

### A.2 Bố cục dialog — **CHỈ giữ Tầng 1 (SCOPE)**

Dialog chỉ còn **một tầng**: chọn Programs và Datasets xác định phạm vi dữ liệu.

```
┌───────────────────────────────────────────────┐
│  ① SCOPE — Programs        |     Datasets       │
│  [All][None]               |  [All][None]        │
│  ☑ Program A      Tracker  |  ☑ Dataset X  Monthly│
│  ☐ Program B      Event    |  ☐ Dataset Y  Yearly │
├───────────────────────────────────────────────┤
│  Summary: "Scope: 2 programs, 1 dataset"        │
│  [Clear All]        [Cancel]  [Apply & Load ▶]  │
└───────────────────────────────────────────────┘
```

- **REQ-FILTER-03** — Hai panel cạnh nhau (QSplitter): **Programs** (trái) và **Datasets** (phải), mỗi panel là danh sách checkbox cuộn được.
- **REQ-FILTER-04** — Mỗi panel có nút nhanh **All / None**. Programs hiển thị cột phụ "Loại" (Tracker/Event); Datasets hiển thị "Period".
- **REQ-FILTER-05** — Dòng **Summary** cập nhật realtime: "Scope: N programs, M datasets"; nếu **không chọn gì** → cảnh báo "⚠ Chưa chọn gì — sẽ tải TOÀN BỘ metadata (chậm hơn)".
- **REQ-FILTER-06** — **Clear All** bỏ chọn tất cả; **Cancel** đóng không lưu; **Apply && Load Metadata** trả `filter_cfg` rồi đóng.
- **REQ-FILTER-07** — Khi mở lại, dialog **khôi phục** lựa chọn từ `filter_cfg` hiện tại (`_restore_selection`).

### A.3 ❌ Bỏ Tầng 2 (THU HẸP THÊM)

- **REQ-FILTER-08** — **Loại bỏ toàn bộ Tầng 2** "② THU HẺP THÊM" gồm 2 tab: **Data Element Groups** và **Keyword Filters** (Program name / Data Element name).
  - Lý do: trùng vai trò với scope; ít dùng; làm dialog phức tạp.
  - `filter_cfg` sau khi bỏ chỉ còn: `program_ids`, `dataset_ids`, `domain_type` (= `"AGGREGATE"`).
  - Backend `dhis2/metadata.py::fetch_all` **vẫn chấp nhận** thiếu `de_group_ids`/`de_name`/`program_name` (chúng optional) → không cần đổi backend; chỉ gỡ phần UI + các key này khỏi `_on_apply`.

### A.4 Apply → Load metadata

- **REQ-METALOAD-01** — Apply → chạy `fetch_all(client, filter_cfg)` trên **thread nền**; progress indeterminate; nút đổi "Loading…".
- **REQ-METALOAD-02** — Lưu cache metadata theo URL + lưu `filter_cfg` riêng (`save_filter_cfg`); cập nhật label "Metadata freshly loaded."
- **REQ-METALOAD-03** — Quy tắc scope của `fetch_all` (giữ nguyên):
  - chọn **program** (không dataset) → tracker scope: program indicators + program stage DEs + TEAs.
  - chọn **dataset** (không program) → aggregate scope: DEs của dataset + aggregate indicators.
  - **không chọn gì** → tải tất cả (chậm).
- **REQ-METALOAD-04** — Sau khi load xong → đẩy metadata vào Chart Editor và **kích hoạt tải dữ liệu mẫu** theo program/dataset đã chọn (xem DATA_EXPORT_REQUIREMENTS).

---

## PART B — Viết & lưu Description cho DE / PA / Indicator

### B.1 Điểm vào & mục đích

- **REQ-DESC-UI-01** — Nút **"Metadata Editor"** ở sidebar, **bật sau khi connect**; mở **panel Metadata Editor embedded** (QStackedWidget index 3) — **không** popup, nhất quán với config/chart/dashboard. Rời panel → tự lưu (flush) mọi mô tả đang sửa.
- **REQ-DESC-UI-02** — Mục đích: cho người dùng ghi **mô tả cục bộ** cho từng DE/PA/Indicator; mô tả này dùng làm **ngữ cảnh cho AI** (dashboard planner) — **không** gửi lên DHIS2.

### B.2 Danh sách & tìm kiếm

- **REQ-DESC-UI-03** — Dialog gộp các loại từ metadata thành một danh sách phẳng, gắn nhãn loại:
  Indicator · Program Indicator · Data Element · Tracker DE (`program_stage_data_elements`) · Tracked Attribute (`tracked_entity_attributes`).
- **REQ-DESC-UI-04** — Ô **search** lọc theo tên hoặc UID (không phân biệt hoa thường, lọc realtime).
- **REQ-DESC-UI-05** — Item **đã có mô tả** hiển thị dấu **✓** ở đầu; bộ đếm "shown / total · N described".

### B.3 Soạn thảo & lưu

- **REQ-DESC-UI-06** — Chọn item → pane phải hiện tên + "UID · loại" + ô soạn `QPlainTextEdit`.
- **REQ-DESC-UI-07** — Sửa mô tả đang được giữ ở **pending** (chưa lưu); chuyển item khác **không mất** edit (pending ưu tiên hơn bản đã lưu).
- **REQ-DESC-UI-08** — **Save description** lưu ngay item hiện tại (`save_description`); **OK** lưu **tất cả** pending một lần (`save_descriptions_bulk`) rồi đóng; **Cancel** bỏ pending.
- **REQ-DESC-UI-09** — `get_descriptions()` trả dict mô tả mới sau khi đóng để app đẩy lại cho dashboard builder.

### B.4 Lưu trữ & ngữ nghĩa (khớp `config/descriptions.py`)

- **REQ-DESC-01** — Lưu/đọc round-trip: `{uid: text}` tại `cache/<url_slug>/descriptions.json`.
- **REQ-DESC-04** — Mô tả **rỗng/trắng** → **xóa** key đó (không để entry mồ côi).
- **REQ-DESC-07** — **Cô lập theo instance**: URL DHIS2 khác nhau → file mô tả khác nhau, không dùng chung.
- **REQ-DESC-UI-10** — Thao tác mô tả **chỉ lưu cục bộ**; không bao giờ ghi ngược lên DHIS2.

---

## C. Acceptance / Test

- **Filter**: kiểm thử thủ công — mở dialog sau connect, chọn 1 program → Apply → metadata load lại, summary đúng; mở lại dialog thấy lựa chọn được khôi phục.
- **Bỏ Tầng 2**: sau khi gỡ, dialog không còn tab DE Groups/Keyword; `filter_cfg` chỉ còn `program_ids/dataset_ids/domain_type`; `fetch_all` vẫn chạy.
- **Descriptions**: `python -m pytest tests/test_descriptions.py -v` → **10 pass** (REQ-DESC-01/02/04/07…).
- **UI**: [scripts/manual/test_ui.py](../scripts/manual/test_ui.py).

---

## D. TO-DO (việc cần làm để khớp requirement)

1. **REQ-FILTER-08** — Gỡ Tầng 2 khỏi `FilterConfigDialog`:
   - Xóa `QTabWidget` + `_build_refine_groups` + `_build_keywords`, các `_de_cbs`, `_de_name_entry`, `_prog_name_entry`.
   - Bỏ `de_group_ids`/`de_name`/`program_name` khỏi `_on_apply` và `_restore_selection`.
   - Cập nhật `_update_summary` (bỏ phần "Thu hẹp").
2. Giữ nguyên backend `fetch_all` (đã tolerant với thiếu key) — chỉ kiểm tra lại không nơi nào còn đọc `de_group_ids`/`de_name` từ UI.
