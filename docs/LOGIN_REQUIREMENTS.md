# Login / Connection Screen — Requirements

Đặc tả màn **Config panel (index 0)** — nơi người dùng kết nối DHIS2, quản lý profile,
nhập Anthropic API key và chọn AI model. Đây là điểm vào của ứng dụng.

> Tài liệu mô tả **hành vi hiện tại của code** (reverse-engineered) làm chuẩn để bảo trì/kiểm thử.
> Code nguồn: [ui/app_window.py](../ui/app_window.py) (`_build_config_content`, `_on_connect`,
> `_connect_worker`, `_on_connect_done`), [config/credentials.py](../config/credentials.py),
> [dhis2/client.py](../dhis2/client.py), [dhis2/cache.py](../dhis2/cache.py).

---

## 1. Phạm vi & bố cục

Config panel là một `QScrollArea` (nền tối, index 0 của `QStackedWidget`) gồm 3 mục:

1. **DHIS2 Connection** — profile, URL/username/password, nút Connect/Save/Refresh, trạng thái, Filters.
2. **Anthropic API Key** — ô nhập (ẩn) + nút lưu.
3. **AI Model** — dropdown chọn model.

| # | Thành phần | Widget | Ghi chú |
|---|---|---|---|
| 1 | Saved profiles | `QComboBox` + nút `✕` xóa | item đầu là placeholder `— Saved profiles —` |
| 2 | Server URL | `QLineEdit` | placeholder `https://hmis.example.org` |
| 3 | Username | `QLineEdit` | placeholder `admin` |
| 4 | Password | `QLineEdit` (EchoMode.Password) | placeholder `••••••••` |
| 5 | Connect | `QPushButton` | xanh DHIS2; khi nối xong → `✓ Connected` (xanh lá, disabled) |
| 6 | Save profile | `QPushButton 💾` | lưu vào Windows Credential Manager |
| 7 | Refresh metadata | `QPushButton ↻` | ép tải lại metadata từ server (bỏ cache) |
| 8 | Change connection | `QPushButton ↺` | chỉ hiện **sau khi** kết nối |
| 9 | Connection status | `QLabel` | `● Not connected` / `● {tên} (N DEs \| M programs)` / `● Connection failed` |
| 10 | Cache label | `QLabel` | `Cached — {time}` hoặc `Metadata freshly loaded.` |
| 11 | Filters && Load Metadata | `QPushButton ⚙` | **disabled** đến khi kết nối |
| 12 | API key | `QLineEdit` (Password) + `💾` | prefill từ `.env` hoặc keyring |
| 13 | AI Model | `QComboBox` | Haiku / Sonnet / Opus |

---

## 2. Saved profiles (REQ-LOGIN-PROFILE)

- **REQ-LOGIN-PROFILE-01** — Dropdown liệt kê các profile đã lưu, định dạng `"{username}  @  {url_rút_gọn}"` (`profile_label`).
- **REQ-LOGIN-PROFILE-02** — Chọn một profile → điền URL/username, nạp password từ Credential Manager, **tự kết nối** sau 100 ms (`_on_profile_selected` → `QTimer.singleShot(100, _on_connect)`).
- **REQ-LOGIN-PROFILE-03** — Nút `💾` lưu profile: yêu cầu **URL + username** (không bắt buộc password để lưu entry). URL+username ghi `config/profiles.json`; password ghi keyring (`save_profile`).
- **REQ-LOGIN-PROFILE-04** — Nút `✕` xóa profile: hiện `QMessageBox` xác nhận; nếu Yes → xóa entry + xóa password khỏi Credential Manager (`delete_profile`).
- **REQ-LOGIN-PROFILE-05** — Upsert: lưu trùng (url, username) **không** tạo bản ghi mới, chỉ cập nhật password.

## 3. Auto-connect khi khởi động (REQ-LOGIN-AUTO)

- **REQ-LOGIN-AUTO-01** — Lúc mở app (`_load_saved_credentials`): nạp danh sách profile, khôi phục API key.
- **REQ-LOGIN-AUTO-02** — Nếu có profile đã lưu → chọn **profile đầu tiên**, điền URL/username/password; nếu có password → **tự kết nối** sau 200 ms.
- **REQ-LOGIN-AUTO-03** — API key: ưu tiên biến môi trường `ANTHROPIC_API_KEY` (`.env`); nếu trống thì nạp từ keyring.

## 4. Luồng kết nối (REQ-LOGIN-CONN)

- **REQ-LOGIN-CONN-01** — Nhấn **Connect** validate: phải có **URL + username + password**, nếu thiếu → báo lỗi đỏ ở status bar, không kết nối.
- **REQ-LOGIN-CONN-02** — Kết nối chạy trên **thread nền** (`_connect_worker`); UI không bị treo; progress bar chuyển sang chế độ indeterminate. Nút Connect đổi `Connecting…`, bị disable.
- **REQ-LOGIN-CONN-03** — Xác thực qua `GET /api/me.json` (`test_connection`); tên hiển thị lấy từ `name`/`username`.
- **REQ-LOGIN-CONN-04** — Giao tiếp luồng↔UI qua Qt **Signals** (`_sig_connect_done` / `_sig_connect_fail` / `_sig_status`) — không gọi widget trực tiếp từ thread.
- **REQ-LOGIN-CONN-05** — Thành công → `_on_connect_done`: ẩn login frame, hiện `↺ Change connection`, status xanh lá `● {tên} (N DEs | M programs)`, mở khóa nav (Chart Editor, Dashboard, Metadata Editor), chuyển sang panel `chart_editor`, cấu hình preview-server proxy, và **tải dữ liệu mẫu nền** ([sample_fetcher](../dhis2/sample_fetcher.py)).
- **REQ-LOGIN-CONN-06** — Thất bại → `_on_connect_fail`: status đỏ `● Connection failed`, hiện thông báo lỗi, bật lại Connect.

## 5. Cache-first metadata & Refresh (REQ-LOGIN-CACHE)

- **REQ-LOGIN-CACHE-01** — Khi connect, nếu **đã có cache** cho URL đó và **không** ép refresh → dùng cache ngay (không gọi lại server), hiện `Cached — {thời gian}` (vàng).
- **REQ-LOGIN-CACHE-02** — Không có cache → fetch metadata theo `filter_cfg` hiện tại, lưu cache, hiện `Metadata freshly loaded.` (xanh).
- **REQ-LOGIN-CACHE-03** — Nút `↻` (`_on_refresh_metadata`) ép `force_refresh=True` → bỏ qua cache, tải lại từ server.
- **REQ-LOGIN-CACHE-04** — Cache key theo **URL** (`dhis2/cache.py::_url_slug`), lưu tại `cache/<url_slug>/metadata.json`.

## 6. Trạng thái sau kết nối & đổi kết nối (REQ-LOGIN-STATE)

- **REQ-LOGIN-STATE-01** — Sau khi nối: login frame ẩn, các ô URL/username/password ở chế độ chỉ đọc cho đến khi bấm `↺`.
- **REQ-LOGIN-STATE-02** — `↺ Change connection` (`_on_change_connection`): quay về panel config, hiện lại login frame, mở khóa các ô, reset nút Connect.
- **REQ-LOGIN-STATE-03** — `⚙ Filters && Load Metadata` chỉ bật sau khi kết nối; mở dialog cấu hình filter (program/dataset/DE-group) rồi tải lại metadata theo phạm vi.
- **REQ-LOGIN-STATE-04** — Trước khi kết nối, các nút nav Chart Editor/Dashboard/Metadata Editor **bị khóa**.

## 7. Anthropic API Key (REQ-LOGIN-APIKEY)

- **REQ-LOGIN-APIKEY-01** — Ô nhập ở chế độ ẩn (Password echo); prefill nếu đã có key (env/keyring).
- **REQ-LOGIN-APIKEY-02** — Nút `💾` lưu key vào Credential Manager (`save_api_key`); rỗng → báo lỗi.
- **REQ-LOGIN-APIKEY-03** — Key được truyền cho Chart Editor qua callback `get_api_key` (ưu tiên giá trị trong ô, fallback `_api_key`).

## 8. AI Model (REQ-LOGIN-MODEL)

- **REQ-LOGIN-MODEL-01** — Dropdown ánh xạ nhãn → model id (`_MODEL_OPTIONS`):
  Haiku 4.5 → `claude-haiku-4-5-20251001`, Sonnet 4.6 → `claude-sonnet-4-6`, Opus 4.8 → `claude-opus-4-8`.
- **REQ-LOGIN-MODEL-02** — `get_model` trả id của nhãn đang chọn; mặc định Haiku nếu không khớp.

## 9. Bảo mật (REQ-LOGIN-SEC)

- **REQ-LOGIN-SEC-01** — **Mật khẩu DHIS2** và **API key**: chỉ lưu trong **Windows Credential Manager** (keyring/DPAPI, theo từng user Windows) — **không** ghi plaintext ra đĩa.
- **REQ-LOGIN-SEC-02** — **URL + username** lưu plaintext tại `config/profiles.json` (không nhạy cảm).
- **REQ-LOGIN-SEC-03** — Credential dùng để gọi API giữ **in-memory** trong `DHIS2Client` (Basic Auth) suốt phiên; không log ra file.
- **REQ-LOGIN-SEC-04** — Nếu `keyring` không khả dụng → password/API key không lưu được (im lặng trả `""`); app vẫn chạy nhưng phải nhập tay mỗi lần.

---

## 10. Acceptance / Test

- UI integration: [scripts/manual/test_ui.py](../scripts/manual/test_ui.py) (chạy không cần mạng, mô phỏng qua QTest + mock).
- Kiểm thử thủ công tối thiểu:
  1. Mở app không có profile → chỉ Config panel, nav khóa, status `● Not connected`.
  2. Nhập URL/user/pass sai → `● Connection failed`, Connect bật lại.
  3. Nhập đúng → `✓ Connected`, nav mở, nhảy sang Chart Editor.
  4. Lưu profile → khởi động lại → tự kết nối.
  5. `↻` → tải lại metadata (label đổi sang "freshly loaded").
  6. `↺` → quay lại sửa kết nối được.

---

## 11. Yêu cầu bổ sung — cần triển khai (TO-DO)

Khác với các mục trên (mô tả hành vi hiện có), phần này là **tính năng mới cần thêm**:

- **REQ-LOGIN-UX-01 — Nút ẩn/hiện mật khẩu**: thêm toggle 👁 ở ô Password (và nên cả ô API key)
  để chuyển `EchoMode.Password ↔ Normal`, giúp người dùng kiểm tra giá trị đã nhập.
- **REQ-LOGIN-VAL-01 — Kiểm tra định dạng URL**: trước khi gọi `Connect`, validate Server URL
  (bắt đầu bằng `http://`/`https://`, có host hợp lệ); URL sai → báo lỗi đỏ ở status bar, **không** gọi mạng.
  Tự chuẩn hóa: bỏ `/` cuối, thêm scheme `https://` nếu thiếu (tùy chọn).

## 12. Quan sát (thông tin, không cần sửa)

1. **Auto-connect tự dùng mật khẩu đã lưu** ngay khi mở app — đã chấp nhận (tiện cho máy cá nhân).
2. `profiles.json` nằm trong `config/` — `.gitignore` đã loại `*.json` nên không bị commit (giữ quy tắc này).
