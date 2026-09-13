# Tổng quan dự án CloudBox

## Loại hệ thống

Ứng dụng web quản lý tài liệu, gồm giao diện server-rendered và REST API dùng
chung Flask session.

## Đối tượng sử dụng

- Sinh viên cần lưu trữ, quản lý và chia sẻ tài liệu phục vụ học tập.
- Các nhóm dự án nội bộ cần cộng tác trên tài liệu trong một môi trường có kiểm soát truy cập.
- Quản trị viên quản lý tài khoản, vai trò, quyền và theo dõi hoạt động của hệ thống.

## Mục tiêu

Xây dựng một hệ thống lưu trữ và chia sẻ tài liệu an toàn trên cloud. Sản phẩm giúp người dùng tải lên, quản lý, tải xuống và chia sẻ tài liệu, đồng thời giúp quản trị viên kiểm soát người dùng và quyền truy cập.

Thành công nghĩa là người dùng có thể cộng tác thuận tiện mà tài liệu vẫn được
bảo vệ bằng xác thực, phân quyền, mã hóa và giám sát truy cập phù hợp. Dự án
đồng thời minh họa cách ánh xạ security controls trong ứng dụng sang hạ tầng
AWS dưới dạng Terraform.

## Phạm vi chức năng

- Đăng ký, đăng nhập, đăng xuất và khôi phục mật khẩu bằng OTP.
- Quản lý tài liệu cá nhân: upload, download, yêu thích, thùng rác và restore.
- Chia sẻ và thu hồi quyền xem tài liệu cho người dùng khác.
- Quản trị tài khoản, role, permission và xem activity log.
- Lưu file ở local hoặc S3; lưu metadata ở SQLite hoặc MySQL.
- Cung cấp Docker, migration, CI security gates và phương án triển khai AWS.

## Công nghệ

| Lớp | Công nghệ chính |
|---|---|
| Backend | Python 3.12, Flask, SQLAlchemy |
| Database | SQLite local, MySQL 8.4/RDS |
| Storage | Local filesystem hoặc Amazon S3 |
| Frontend | Jinja templates, CSS, JavaScript |
| Infrastructure | Docker Compose, Terraform, AWS |
| Quality | unittest, Bandit, pip-audit, Trivy, GitHub Actions |

## Định hướng

Sản phẩm đặt kiểm soát bảo mật ngay trong luồng quản lý tài liệu: danh tính người dùng, vai trò, quyền truy cập, khôi phục tài khoản bằng OTP và khả năng giám sát phải cùng tạo thành một cơ chế bảo vệ xuyên suốt thay vì là các tính năng rời rạc.

## Bối cảnh vận hành

- Giao diện và nội dung sản phẩm sử dụng tiếng Việt.
- Người dùng đăng ký, đăng nhập và có thể khôi phục mật khẩu bằng OTP qua email.
- Người dùng quản lý tài liệu của mình, đánh dấu yêu thích, đưa vào thùng rác, khôi phục, tải xuống và chia sẻ cho người dùng khác.
- Quản trị viên sử dụng khu vực quản trị để quản lý tài khoản, trạng thái hoạt động, vai trò và quyền.
- Môi trường phát triển local dùng Flask và SQLite.
- Sản phẩm chạy bằng Docker trên Ubuntu và cần hỗ trợ triển khai lên AWS.

## Năng lực và giới hạn

- Backend và giao diện web hiện tại dùng Flask với template phía máy chủ.
- SQLite là cơ sở dữ liệu local; Docker và phương án AWS sử dụng MySQL 8.4 trên Amazon RDS.
- Hệ thống phải duy trì password hashing, RBAC, OTP, kiểm soát truy cập và bảo vệ dữ liệu.
- Mô hình vai trò hiện có gồm `admin` và `user`; hệ thống dữ liệu có các permission chi tiết.
- Chỉ chủ sở hữu được thay đổi trạng thái tài liệu hoặc chia sẻ tài liệu; người nhận chỉ được truy cập tài liệu đã chia sẻ hợp lệ.
- Việc vô hiệu hóa hoặc xóa tài khoản phải làm mất hiệu lực phiên truy cập liên quan.
- Dữ liệu AWS được bảo vệ bằng mã hóa mặc định của S3, EBS và RDS; kết nối RDS yêu cầu TLS.
- CSRF được bật toàn cục cho form và API thay đổi dữ liệu. Ứng dụng còn có rate limit, account lockout, security headers và vô hiệu hóa session sau khi tài khoản hoặc mật khẩu thay đổi.
- Malware scanning, HTTPS với domain, AWS Backup nâng cao và restore testing là các khả năng tùy chọn hoặc chưa bật vì phát sinh chi phí.
- Đây là bài tập lớn và môi trường minh họa, không phải tuyên bố hệ thống production hoặc chứng nhận bảo mật.

## Nguyên tắc trình bày

- Ngôn ngữ giao diện: tiếng Việt.
- Tên làm việc hiện tại: Cloud Security Project.
- Thông điệp và nội dung phải chính xác về năng lực bảo mật; không được tạo tuyên bố, chứng nhận hoặc bằng chứng bảo mật chưa được kiểm chứng.

## Bằng chứng trong repository

- Luồng xác thực và OTP: `app/routes/auth.py`, `app/services/otp_service.py`, `app/services/email_service.py`.
- Quản lý và chia sẻ tài liệu: `app/routes/documents.py`, `app/routes/share.py`, `app/services/storage_service.py`.
- RBAC và khu vực quản trị: `app/permissions.py`, `app/routes/admin.py`, `app/templates/admin/` và `docs/RBAC.md`.
- Schema: model trong `app/models/`, Alembic trong `migrations/`; `app/database.py` hỗ trợ database SQLite cũ.
- Cấu hình Docker: `docker/Dockerfile`, `docker/docker-compose.yml`.
- Bộ kiểm thử: `tests/`, `security/**/test_*.py`, kiểm tra tích hợp trong `scripts/` và các gate trong `.github/workflows/ci.yml`.
- Chưa có bằng chứng về chứng nhận bảo mật, pentest độc lập, benchmark hoặc một
  deployment AWS production đang vận hành. Không dùng Terraform plan hay tính
  năng dự kiến để tuyên bố một control cloud đang hoạt động thật.

## Nguyên tắc thiết kế

1. Quyền truy cập tối thiểu: mỗi người chỉ thấy và thao tác trên tài nguyên mà danh tính, vai trò và quan hệ chia sẻ của họ cho phép.
2. Bảo mật có thể kiểm chứng: mọi tuyên bố bảo vệ dữ liệu phải gắn với cơ chế và bằng chứng triển khai thực tế.
3. Cộng tác không làm suy yếu kiểm soát: chia sẻ tài liệu phải thuận tiện nhưng không vượt qua quyền sở hữu và chính sách truy cập.
4. Vận hành rõ ràng: trạng thái tài khoản, quyền, lỗi xác thực và hoạt động quan trọng phải dễ hiểu và có thể giám sát.
5. Triển khai tiến hóa an toàn: giữ trải nghiệm local đơn giản với Flask và SQLite, đồng thời tránh các quyết định cản trở Docker trên Ubuntu hoặc triển khai AWS sau này.

## Ngoài phạm vi

- Cam kết SLA, high availability hoặc disaster recovery production.
- WAF, Auto Scaling, SIEM và malware scanning trả phí.
- Mobile application, OAuth/social login và public developer API bằng JWT.
- Chứng nhận tuân thủ hoặc tuyên bố hệ thống đã vượt qua pentest.

Các mục ngoài phạm vi có thể được nêu ở phần hướng phát triển, nhưng không phải
điều kiện để hoàn thành bài tập lớn.
