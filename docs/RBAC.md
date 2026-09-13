# RBAC, quyền hạn và khu vực quản trị

## Vai trò mặc định

| Vai trò | Mô tả |
|---|---|
| `admin` | Truy cập các trang và API quản trị |
| `user` | Sử dụng chức năng tài liệu thông thường |

Role được xác định bằng tên trong lúc kiểm tra quyền. Không nên viết logic mới phụ thuộc cứng vào ID role.

## Quyền mặc định

`view_documents`, `create_document`, `edit_document`, `delete_document`, `share_document`, `manage_users`, `manage_roles`, `view_reports`, `manage_system`.

Các trang admin dùng `@require_admin`, tức kiểm tra role `admin`. Route tài liệu
trên cả web và REST API enforce `view_documents`, `create_document`,
`edit_document`, `delete_document` và `share_document`; thu hồi một permission
sẽ có hiệu lực ở request tiếp theo.

## Lược đồ dữ liệu

- `roles`: danh sách vai trò.
- `permissions`: danh sách quyền.
- `role_permissions`: quan hệ nhiều-nhiều giữa role và permission.
- `users.role_id`: role của tài khoản, mặc định là role user.
- `users.is_active`: trạng thái tài khoản.

Model trong `app/models/` và Alembic migration trong `migrations/` là nguồn
schema chính thức. `app/database.py` chỉ giữ lớp tương thích cho SQLite local
được tạo từ các phiên bản cũ.

## Quy tắc bảo vệ hiện tại

- Chưa đăng nhập: chuyển tới trang đăng nhập.
- User thường truy cập `/admin/*`: HTTP 403.
- Tài khoản bị vô hiệu hóa: không đăng nhập được; phiên cũ bị xóa ở request tiếp theo.
- Admin không thể tự đổi role, tự vô hiệu hóa hoặc tự xóa.
- Không thể hạ quyền, vô hiệu hóa hoặc xóa admin đang hoạt động cuối cùng.

## Route quản trị

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

## Bảo vệ bổ sung

Các request thay đổi dữ liệu có CSRF token; thao tác quản trị quan trọng được
ghi audit log. Permission theo hành động luôn kết hợp với kiểm tra owner/shared
trên từng tài liệu.

## Cách dùng decorator phân quyền

Các helper nằm trong `app/permissions.py`:

```python
from permissions import require_admin, require_login, require_permission, require_role

@require_login
def profile():
    ...

@require_permission("create_document")
def upload():
    ...

@require_role("admin")
def settings():
    ...
```

`@require_admin` tương đương `@require_role("admin")`. Với route tài liệu,
decorator không thay thế kiểm tra object-level authorization. Truy vấn vẫn phải
ràng buộc `Document.user_id` hoặc `DocumentShare.shared_with_user_id`.

## Giao diện admin

| URL | Nội dung |
|---|---|
| `/admin/dashboard` | Thống kê tổng quan |
| `/admin/users` | Quản lý tài khoản và role |
| `/admin/documents` | Xem metadata và xóa mềm tài liệu |
| `/admin/activity-logs` | Xem tối đa 500 hoạt động gần nhất |
| `/admin/roles` | Gán và thu hồi permission |
| `/admin/permissions` | Danh sách permission |

Các request thay đổi dữ liệu ở giao diện admin gửi CSRF token. Thao tác đổi
role, vô hiệu hóa, xóa user, sửa permission và admin xóa tài liệu được ghi vào
`activity_logs`.

## Quy tắc khi mở rộng

- Không cấp quyền tài liệu cho admin chỉ vì role là `admin` nếu nghiệp vụ không
  yêu cầu.
- Dùng SQLAlchemy parameter binding; không ghép dữ liệu request vào SQL.
- Viết test cho người có quyền, thiếu quyền và tài nguyên thuộc người khác.
- Nếu thêm role tùy chỉnh, phụ thuộc vào tên role/permission thay vì ID cố định,
  ngoại trừ dữ liệu seed mặc định.
