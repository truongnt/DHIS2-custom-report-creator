# UI Guidelines & Requirements

Chuẩn UI cho app (PySide6/Qt desktop) — để **tránh tràn layout, màu không tương phản, style không nhất quán**.
Checklist chức năng per-màn nay nằm trong các req theo tính năng ([LOGIN_REQUIREMENTS.md](LOGIN_REQUIREMENTS.md),
[METADATA_FILTER_REQUIREMENTS.md](METADATA_FILTER_REQUIREMENTS.md), [charts/](charts/)); file này tập trung **chất lượng UI**.

## Nguồn tham chiếu (dùng làm chuẩn)

- **KDE Human Interface Guidelines** — <https://develop.kde.org/hig/> — bộ HIG cho app **Qt** (KDE xây trên Qt),
  phù hợp nhất với app này. Nguyên tắc chính lấy từ đây.
- **WCAG 2.1 (AA)** — chuẩn tương phản màu: text thường **≥ 4.5:1**, text lớn (≥18px hoặc ≥14px bold) **≥ 3:1**.
- Design tokens hiện có: [ui/qt_utils.py](../ui/qt_utils.py) (`APP_QSS`, `DHIS2_BLUE`, `SIDEBAR_BG`, …).

---

## 1. Design tokens (nguồn chân lý: `qt_utils.py`)

| Token | Hex | Dùng cho |
|---|---|---|
| `DHIS2_BLUE` | `#1a6fa8` | primary action, focus border |
| `SIDEBAR_BG` | `#1e2d3d` | nền tối (sidebar, config panel) |
| `SIDEBAR_FG` | `#ffffff` | text trên nền tối |
| `PANEL_BG` | `#f7f9fc` | nền sáng (vùng nội dung) |
| `BORDER_CLR` | `#d0dde8` | viền |

- **REQ-UI-TOKEN-01** — Mọi widget **dùng token + biến QSS class** (`primary`/`success`/`danger`/`outline-primary`/`ghost` đã định nghĩa trong `APP_QSS`), **không** hardcode màu inline rải rác. Cần màu mới → thêm token, không đặt số hex tùy tiện.

---

## 2. Tương phản màu (WCAG AA) — REQ-UI-COLOR

- **REQ-UI-COLOR-01** — Mọi text phải đạt **≥ 4.5:1** (text lớn ≥ 3:1) so với nền.
- **REQ-UI-COLOR-02** — **Không dùng màu đơn lẻ** để truyền nghĩa (KDE HIG): trạng thái phải kèm **icon/chữ/hình** (vd `● Connected` có cả chấm + chữ).
- **REQ-UI-COLOR-03** — Màu ngữ nghĩa nhất quán: xanh lá = thành công, đỏ = lỗi, cam = cảnh báo, xanh DHIS2 = hành động chính.

### Kết quả đo bảng màu hiện tại (cần sửa các dòng FAIL)

| Cặp (fg trên bg) | Tỉ lệ | AA thường (4.5) |
|---|---|---|
| `#ffffff` / `#1e2d3d` (text trắng/sidebar) | 14.0 | ✅ |
| `#8aa3b8` / `#1e2d3d` (nav mờ) | 5.35 | ✅ |
| `#f39c12` / `#1e2d3d` (cảnh báo) | 6.39 | ✅ |
| `#2ecc71` / `#1e2d3d` (connected) | 6.67 | ✅ |
| `#ffffff` / `#1a6fa8` (text nút primary) | 5.41 | ✅ |
| `#1e2d3d` / `#f7f9fc` (text nội dung) | 13.3 | ✅ |
| **`#6b8299` / `#1e2d3d`** (field hint) | 3.52 | ❌ |
| **`#6b8299` / `#eef2f7`** (status bar) | 3.54 | ❌ |
| **`#e74c3c` / `#eef2f7`** (lỗi trên status bar) | 3.40 | ❌ |
| **`#4a6278` / `#1e2d3d`** (footer, cache_lbl) | 2.21 | ❌ |
| **`#445566` / `#1e2d3d`** (nav disabled) | 1.83 | ❌ |

- **REQ-UI-COLOR-05** — **Danh sách (QListView/QListWidget) phải set màu chữ item rõ ràng**
  cho cả 3 trạng thái (thường / hover / selected). Không để item dựa vào màu mặc định của palette
  → tránh "chữ trùng nền không đọc được" (đã gặp ở Metadata Editor: item không set `color` → chữ sáng trên nền sáng).

- **REQ-UI-COLOR-04 (TO-DO)** — Sửa 5 cặp ❌: làm sáng màu chữ. Gợi ý:
  `#4a6278`→`#7d96ad`; `#445566`→`#6a7f95` (disabled vẫn nên ≥ 3:1);
  `#6b8299`→`#9fb3c6` trên nền tối và `#52708c` trên nền sáng; lỗi đỏ trên nền sáng `#e74c3c`→`#c0392b`.

---

## 3. Layout & chống tràn — REQ-UI-LAYOUT

- **REQ-UI-LAYOUT-01** — Vùng nội dung dài phải nằm trong **`QScrollArea`** (`setWidgetResizable(True)`) — không để widget bị cắt khi cửa sổ nhỏ. (Config panel đã đúng; áp dụng nhất quán.)
- **REQ-UI-LAYOUT-02** — **Hạn chế `setFixedHeight/Width`** cho phần chứa text động; ưu tiên min/max + layout co giãn. Text nhiều dòng phải `setWordWrap(True)` (label) để không tràn ngang.
- **REQ-UI-LAYOUT-03** — Cửa sổ có **`minimumSize` hợp lý** (đang `1024×640`); mọi dialog có `minimumSize` để không vỡ khi thu nhỏ.
- **REQ-UI-LAYOUT-04** — Dùng **spacing/margin theo bội số 4px** (KDE HIG: lưới đều) — vd 4/8/16; tránh số lẻ tùy tiện.
- **REQ-UI-LAYOUT-05** — Danh sách dài (DE list, OU list) **cuộn riêng** với chiều cao giới hạn (đã có max 140px cho DE list); không để đẩy nút bấm ra ngoài màn.
- **REQ-UI-LAYOUT-06** — Text có thể dài (tên DE/OU, lỗi) → **elide hoặc wrap + tooltip**, không cho tràn khỏi container.
- **REQ-UI-LAYOUT-07** — **Toàn bộ trang/dialog phải nằm gọn trong màn hình**; **nút hành động chính
  (Apply, Save, Connect…) không bao giờ bị cắt phía dưới**. Dialog phải **kẹp kích thước theo
  `availableGeometry()`** của màn hình và đặt `minimumHeight` đủ nhỏ (≤ ~700px) để vừa laptop;
  nội dung dài thì cuộn bên trong, **thanh nút giữ cố định luôn thấy được**.
  (Đã gặp: FilterConfigDialog cao 700px tràn khỏi màn thấp → nút "Apply & Load" bị che.)

---

## 4. Nhất quán component — REQ-UI-COMP

- **REQ-UI-COMP-01** — Nút theo cấp bậc: **1 primary** mỗi màn (hành động chính), còn lại outline/ghost. Không nhiều nút primary cạnh nhau (KDE HIG).
- **REQ-UI-COMP-02** — Trạng thái focus phải thấy rõ (đã có `border-color:#1a6fa8` khi focus ô nhập) — giữ nhất quán mọi input.
- **REQ-UI-COMP-03** — Icon/emoji trong nút giữ nhất quán bộ; nhãn nút là **động từ** ("Connect", "Apply & Load", "Save description").
- **REQ-UI-COMP-04** — Disabled state phải phân biệt được nhưng **vẫn đọc được** (≥ 3:1) — liên quan REQ-UI-COLOR-04.
- **REQ-UI-COMP-05** — **Mọi nút phải có `:hover` rõ ràng**. Nền đặc → hover **đậm hơn**; nền outline/trong suốt → hover **đổ nền** (không chỉ đổi viền mờ). Hai nút cạnh nhau **không dùng cùng một màu hover** — phải phân biệt được khi rê chuột (vd Save = tím đặc, Save As = outline tím, hover nền tím nhạt).
- **REQ-UI-COMP-06** — Nút **không dùng được trong flow hiện tại** phải **`setEnabled(False)`** và hiển thị màu disabled, thay vì để bấm rồi báo lỗi. Vd: Chart Editor — Save / Save As / Add to Dashboard / Preview disabled khi chưa chọn chart type + metric; Open disabled khi chưa có chart đã lưu. Cập nhật trạng thái mỗi khi state đổi (`_update_action_buttons`).
- **REQ-UI-COMP-07** — **Luồng entity (chart & dashboard)**: phải có đủ **New / Open (Load) / Save / Save As**. *Save* cập nhật entity đang mở (theo id/tên — không tạo trùng); *Save As* luôn tạo bản mới; *New* xóa nội dung + tách khỏi entity đang mở; *Open* nạp entity cũ để sửa lại.
- **REQ-UI-COMP-08** — **Thứ tự nút đồng nhất giữa các màn**: các nút quản lý entity luôn theo thứ tự **New · Open · Save · Save As** (rồi mới tới các nút ngữ cảnh như Add/Filters/Preview/Export/Deploy). Áp dụng cho Chart Editor và cả 2 chế độ của Dashboard (Manual + AI).
- **REQ-UI-COMP-09** — **Footer của dialog**: mọi `QDialogButtonBox` phải dùng `qt_utils.style_dialog_buttons(box)` → nút **căn phải**, có **padding** (không dính sát mép/góc), nút **Accept/OK là primary (xanh)**, mọi nút có **`:hover` / `:pressed` / `:disabled`** rõ và min-size hợp lý. Không tự set stylesheet rời cho từng button box.
- **REQ-UI-COMP-10** — **Combobox trong widget tùy biến**: khi set stylesheet riêng cho một `QComboBox` (vd dropdown agg SUM/COUNT trong chip metric), phải **kèm luôn rule `QComboBox QAbstractItemView`** (nền trắng, chữ tối) — stylesheet chỉ có `font-size` sẽ reset popup về mặc định OS (nền đen ở dark mode). Popup là cửa sổ top-level.
- **REQ-UI-COMP-11** — **Các control cùng một hàng phải cùng chiều cao**: trong chip/row có nhiều control (label, dropdown, nút ×), đặt **chiều cao cố định đồng nhất** cho cả row và các control con (vd chip metric `_RH=28`, dropdown/nút ~22).
- **REQ-UI-COMP-12** — **Reorder bằng kéo-thả**: danh sách item người dùng sắp xếp được (vd metrics) phải hỗ trợ **drag-and-drop để đổi thứ tự**, có **grip handle** rõ; chỉ hiện grip khi có >1 item.
- **REQ-UI-COMP-13** — **Alias cho metric**: mỗi metric có ô nhập **alias (tên hiển thị)**; khi có alias, mọi nơi hiển thị (label chart, header cột bảng, legend) **dùng alias thay tên gốc**. Lưu cùng config (`metrics[].alias`, tên gốc giữ ở `orig_name`), khôi phục khi Open. Picker dimension không có ô alias.
- **REQ-UI-OPT-01** — **Giá trị tùy chỉnh — chỉ nơi thực sự cần**: chỉ bật custom cho option **màu đơn** (point/value/border color → color picker 🎨) và **kích thước/số** (size/scale/width/rotation/row_limit). Các option enum (mode, base map, x-axis, ou level…) **không** có custom. Plugin phải hiểu giá trị custom (số → px/radius; `#hex` → màu). Có color picker riêng cho màu chart.
- **REQ-UI-OPT-02** — **Ô nhập inline, không popup**: custom kiểu number/text hiển thị **ô nhập ngay trên hàng** (gõ trực tiếp, commit khi Enter/blur), KHÔNG mở hộp thoại nhập. Chọn preset sẽ xoá giá trị custom và ngược lại.
- **REQ-UI-LOAD-01** — **Mở lại entity phải khôi phục ĐẦY ĐỦ tham số**: khi Open/Load một chart/dashboard đã lưu, phải nạp lại tất cả (chart type, source + stage, metrics + agg, dimension split-by, filters, plugin options, time grain, sort, màu, col width, custom AI options) — không chỉ tiêu đề.
- **REQ-UI-LOAD-02** — **Dialog Open dạng bảng**: liệt kê chart/dashboard đã lưu trong **`QTableWidget`** với cột **Name · Description · Type · Date** và **nút xóa (✕) mỗi dòng**; double-click hoặc nút **Open** để mở; dùng chung `EntityTableDialog`. Header đọc được, dòng chọn nền xanh, có hover.
- **REQ-UI-LOAD-03** — **Nhập Description khi lưu**: Save/Save As (chart & dashboard) phải cho nhập **mô tả** qua **cùng một `SaveEntityDialog` (Name + Description)** — KHÔNG dùng ô name/description inline. Save trên entity đang mở thì cập nhật im lặng (giữ name+desc); Save khi chưa có entity hoặc Save As thì mở dialog. Tên entity đang sửa hiển thị ở label tiêu đề ("• <name>"/"• new …"). Description lưu cùng entity và hiển thị ở cột Description của dialog Open (trống → tự suy ra: chart = metric·program, dashboard = số chart).

---

## 5. Quy ước UI cụ thể (kế thừa từ bản Qt migration)

Các chuẩn đã áp dụng và **cần giữ nhất quán** khi thêm màn/widget mới:

- **REQ-UI-CONV-01** — App mở **maximized**; cửa sổ `minimumSize` 1024×640.
- **REQ-UI-CONV-02** — Sidebar nav: nút **active** tô nền **DHIS2 blue**, nút **inactive** nền trong suốt; nút khóa khi chưa connect.
- **REQ-UI-CONV-03** — Danh sách DE/OU: **cuộn riêng**, chiều cao giới hạn (~140px), search lọc **live**, nút `✕` xóa search; không recreate toàn bộ list khi gõ (mượt).
- **REQ-UI-CONV-04** — Chart type: lưới **tiles** (icon + label), chọn xong **thu gọn** thành dòng tóm tắt + nút "Change ▼" để mở lại.
- **REQ-UI-CONV-05** — Bảng màu preset: nút **20×20**, ô đang chọn có **viền trắng** làm nổi bật.
- **REQ-UI-CONV-06** — Preview **debounce 400ms** (`QTimer` singleShot) sau khi đổi config; thao tác connect/load chạy thread nền, **không khóa main thread**.
- **REQ-UI-CONV-07** — Status bar: thông báo lỗi **đỏ**; progress **indeterminate** khi async, dừng khi xong.
- **REQ-UI-CONV-08** — Dashboard: bố cục 2 cột (Library ~240px | Canvas); Export/Deploy **disabled khi canvas rỗng**; xóa/clear có dialog xác nhận.
- **REQ-UI-CONV-09** — Dùng **`&&`** trong text nút/label để hiển thị ký tự `&` (vì `&` đơn là phím tắt Qt).
- **REQ-UI-CONV-10** — Col width chart: SegmentedButton **Full / Half / Third**.

## 6. Acceptance

- **Tương phản**: chạy script đo (đoạn Python trong PR/commit) — mọi cặp text/nền đạt AA; 5 cặp ❌ ở §2 được sửa.
- **Tràn layout**: thu nhỏ cửa sổ về `minimumSize` → không widget nào bị cắt, không cần scroll ngang ngoài ý muốn.
- **Nhất quán**: không còn màu hex hardcode ngoài token (rà `grep -rn "#" ui/` các giá trị lạ).
- Hồi quy chức năng: [scripts/manual/test_ui.py](../scripts/manual/test_ui.py).

---

## 7. TO-DO

1. **REQ-UI-COLOR-04** — Sửa 5 cặp màu fail AA trong `qt_utils.py` + các style inline ở `app_window.py`.
2. Cân nhắc gom các style inline lặp lại (nút Connect/Change…) vào QSS class trong `APP_QSS` (REQ-UI-TOKEN-01).
3. Rà các `setFixedHeight` chứa text động → đổi sang min/max (REQ-UI-LAYOUT-02).

> Tài liệu này là **chuẩn sống**: khi thêm màn/ở widget mới, đối chiếu §2–§4 trước khi merge.
