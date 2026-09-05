# Kiểm thử MySQL bằng Docker Compose

Cấu hình Compose gồm các service sau:

- `db`: MySQL 8.4, dữ liệu được giữ trong volume `mysql_data`.
- `migrate`: chờ MySQL healthy rồi chạy `flask db upgrade` trước ứng dụng.
- `web`: ứng dụng chính tại cổng 5000.
- `web-secondary`: ứng dụng thứ hai tại cổng 5001, chỉ chạy trong profile
  `integration` để kiểm tra dùng chung database và session.

## Chuẩn bị

Từ thư mục gốc của project:

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

Nếu `.env` đã tồn tại, chỉ bổ sung các biến MySQL còn thiếu. Thay các giá trị
`SECRET_KEY`, `DB_PASSWORD` và `MYSQL_ROOT_PASSWORD`; không commit file `.env`.

## Chạy bình thường

```powershell
docker compose --env-file .env -f docker/docker-compose.yml up -d --build
docker compose --env-file .env -f docker/docker-compose.yml ps
docker compose --env-file .env -f docker/docker-compose.yml logs migrate
```

`migrate` phải kết thúc với exit code 0 và `web`, `db` phải ở trạng thái
healthy. Dừng container nhưng giữ dữ liệu:

```powershell
docker compose --env-file .env -f docker/docker-compose.yml down
```

Không thêm `--volumes` nếu muốn giữ database.

## Kiểm tra hai container dùng chung tài khoản

Script sau build stack, đăng ký tài khoản qua `web`, đọc session từ
`web-secondary`, restart hai web container, restart MySQL và đăng nhập lại.
Script dùng cổng 15000/15001 để không xung đột ứng dụng local đang chạy:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/test-mysql-containers.ps1
```

Kết thúc thành công sẽ in bốn dòng `PASS`. Các container và volume được giữ
lại để có thể kiểm tra dữ liệu sau test.

Có thể dùng một stack hoàn toàn tạm thời với secret ngẫu nhiên và tự dọn đúng
volume vừa tạo:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/test-mysql-containers.ps1 `
  -TemporaryStack -Cleanup
```

## Kiểm tra migration thủ công

```powershell
docker compose --env-file .env -f docker/docker-compose.yml run --rm migrate
docker compose --env-file .env -f docker/docker-compose.yml exec db `
  mysql -u cloudbox -p cloudbox -e "SELECT version_num FROM alembic_version;"
```

Giá trị `version_num` phải trùng revision mới nhất trong `migrations/versions`.

## Khi triển khai EC2/RDS

Trên EC2 chỉ chạy `web` và một job `migrate`; đặt `DB_HOST` thành endpoint RDS.
Không public cổng 3306. Security Group của RDS chỉ cho phép kết nối từ Security
Group của EC2. Đặt `SESSION_COOKIE_SECURE=true` sau khi HTTPS hoạt động.
