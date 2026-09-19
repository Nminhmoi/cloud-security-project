# Bảo mật tải lên và vòng đời file

Trước khi lưu tệp vào ổ đĩa cục bộ hoặc S3, CloudBox kiểm tra kích thước, phần mở rộng, MIME, chữ ký tệp và cấu trúc bên trong của tệp Office hoặc tệp nén. Mỗi tệp được giới hạn mặc định ở 16 MiB; mỗi người dùng có hạn mức lưu trữ riêng.

Ứng dụng còn lưu SHA-256, tạo khóa lưu trữ riêng tư ngẫu nhiên, kiểm tra quyền bằng RBAC và cho phép khôi phục tài liệu từ thùng rác. Các biện pháp này không cần thêm dịch vụ trả phí.

## Cấu hình

Có thể thay đổi giá trị mặc định bằng biến môi trường:

```dotenv
MAX_UPLOAD_BYTES=16777216
USER_STORAGE_QUOTA_BYTES=524288000
DELETED_DOCUMENT_RETENTION_DAYS=30
MAX_ARCHIVE_MEMBERS=1000
MAX_ARCHIVE_UNCOMPRESSED_BYTES=134217728
MAX_ARCHIVE_COMPRESSION_RATIO=100
```

Quota tính cả tài liệu đang hoạt động và đã xóa mềm vì cả hai vẫn chiếm dung
lượng. Chỉ đặt `USER_STORAGE_QUOTA_BYTES=0` khi thực sự muốn không giới hạn.

## Thông tin tệp và khóa lưu trữ

`filename` là tên hiển thị đã được làm sạch. `storage_key` là vị trí riêng tư,
ngẫu nhiên và không được trả về bởi document API. Với tệp mới tải lên, ứng dụng còn lưu MIME đã
kiểm tra, kích thước byte, SHA-256 và trạng thái scan. Bản ghi database cũ có
thể dùng `filename` làm storage reference dự phòng.

Chạy migration trước khi triển khai phiên bản ứng dụng mới:

```powershell
docker compose --env-file .env -f docker/docker-compose.yml run --rm migrate
```

## Dọn thùng rác

Xóa mềm ghi `deleted_at`; khôi phục sẽ xóa giá trị này. Chạy định kỳ lệnh sau để
xóa bản ghi cơ sở dữ liệu và object local/S3 sau thời hạn lưu:

```powershell
docker compose --env-file .env -f docker/docker-compose.yml run --rm web `
  flask --app app.py purge-deleted-documents
```

Để kiểm tra ngay trên môi trường dùng một lần, truyền `--retention-days 0`.
Không dùng thời hạn bằng 0 nếu người dùng cần khôi phục từ thùng rác. S3
Versioning giữ các version đã xóa trong thời gian lifecycle của Terraform và tự
dọn expired delete marker.

EC2 được tạo bởi Terraform sẽ bật `cloudbox-trash-purge.timer` để chạy cùng lệnh
mỗi ngày. Kiểm tra qua Systems Manager Session Manager:

```bash
systemctl status cloudbox-trash-purge.timer
journalctl -u cloudbox-trash-purge.service
```

## Giới hạn của việc quét mã độc

Kiểm tra MIME, signature và archive chỉ xác minh cấu trúc, không phải quét mã
độc. Nếu cho phép tải tệp lên từ nguồn không tin cậy, cần tích hợp scanner bất đồng bộ
và dùng các trạng thái `pending`, `clean`, `infected`, `failed`. Việc tải xuống phải bị chặn cho đến khi kết quả là `clean`; ứng dụng hiện chặn record ở trạng thái
`pending`, `infected` và `failed`.

[GuardDuty Malware Protection for S3](https://docs.aws.amazon.com/guardduty/latest/ug/how-malware-protection-for-s3-gdu-works.html)
là một lựa chọn AWS phù hợp nhưng không bật mặc định vì tính phí theo object.
Khi chưa có scanner, file mới mang trạng thái `not_scanned` và vẫn được tải sau
khi vượt qua kiểm tra cấu trúc tệp.
