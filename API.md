# REST API

Base URL: `/api/v1`. API dùng session cookie của Flask. Sau khi gọi đăng nhập,
client cần gửi lại cookie trong các request tiếp theo. Thành công trả về trường
`data`; lỗi trả về `{"error": {"message": "...", "status": 400}}`.

Các request `POST`, `PATCH` và `DELETE` phải gửi CSRF token. Lấy token từ
`GET /csrf-token`, giữ session cookie và gửi token trong header `X-CSRFToken`.

| Method | Endpoint | Mô tả |
|---|---|---|
| GET | `/csrf-token` | Tạo CSRF token cho session hiện tại |
| POST | `/auth/register` | Đăng ký bằng JSON `username`, `email`, `password` |
| POST | `/auth/login` | Đăng nhập bằng JSON `username`, `password` |
| POST | `/auth/logout` | Đăng xuất |
| GET | `/me` | Lấy người dùng hiện tại |
| GET | `/documents?view=mine\|shared\|deleted` | Danh sách tài liệu |
| POST | `/documents` | Upload `multipart/form-data`, field `file` |
| GET | `/documents/{id}/download` | Tải tài liệu được phép truy cập |
| DELETE | `/documents/{id}` | Xóa mềm tài liệu của mình |
| POST | `/documents/{id}/restore` | Khôi phục tài liệu |
| PATCH | `/documents/{id}/favorite` | JSON `is_favorite` (boolean) |
| GET | `/users/search?q=...` | Tìm người nhận đang hoạt động |
| GET | `/documents/{id}/shares` | Danh sách người được chia sẻ |
| POST | `/documents/{id}/shares` | JSON `recipient` (username/email) |
| DELETE | `/documents/{id}/shares/{user_id}` | Thu hồi chia sẻ |

```bash
TOKEN=$(curl -s -c cookies.txt http://localhost:5000/api/v1/csrf-token | jq -r .data.csrf_token)

curl -b cookies.txt -c cookies.txt -X POST http://localhost:5000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -H "X-CSRFToken: $TOKEN" \
  -d '{"username":"user#1","password":"Correct-Horse-123"}'

curl -b cookies.txt -F "file=@report.pdf" \
  -H "X-CSRFToken: $TOKEN" \
  http://localhost:5000/api/v1/documents
```

Mật khẩu mới dài từ 12 đến 128 ký tự theo mặc định. Upload tối đa 16 MiB và chỉ
nhận `pdf`, `txt`, `csv`, `png`, `jpg`, `jpeg`, `docx`, `xlsx`, `pptx`, `zip`.
Metadata trả về gồm tên hiển thị, kích thước, MIME đã kiểm tra, SHA-256 và trạng
thái scan; private `storage_key` không xuất hiện trong API. Quota mặc định là
500 MiB cho mỗi tài khoản và tính cả tài liệu trong thùng rác.
Server có thể trả `413` khi tệp quá lớn và `429` khi vượt giới hạn request hoặc
tài khoản tạm thời bị khóa.
