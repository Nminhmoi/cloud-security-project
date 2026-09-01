# Ví dụ mở rộng RBAC

> Đây là tài liệu tham khảo, không phải mã đang chạy. Kiểm tra tên blueprint, URL và quy tắc sở hữu tài liệu trước khi áp dụng.

## Bảo vệ upload bằng permission

Route hiện tại là `/upload` trong `app/routes/documents.py`:

```python
from permissions import require_permission

@documents_bp.route("/upload", methods=["POST"])
@require_permission("create_document")
def upload():
    ...
```

## Bảo vệ xóa tài liệu

Permission không thay thế kiểm tra quyền sở hữu. Cần giữ điều kiện `user_id` trong câu lệnh cập nhật:

```python
@documents_bp.route("/delete/<int:document_id>", methods=["POST"])
@require_permission("delete_document")
def delete(document_id):
    connection.execute(
        "UPDATE documents SET is_deleted = 1 WHERE id = ? AND user_id = ?",
        (document_id, session["user_id"]),
    )
```

## Kiểm tra nhiều quyền

Thư viện hiện chưa cung cấp `require_any_permission` hoặc `require_all_permissions`. Nếu bổ sung decorator mới, cần dùng `functools.wraps`, xử lý user chưa đăng nhập và trả HTTP 403 khi thiếu quyền.

## Lưu ý

- Không cho admin toàn quyền với tài liệu của người khác nếu yêu cầu nghiệp vụ chưa nói rõ.
- Mọi truy vấn phải dùng parameter binding của SQLite.
- Request `POST` vẫn cần CSRF token khi triển khai công khai.
- Viết test cho cả user có quyền, thiếu quyền và tài nguyên không thuộc sở hữu.
