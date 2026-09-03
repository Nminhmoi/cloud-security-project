# REST API

Base URL: `/api/v1`. API dùng session cookie của Flask. Sau khi gọi đăng nhập,
client cần gửi lại cookie trong các request tiếp theo. Thành công trả về trường
`data`; lỗi trả về `{"error": {"message": "...", "status": 400}}`.

| Method | Endpoint | Mô tả |
|---|---|---|
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
curl -c cookies.txt -X POST http://localhost:5000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"user#1","password":"secret123"}'

curl -b cookies.txt -F "file=@report.pdf" \
  http://localhost:5000/api/v1/documents
```
