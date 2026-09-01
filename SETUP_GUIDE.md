# Hướng dẫn cài đặt và vận hành

## Yêu cầu

- Python 3
- Các package trong `app/requirements.txt`: Flask và Werkzeug

## Cài đặt

```powershell
cd E:\BtapThucHanh\Antoanthongtin\cloud-security-project
py -m venv .venv
.venv\Scripts\python.exe -m pip install -r app\requirements.txt
```

## Chạy ứng dụng

```powershell
.venv\Scripts\python.exe app\app.py
```

Ứng dụng chạy mặc định tại `http://localhost:5000`.

Không dùng `python -c "from app.app import app"` trong cấu trúc hiện tại vì các module đang dùng import tuyệt đối từ thư mục `app`.

## Database

Đường dẫn mặc định là `cloud-security-project/database.db`. Có thể đổi bằng biến môi trường:

```powershell
$env:DATABASE_PATH = "D:\data\cloudbox.db"
.venv\Scripts\python.exe app\app.py
```

Nếu file chưa tồn tại, SQLite tự tạo file và `init_db()` tạo bảng. Nếu mở database phiên bản cũ, migration trong `app/database.py` bổ sung các cột còn thiếu. Luôn sao lưu trước khi nâng cấp.

Khôi phục bản database đã commit gần nhất:

```powershell
git restore --source=HEAD -- database.db
```

Lệnh này chỉ phục hồi dữ liệu tại thời điểm commit; dữ liệu mới hơn cần bản sao lưu riêng.

## Tài khoản admin

Tạo admin đầu tiên hoặc quản lý admin hiện có:

```powershell
.venv\Scripts\python.exe admin.py
```

Script này nằm ngoài `app` là hợp lý vì đây là công cụ vận hành, không phải module phục vụ request web.

## Kiểm tra

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -v
sqlite3 database.db "PRAGMA integrity_check;"
```

Kết quả integrity mong đợi là `ok`.
