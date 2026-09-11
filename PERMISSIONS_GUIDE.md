# Hướng dẫn sử dụng permissions

Các hàm nằm trong `app/permissions.py`. Với cấu trúc chạy hiện tại, route trong `app` import như sau:

```python
from permissions import require_admin, require_login, require_permission, require_role
```

## Decorator

```python
@require_login
def profile():
    ...

@require_permission("create_document")
def upload():
    ...

@require_role("admin")
def settings():
    ...

@require_admin
def admin_page():
    ...
```

`@require_admin` tương đương `@require_role("admin")`.

## Kiểm tra trong code

```python
from permissions import has_permission, has_role, is_admin

has_permission(user_id, "delete_document")
has_role(user_id, "admin")
is_admin(user_id)
```

## Hàm quản lý

- `get_user_permissions(user_id)`
- `get_role_permissions(role_id)`
- `get_all_roles()`
- `get_all_permissions()`
- `assign_role_to_user(user_id, role_id)`
- `assign_permission_to_role(role_id, permission_id)`
- `revoke_permission_from_role(role_id, permission_id)`

Đối với request từ trình duyệt, ưu tiên dùng route trong `app/routes/admin.py` thay vì gọi trực tiếp các hàm gán quyền. Route có thêm kiểm tra dữ liệu, tài khoản hiện tại và admin cuối cùng.

## Phạm vi hiện tại

Route admin dùng RBAC theo vai trò. Route tài liệu web và API kết hợp permission
theo hành động với kiểm tra owner/shared trên từng document. Khi thêm endpoint
tài liệu mới, phải giữ cả hai lớp kiểm tra này.
