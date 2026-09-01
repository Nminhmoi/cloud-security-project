# Phân quyền RBAC

## Vai trò mặc định

| Vai trò | Mô tả |
|---|---|
| `admin` | Truy cập các trang và API quản trị |
| `user` | Sử dụng chức năng tài liệu thông thường |

Role được xác định bằng tên trong lúc kiểm tra quyền. Không nên viết logic mới phụ thuộc cứng vào ID role.

## Quyền mặc định

`view_documents`, `create_document`, `edit_document`, `delete_document`, `share_document`, `manage_users`, `manage_roles`, `view_reports`, `manage_system`.

Hiện tại các trang admin dùng `@require_admin`, tức kiểm tra role `admin`. Các permission chi tiết đã có trong database và thư viện nhưng chưa được gắn vào toàn bộ route tài liệu.

## Schema

- `roles`: danh sách vai trò.
- `permissions`: danh sách quyền.
- `role_permissions`: quan hệ nhiều-nhiều giữa role và permission.
- `users.role_id`: role của tài khoản, mặc định là role user.
- `users.is_active`: trạng thái tài khoản.

Schema và migration chính thức nằm trong `app/database.py`. `DATABASE_SCHEMA.sql` chỉ dùng để đọc và tra cứu.

## Quy tắc bảo vệ hiện tại

- Chưa đăng nhập: chuyển tới trang đăng nhập.
- User thường truy cập `/admin/*`: HTTP 403.
- Tài khoản bị vô hiệu hóa: không đăng nhập được; phiên cũ bị xóa ở request tiếp theo.
- Admin không thể tự đổi role, tự vô hiệu hóa hoặc tự xóa.
- Không thể hạ quyền, vô hiệu hóa hoặc xóa admin đang hoạt động cuối cùng.

## Route admin

| Method | Route | Chức năng |
|---|---|---|
| GET | `/admin/dashboard` | Dashboard |
| GET | `/admin/users` | Danh sách user |
| GET | `/admin/users/<id>` | Chi tiết user |
| POST | `/admin/users/<id>/role` | Đổi role |
| POST | `/admin/users/<id>/toggle-active` | Đổi trạng thái |
| POST | `/admin/users/<id>/delete` | Xóa user |
| GET | `/admin/roles` | Danh sách role và quyền |
| GET | `/admin/roles/<id>/permissions` | Quyền của role |
| POST | `/admin/roles/<id>/assign-permission` | Gán quyền |
| POST | `/admin/roles/<id>/revoke-permission` | Thu hồi quyền |
| GET | `/admin/permissions` | Danh sách quyền |

## Giới hạn bảo mật

Dự án chưa triển khai CSRF token và audit log. Không xem việc dùng method `POST` là CSRF protection.
