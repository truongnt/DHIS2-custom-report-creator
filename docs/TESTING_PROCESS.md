# Automated Testing Process — Standard

Quy trình test tự động chuẩn cho app. Mục tiêu: **"test pass" phải đồng nghĩa với "app chạy đúng"** —
không còn tình trạng unit test xanh nhưng chạy thật lại sai.

> Nguyên tắc: một test **chỉ được PASS** khi (1) kiểm tra **hành vi quan sát được** (không phải chuỗi),
> (2) **khớp với một REQ-ID** cụ thể, và (3) có **log + bằng chứng** (screenshot / console log / dữ liệu).

---

## 1. Vì sao test hiện tại "pass nhưng app sai" (chẩn đoán)

| Vấn đề | Hiện trạng |
|---|---|
| **Test chuỗi, không test hành vi** | `tests/test_preview.py` chủ yếu `html.find("...")` / assert substring → chỉ chứng minh *template chứa đoạn text*, **không** chứng minh chart vẽ ra, data nạp đúng, hay option có hiệu lực. |
| **Không chạy code runtime** | Charts render bằng Chart.js/Leaflet **trong browser**; không layer nào load HTML vào trình duyệt để bắt **lỗi JS runtime**. Lỗi JS → app trắng, nhưng unit test vẫn xanh. |
| **Bằng chứng render bị tách rời** | Chỉ `scripts/checklists/` chụp ảnh thật (Node+CDP), nhưng **thủ công**, per-chart, hardcode `C:/Temp`, **không** nằm trong `pytest`, không chạy sau mỗi lần sửa. |
| **Không truy vết REQ** | Không map REQ → test → bằng chứng, nên "pass" không nói lên đã thỏa yêu cầu nào. |
| **E2E mô phỏng quá nhiều** | `scripts/manual/test_ui.py` mock gần hết → không bắt lỗi tích hợp thật; lại nằm ngoài `tests/`. |

---

## 2. Kim tự tháp test (4 tầng) — mỗi tầng bắt một lớp lỗi

```
        ▲  ít, chậm, gần thực tế nhất
   E2E render (browser thật, bắt lỗi JS + render)   ← TẦNG ĐANG THIẾU
   Integration (pytest-qt: widget thật, luồng connect/filter/desc)
   Unit hành vi (adapter, aggregate, config — assert GIÁ TRỊ)
   Unit chuỗi (HTML fragment) — giữ, nhưng KHÔNG đủ để PASS tính năng
        ▼  nhiều, nhanh
```

- **REQ-TEST-01 (Unit logic)** — Hàm thuần (vd `event_adapter.events_to_rows`, `aggregate_for_dim`)
  test bằng **giá trị đầu ra** (rows/labels/values), không phải substring. *(đã có: `test_event_adapter.py`.)*
- **REQ-TEST-02 (Integration Qt)** — Dùng **`pytest-qt` (`qtbot`)** drive widget thật:
  connect (mock `DHIS2Client`) → nav mở khóa; FilterDialog apply → `filter_cfg` đúng; MetadataEditor lưu description.
  `qtbot` tự bắt exception trong slot/signal → fail test (bắt lỗi wiring mà string-check bỏ sót).
- **REQ-TEST-03 (E2E render)** — Render **HTML preview thật** trong **browser headless**, assert:
  (a) **không có lỗi console JS**, (b) canvas/`<svg>`/Leaflet container tồn tại & có kích thước > 0,
  (c) số series/điểm dữ liệu đúng kỳ vọng, (d) option có hiệu lực (vd `DARK_MAP1=true` → nền tối).
  **Bắt buộc lưu screenshot + console log** làm bằng chứng.
- **REQ-TEST-04 (Visual regression, tùy chọn)** — So screenshot với **baseline**; lệch quá ngưỡng → fail.

---

## 3. Định nghĩa PASS (cổng chất lượng)

Một tính năng/sửa lỗi **chỉ DONE** khi:

1. **Mọi REQ liên quan có ≥1 test** ở tầng phù hợp (logic→unit, UI→integration, render→E2E).
2. Test assert **hành vi/giá trị quan sát được**, không chỉ chuỗi.
3. **Không lỗi console JS** ở E2E (console error = FAIL, kể cả khi ảnh trông "ổn").
4. **Bằng chứng được lưu**: screenshot + log dưới `test-evidence/<timestamp>/` (đường dẫn in ra report).
5. Báo cáo **REQ → kết quả → bằng chứng** sinh tự động (xem §5).

> Quy tắc vàng: **nếu không có bằng chứng render/giá trị, KHÔNG được tuyên bố PASS** — chỉ được nói
> "unit logic pass, chưa verify render".

---

## 4. Hạ tầng cần thêm

| Việc | Chi tiết |
|---|---|
| **Thêm dependency test** | `pytest`, `pytest-qt`, và **một** trong: `playwright` (khuyến nghị) hoặc dùng `selenium` (đã cài). Ghi vào `requirements-dev.txt`. |
| **`pytest.ini`** | đặt `testpaths=tests`, marker `unit/integration/e2e`, `qt_api=pyside6`. |
| **`tests/conftest.py`** | fixtures dùng chung: `qtbot` (qua pytest-qt), `evidence_dir` (tạo `test-evidence/<ts>/`), `render_preview(html)` (mở browser headless, trả console log + screenshot). |
| **Vendor JS libs offline** | E2E phải chạy offline → bản local của `chart.umd.min.js`, datalabels, Leaflet (giống checklist đang lấy ở `C:/Temp/chartjs`) đặt vào `tests/assets/` và inject khi render. |
| **Gộp engine screenshot** | Chuyển logic Node+CDP trong `scripts/checklists/test_checklist_base.py` thành helper tái dùng trong `tests/e2e/` (bỏ hardcode `C:/Temp` → dùng `evidence_dir`). |
| **Traceability** | Mỗi test gắn REQ-ID trong tên/docstring (vd `test_areamap_dark_basemap` ↔ REQ map `base_map: CartoDB Dark`). |

---

## 5. Quy trình "sau khi code xong" (tự động)

```
   sửa code
      │
      ▼
   make test   (hoặc: python scripts/run_tests.py)
      ├─ 1. pytest -m unit          → logic
      ├─ 2. pytest -m integration   → Qt widgets (pytest-qt, headless QT_QPA_PLATFORM=offscreen)
      ├─ 3. pytest -m e2e           → render browser, chụp ảnh + log console
      └─ 4. sinh report: test-evidence/<ts>/report.md
                 REQ-ID | layer | PASS/FAIL | evidence path
      │
      ▼
   ĐỌC report: PASS chỉ khi tất cả khớp REQ + không lỗi console + có bằng chứng
```

- **REQ-TEST-05** — Có **một lệnh duy nhất** chạy cả 3 tầng + sinh report (CI dùng đúng lệnh đó).
- **REQ-TEST-06** — Report liệt kê **REQ-ID ↔ kết quả ↔ đường dẫn bằng chứng**; REQ nào không có test → đánh dấu **GAP** (không tính pass).
- **REQ-TEST-07** — E2E phải chạy **headless & offline** (CI không có màn hình, không internet): Qt dùng `QT_QPA_PLATFORM=offscreen`; JS libs vendor local.
- **REQ-TEST-08** — Bất kỳ **lỗi/exception/console-error** nào trong khi render → **FAIL**, kèm log đầy đủ.

---

## 6. Áp dụng cho các tính năng đã có (ví dụ map matrix)

Map options trong `CLAUDE.md` đã có **acceptance table** (log phải show gì, visual phải thấy gì) —
đó chính là REQ cho E2E. Chuyển mỗi dòng bảng thành **một test E2E** assert log + ảnh:
`base_map: CartoDB Dark` → test mở HTML, kiểm `DARK_MAP1=true` trong DOM, không lỗi console, screenshot nền tối.

---

## 7. Lộ trình triển khai (đề xuất)

1. **Nền tảng** (nhỏ, ít rủi ro): `requirements-dev.txt` + `pytest.ini` + `tests/conftest.py` (evidence_dir + qtbot).
2. **Integration**: cài `pytest-qt`, viết test connect/filter/description với client mock → chuyển `scripts/manual/test_ui.py` vào `tests/integration/`.
3. **E2E render**: vendor JS libs vào `tests/assets/`, viết `tests/e2e/conftest` helper render headless + 1 test mẫu (bar chart: assert canvas + no console error + screenshot).
4. **Mở rộng**: phủ map matrix + các plugin còn lại; thêm report generator (§5).
5. **CI**: chạy `python scripts/run_tests.py` mọi commit.

---

## 8. Quyết định cần chốt trước khi build

1. **Công cụ E2E browser**: **Playwright** (khuyến nghị — tự quản trình duyệt, API gọn, bắt console dễ)
   hay **Selenium** (đã cài sẵn nhưng cần chromedriver/Chrome)?
2. **Visual regression** (so ảnh baseline) — làm luôn (REQ-TEST-04) hay để sau?
3. **CI**: chạy ở đâu (GitHub Actions / máy local pre-commit)?

---

## 9. Regression rule — MỖI LỖI → MỘT KỊCH BẢN TEST (bắt buộc)

> **Quy tắc:** Mỗi khi phát hiện một lỗi thực tế (người dùng báo, hoặc thấy khi chạy app),
> **đưa ĐÚNG các tham số người dùng đã chọn vào một kịch bản test** tái hiện lỗi đó.
> Lỗi chỉ được coi là "đã sửa" khi: test tái hiện **fail trước khi sửa**, **pass sau khi sửa**,
> và **ở lại trong suite vĩnh viễn** → nếu suite còn pass thì lỗi đó **không thể tái diễn**.

Cách làm:
1. **Lấy tham số từ log** `logs/debug_*.log` — dòng `UI ... PREVIEW plugin=... metrics=[...] ou_level=... pe=...`
   cho biết chính xác người dùng chọn gì. Dòng `JS:error [ChartN] ...` cho thông điệp lỗi.
2. **Dựng config y hệt** trong test (cùng plugin_id, metric type, plugin_options, ou_level, pe).
3. **Assert hành vi quan sát được** (không console error / render đúng), kèm bằng chứng.
4. Nếu lỗi nằm ở nhánh dữ liệu khó tái hiện bằng mock (vd response thiếu cột), **test trực tiếp
   hàm/đơn vị bị lỗi** với input gây lỗi (vd `formatPeriodLabel(undefined)` phải trả `''`, không throw).

**Ví dụ đã áp dụng** — lỗi `"can't access property match, pe is undefined"` (bar + metric `tracker_option`,
`pe` rỗng): `formatPeriodLabel(undefined)` ném lỗi → đã (a) làm hàm null-safe, (b) thêm regression test
`tests/e2e/test_regressions.py` gọi `formatPeriodLabel(undefined)` + render đúng config người dùng chọn.
