# Data & Metadata Export — Requirements

Yêu cầu thiết kế lại cách app tải **dữ liệu sự kiện (events) mẫu** và **metadata** sau khi login,
chuyển từ Analytics query (hiện tại) sang **Export API** của DHIS2, **giữ nguyên format gốc** của DHIS2.

> Mục tiêu: tải **dữ liệu MẪU để chạy test local** — KHÔNG phải toàn bộ dữ liệu.
> Trạng thái: **requirement only — chưa code.** Cần duyệt trước khi triển khai.
> Tham chiếu: DHIS2 Tracker API (events export), Metadata API (dependency export).

---

## 0. Bối cảnh — vì sao thay đổi

### Cách hiện tại (kém hiệu quả)

`dhis2/fixture_fetcher.py` dùng **Analytics events query**
(`GET /api/analytics/events/query/{program}?dimension={stage}.{de}…`):

1. **Batch theo DE** (`_MAX_DES_PER_REQ = 20`) → nhiều request/stage rồi tự ghép theo `psi` — phức tạp, dễ sai.
2. Dữ liệu đã qua **analytics engine** (có độ trễ, đã xử lý) — không phải event gốc.
3. **Tự chế format** (`raw_events_v1`: headers + rows) → lệch khỏi format gốc DHIS2, khó đối chiếu.

`dhis2/metadata.py::fetch_all` gộp mọi thứ vào **một dict / một file cache** → khó kiểm tra, khó tái dùng.

### Cách mới (đề xuất)

- **Events**: dùng **Tracker Export API** `GET /api/tracker/events`, lấy **~100–200 event mẫu/program**,
  mỗi event **đủ toàn bộ trường** (`fields=*`, gồm tất cả `dataValues`), **lưu nguyên JSON gốc**.
- **Metadata**: dùng **dependency export** (`/api/programs/{id}/metadata.json`, `/api/dataSets/{id}/metadata.json`)
  + collection endpoint cho org units; **tách mỗi loại thành một file JSON độc lập**, **giữ object format gốc** của DHIS2.
- **Chỉ** tải program/dataSet **được chọn**.

---

## PART A — Event Sample Export

### A.1 Endpoint & tham số

`GET /api/tracker/events`

| Param | Giá trị đề xuất | Ghi chú |
|---|---|---|
| `program` | UID program đã chọn | bắt buộc |
| `orgUnit` | root OU của user | lấy từ `GET /api/me?fields=organisationUnits[id]` |
| `orgUnitMode` | `DESCENDANTS` | toàn bộ cây con (modes: SELECTED/CHILDREN/DESCENDANTS/ACCESSIBLE/CAPTURE/ALL) |
| `fields` | `*` | **lấy đủ mọi trường** của event (bao gồm `dataValues`) — giữ object gốc |
| `pageSize` | `200` (cấu hình, mặc định 100–200) | **chỉ lấy mẫu** |
| `page` | `1` | **chỉ trang đầu** — không phân trang hết |
| `order` | `occurredAt:desc` (tùy chọn) | lấy event mới nhất làm mẫu cho trực quan |

> **Bỏ** `LAST_12_MONTHS`, `_MAX_ROWS=5000`, batch theo DE và ghép `psi`.
> **Lưu ý version**: khóa mảng events đổi giữa các phiên bản (`instances` ↔ `events`) → loader đọc linh hoạt cả hai.

### A.2 Yêu cầu

- **REQ-EVT-01** — Với **mỗi program được chọn**, tải **mẫu ~100–200 event** qua `/api/tracker/events`
  (`page=1`, `pageSize` cấu hình, mặc định 200). **Không** tải toàn bộ.
- **REQ-EVT-02** — Dùng `fields=*` để **mỗi event có đầy đủ mọi trường + toàn bộ `dataValues`** → test local chuẩn xác.
- **REQ-EVT-03** — **Lưu nguyên JSON gốc** trả về từ DHIS2 (không đổi sang `headers/rows` hay format tự chế).
- **REQ-EVT-04** — Mỗi program **một file độc lập** trong thư mục `data/` (xem §C). Tên: `events_{program}.json`.
- **REQ-EVT-05** — Chạy **nền (background thread)**, im lặng; lỗi một program **không** làm hỏng program khác.
- **REQ-EVT-06** — Hỗ trợ cả tracker program (WITH_REGISTRATION) và event program (WITHOUT_REGISTRATION).
- **REQ-EVT-07** — Bỏ qua nếu file đã tồn tại & còn mới (< 7 ngày); hỗ trợ refresh thủ công (ghi đè).
- **REQ-EVT-08** — Loader đọc linh hoạt khóa mảng (`events` hoặc `instances`).

### A.3 Acceptance (Part A)

- File `data/.../events_{prog}.json` chứa **100–200 event**, mỗi event giữ **nguyên object DHIS2** kèm `dataValues` đầy đủ.
- Có thể chạy test/preview hoàn toàn **offline** từ file này, không gọi mạng.
- Không còn lời gọi `analytics/events/query`; số request/program = **1**.

---

## PART B — Metadata Export (mỗi loại một file, format gốc)

### B.1 Chiến lược

1. **Program đã chọn** → `GET /api/programs/{id}/metadata.json?skipSharing=true`
   → closure đầy đủ: programs, programStages, dataElements, optionSets/options, trackedEntityAttributes, categoryCombos…
2. **DataSet đã chọn** → `GET /api/dataSets/{id}/metadata.json?skipSharing=true`.
3. **Org units (level 1–5, TẤT CẢ)** → tải riêng:
   `GET /api/organisationUnits.json?paging=false&fields=id,name,level,path,parent[id],geometry`
   *(không lọc level → lấy hết 1–5; có `geometry` cho bản đồ; giữ object gốc).*
4. **Gộp** các bundle, **khử trùng theo `id`**, rồi **tách theo khóa-loại gốc của DHIS2**
   (`programs`, `programStages`, `dataElements`, `optionSets`, …) — mỗi khóa thành một file.

> Dependency export endpoint khác (tham khảo): `/api/optionSets/{id}/metadata.json`, `/api/categoryCombos/{id}/metadata.json`.

### B.2 Yêu cầu

- **REQ-META-01** — Mỗi **program được chọn** → gọi `/api/programs/{id}/metadata.json?skipSharing=true`.
- **REQ-META-02** — Mỗi **dataSet được chọn** → gọi `/api/dataSets/{id}/metadata.json?skipSharing=true`.
- **REQ-META-03** — **CHỈ** tải program/dataSet **được chọn** — không dump toàn instance.
- **REQ-META-04** — **Org units: tải HẾT level 1–5**, kèm `geometry` (thay cho `geoFeatures` rời rạc hiện tại).
- **REQ-META-05** — **Tách mỗi loại metadata thành một file JSON riêng**, **giữ object format gốc** của DHIS2
  (không trim/đổi tên field). Khử trùng theo `id` khi gộp nhiều bundle.
- **REQ-META-06** — `optionSets` giữ `options` **inline** đúng như DHIS2 trả về.
- **REQ-META-07** — Mỗi file **độc lập & tự kiểm tra được** (mở ra là JSON DHIS2 hợp lệ của loại đó).
- **REQ-META-08** — Tầng loader đọc các file này dựng lại metadata in-memory cho UI (giữ tương thích consumer, hoặc cập nhật consumer).

### B.3 Acceptance (Part B)

- `data/.../metadata/` có **một file mỗi loại**, mở ra đọc được độc lập, **đúng format gốc** DHIS2.
- `programs.json`/`dataSets.json` chỉ chứa mục **đã chọn**; `organisationUnits.json` có **đủ level 1–5 + geometry**.
- UI (chart editor, dimension picker, map) hoạt động không kém metadata cũ — verify bằng `tests/`.

---

## C. Bố cục lưu trữ (format gốc, dưới `data/`)

```
data/<instance_slug>/
  events/
    events_{program}.json        # nguyên JSON gốc /api/tracker/events (100–200 event, fields=*)
  metadata/
    organisationUnits.json       # tất cả OU level 1–5, có geometry  (object gốc)
    optionSets.json              # options inline  (object gốc)
    programs.json                # CHỈ program được chọn  (closure, object gốc)
    programStages.json
    dataElements.json
    dataSets.json                # CHỈ dataSet được chọn
    trackedEntityAttributes.json
    categoryCombos.json
    ... (mỗi khóa-loại DHIS2 trả về → một file)
```

- `<instance_slug>` theo `url_slug` (đồng nhất với `config/descriptions.py`) → **cô lập theo instance**.
- `data/` cần thêm vào `.gitignore` (dữ liệu thật/test, không commit).
- Mỗi file là **JSON DHIS2 thuần** — không bọc header tự chế, không transform.

---

## D. Tác động & di trú

- **Thay thế**: `dhis2/fixture_fetcher.py` (events) và một phần `dhis2/metadata.py::fetch_all`, `dhis2/cache.py` (1 file → nhiều file).
- **Consumer cần rà & cập nhật** (vì đổi từ `raw_events_v1` headers/rows → event JSON gốc):
  - `charts/fixed_templates.py` — `load_raw_events`, nhúng `window.__DEMO_FX__`
  - `charts/plugins/bar.py` — `aggregate_for_dim` (đọc `dataValues` thay vì `rows`)
  - `ui/app_window.py` — `_fetch_fixtures_background`, `_connect_worker`
- **Adapter**: cần hàm đọc event JSON gốc (`event.dataValues[].dataElement/value`, `occurredAt`) và gom theo period
  cho chart preview — thay logic `headers/rows` hiện tại.
- **Bảo mật / tài liệu**: cần đính chính README/CLAUDE.md — app **có** tải event thật (dạng mẫu) về `data/`.

---

## E. Đã chốt (theo trao đổi)

| Câu hỏi | Quyết định |
|---|---|
| Khối lượng events | **Mẫu ~100–200 event/program**, `page=1` |
| Độ đầy đủ mỗi event | **Đủ mọi trường** (`fields=*`, gồm tất cả `dataValues`) |
| Format lưu | **Nguyên JSON gốc DHIS2** (không transform) |
| Vị trí lưu | Thư mục **`data/<instance_slug>/`** (events/ + metadata/) |
| OU geometry | **Tải hết level 1–5** |

| Phạm vi OU cho events | **Root OU của user** (`/api/me`) + `orgUnitMode=DESCENDANTS` |
| Loader | **Adapter đọc thẳng format gốc** — không giữ tương thích ngược |

### Ghi chú triển khai (đã chốt)

- Lưu **raw tracker-events** + **metadata gốc** xuống `data/<instance_slug>/`.
- Adapter chuyển raw events → cấu trúc `{headers, rows}` (kiểu analytics/events/query) **tại lúc build preview**,
  nên **browser mock `_mockDhis2Get` giữ nguyên**, không phải viết lại.
- `_geo` (ranh giới bản đồ) dựng từ `organisationUnits.json` (geometry, level 1–5) thay cho `geoFeatures` nhúng cũ.
- `data_store` giữ "active instance" (set khi connect) để preview generator đọc đúng thư mục mà không cần truyền `base_url`.
