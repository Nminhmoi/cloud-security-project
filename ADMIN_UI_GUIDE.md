# Hướng dẫn giao diện admin

## Truy cập

Đăng nhập bằng tài khoản có role `admin`, sau đó dùng:

| URL | Nội dung |
|---|---|
| `/admin/dashboard` | Thống kê tổng quan |
| `/admin/users` | Quản lý tài khoản và role |
| `/admin/roles` | Xem, gán và thu hồi permission |
| `/admin/permissions` | Danh sách permission |

## Quản lý user

Trang `/admin/users` hỗ trợ tìm kiếm, đổi role, kích hoạt/vô hiệu hóa và xóa tài khoản.

Các ràng buộc phía server:

- Không được thay đổi role, vô hiệu hóa hoặc xóa chính mình.
- Không được làm mất admin đang hoạt động cuối cùng.
- ID user, role và JSON request đều được kiểm tra.
- Khi xóa user, các bản ghi chia sẻ liên quan được xóa trước để tránh lỗi khóa ngoại.

## Quản lý role và permission

Trang `/admin/roles` hiển thị permission của từng role và gửi request tới API gán/thu hồi. Trang này không tạo hoặc xóa role mới.

Trang `/admin/permissions` chỉ hiển thị danh sách permission; không chỉnh sửa trực tiếp.

## File giao diện

- `app/templates/admin/dashboard.html`
- `app/templates/admin/users.html`
- `app/templates/admin/roles.html`
- `app/templates/admin/permissions.html`
- `app/static/admin.css`

## Bảo mật

Tất cả route trong blueprint admin được bảo vệ bằng `@require_admin`. Tuy nhiên dự án hiện **chưa có CSRF protection**. Trước khi triển khai công khai, cần bổ sung token CSRF cho form và các request JavaScript thay đổi dữ liệu.
