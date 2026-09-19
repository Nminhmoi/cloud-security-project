# REST API

Các endpoint dùng đường dẫn gốc `/api/v1` và xác thực bằng cookie phiên đăng nhập của Flask. Sau khi đăng nhập, client cần gửi kèm cookie trong những yêu cầu tiếp theo. Phản hồi thành công chứa trường `data`; phản hồi lỗi có dạng `{"error": {"message": "...", "status": 400}}`.

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
| POST | `/documents` | Tải lên `multipart/form-data`, field `file` |
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

Mật khẩu mới dài từ 12 đến 128 ký tự theo mặc định. Tệp tải lên có kích thước tối đa 16 MiB và chỉ
nhận `pdf`, `txt`, `csv`, `png`, `jpg`, `jpeg`, `docx`, `xlsx`, `pptx`, `zip`.
Metadata trả về gồm tên hiển thị, kích thước, MIME đã kiểm tra, SHA-256 và trạng
thái quét; khóa riêng tư `storage_key` không xuất hiện trong API. Hạn mức lưu trữ mặc định là
500 MiB cho mỗi tài khoản và tính cả tài liệu trong thùng rác.
Server có thể trả `413` khi tệp quá lớn và `429` khi vượt giới hạn request hoặc
tài khoản tạm thời bị khóa.

## Quy ước quyền truy cập

- `401`: chưa có session hợp lệ.
- `403`: đã đăng nhập nhưng thiếu quyền hoặc file không vượt qua kiểm tra
  an toàn.
- `404`: tài nguyên không tồn tại hoặc không thuộc phạm vi người dùng được xem.
- Permission theo hành động luôn được kết hợp với quyền sở hữu hoặc quan hệ
  chia sẻ; biết ID tài liệu không tạo ra quyền truy cập.

Khi tích hợp API, hãy giữ cookie và CSRF token trong cùng một phiên. API hiện chưa hỗ trợ xác thực bằng Bearer token hoặc JWT.
