# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

- Sinh viên cần lưu trữ, quản lý và chia sẻ tài liệu phục vụ học tập.
- Các nhóm dự án nội bộ cần cộng tác trên tài liệu trong một môi trường có kiểm soát truy cập.
- Quản trị viên quản lý tài khoản, vai trò, quyền và theo dõi hoạt động của hệ thống.

## Product Purpose

Xây dựng một hệ thống lưu trữ và chia sẻ tài liệu an toàn trên cloud. Sản phẩm giúp người dùng tải lên, quản lý, tải xuống và chia sẻ tài liệu, đồng thời giúp quản trị viên kiểm soát người dùng và quyền truy cập.

Thành công nghĩa là người dùng có thể cộng tác thuận tiện mà tài liệu vẫn được bảo vệ bằng xác thực, phân quyền, mã hóa và giám sát truy cập phù hợp.

## Positioning

Sản phẩm đặt kiểm soát bảo mật ngay trong luồng quản lý tài liệu: danh tính người dùng, vai trò, quyền truy cập, khôi phục tài khoản bằng OTP và khả năng giám sát phải cùng tạo thành một cơ chế bảo vệ xuyên suốt thay vì là các tính năng rời rạc.

## Operating Context

- Giao diện và nội dung sản phẩm sử dụng tiếng Việt.
- Người dùng đăng ký, đăng nhập và có thể khôi phục mật khẩu bằng OTP qua email.
- Người dùng quản lý tài liệu của mình, đánh dấu yêu thích, đưa vào thùng rác, khôi phục, tải xuống và chia sẻ cho người dùng khác.
- Quản trị viên sử dụng khu vực quản trị để quản lý tài khoản, trạng thái hoạt động, vai trò và quyền.
- Môi trường phát triển local dùng Flask và SQLite.
- Sản phẩm chạy bằng Docker trên Ubuntu và cần hỗ trợ triển khai lên AWS.

## Capabilities and Constraints

- Backend và giao diện web hiện tại dùng Flask với template phía máy chủ.
- SQLite là cơ sở dữ liệu ở giai đoạn local; phương án dữ liệu cho môi trường cloud chưa được xác nhận.
- Hệ thống phải duy trì password hashing, RBAC, OTP, kiểm soát truy cập và bảo vệ dữ liệu.
- Mô hình vai trò hiện có gồm `admin` và `user`; hệ thống dữ liệu có các permission chi tiết.
- Chỉ chủ sở hữu được thay đổi trạng thái tài liệu hoặc chia sẻ tài liệu; người nhận chỉ được truy cập tài liệu đã chia sẻ hợp lệ.
- Việc vô hiệu hóa hoặc xóa tài khoản phải làm mất hiệu lực phiên truy cập liên quan.
- Mã hóa dữ liệu và giám sát truy cập là yêu cầu sản phẩm, nhưng mức độ triển khai hoàn chỉnh của chúng chưa được xác nhận.
- Dự án hiện chưa có CSRF protection đầy đủ; không được mô tả hệ thống là sẵn sàng triển khai công khai cho tới khi khoảng trống này được xử lý.

## Brand Commitments

- Ngôn ngữ giao diện: tiếng Việt.
- Tên làm việc hiện tại: Cloud Security Project.
- Thông điệp và nội dung phải chính xác về năng lực bảo mật; không được tạo tuyên bố, chứng nhận hoặc bằng chứng bảo mật chưa được kiểm chứng.

## Evidence on Hand

- Luồng xác thực và OTP: `app/routes/auth.py`, `app/services/otp_service.py`, `app/services/email_service.py`.
- Quản lý và chia sẻ tài liệu: `app/routes/documents.py`, `app/routes/share.py`, `app/services/storage_service.py`.
- RBAC và khu vực quản trị: `app/permissions.py`, `app/routes/admin.py`, `app/templates/admin/`, `RBAC_README.md`.
- Schema và migration local: `app/database.py`, với `DATABASE_SCHEMA.sql` chỉ dùng để tham khảo.
- Cấu hình Docker: `docker/Dockerfile`, `docker/docker-compose.yml`.
- Bộ kiểm thử hiện có: `tests/test_api.py`, `tests/test_admin_rbac.py`.
- Chưa có bằng chứng được xác nhận về chứng nhận bảo mật, kiểm thử xâm nhập, khách hàng, benchmark, triển khai AWS production hoặc mức độ mã hóa dữ liệu hoàn chỉnh; công việc tương lai không được tự tạo các tuyên bố này.

## Product Principles

1. Quyền truy cập tối thiểu: mỗi người chỉ thấy và thao tác trên tài nguyên mà danh tính, vai trò và quan hệ chia sẻ của họ cho phép.
2. Bảo mật có thể kiểm chứng: mọi tuyên bố bảo vệ dữ liệu phải gắn với cơ chế và bằng chứng triển khai thực tế.
3. Cộng tác không làm suy yếu kiểm soát: chia sẻ tài liệu phải thuận tiện nhưng không vượt qua quyền sở hữu và chính sách truy cập.
4. Vận hành rõ ràng: trạng thái tài khoản, quyền, lỗi xác thực và hoạt động quan trọng phải dễ hiểu và có thể giám sát.
5. Triển khai tiến hóa an toàn: giữ trải nghiệm local đơn giản với Flask và SQLite, đồng thời tránh các quyết định cản trở Docker trên Ubuntu hoặc triển khai AWS sau này.
