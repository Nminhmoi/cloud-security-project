# Sao lưu và khôi phục

CloudBox dùng cơ chế khôi phục riêng cho SQLite local và Amazon RDS. Một bản sao
lưu chỉ được xem là hữu ích sau khi đã kiểm tra tính toàn vẹn hoặc thử đường
khôi phục của nó.

## Amazon RDS

Automated backup và point-in-time recovery của RDS mặc định được giữ trong bảy
ngày. Terraform cũng giữ automated backup khi DB instance được quản lý bị xóa.
Thay đổi thời gian lưu bằng:

```powershell
terraform -chdir=terraform plan `
  -var="app_git_ref=$appGitRef" `
  -var="db_backup_retention_days=14"
```

Để tạo thêm snapshot hằng ngày trong AWS Backup vault riêng, bật plan tùy chọn.
Thời gian giữ mặc định là 35 ngày. Plan bắt đầu lúc 20:00 UTC, ngoài cửa sổ RDS
automated backup từ 18:00 đến 19:00 UTC.

```powershell
terraform -chdir=terraform plan `
  -var="app_git_ref=$appGitRef" `
  -var="enable_aws_backup=true" `
  -var="aws_backup_retention_days=35"
```

Dung lượng AWS Backup phát sinh chi phí. Vault đặt `force_destroy=false`, vì
vậy Terraform không thể âm thầm xóa các recovery point vẫn còn thời hạn lưu.

### Kiểm tra điểm khôi phục

Các lệnh sau chỉ đọc:

```powershell
aws rds describe-db-instance-automated-backups `
  --region ap-southeast-1 `
  --db-instance-identifier dev-cloudbox-mysql

aws backup list-recovery-points-by-backup-vault `
  --region ap-southeast-1 `
  --backup-vault-name dev-cloudbox-database-vault
```

Ghi lại recovery point thành công gần nhất, thời điểm tạo và lifecycle trong
bằng chứng kiểm thử của dự án.

### Thử nghiệm khôi phục tự động

Restore testing tạo RDS resource tạm thời nên phát sinh chi phí và mặc định bị
tắt. Chỉ bật cùng AWS Backup:

```powershell
terraform -chdir=terraform plan `
  -var="app_git_ref=$appGitRef" `
  -var="enable_aws_backup=true" `
  -var="enable_restore_testing=true"
```

Kiểm thử chạy hằng tuần, chọn snapshot mới nhất trong bảy ngày trước, khôi phục,
giữ cửa sổ xác minh một giờ rồi để AWS Backup dọn resource tạm. Không xóa tag
`awsbackup-restore-test` vì AWS dùng tag này trong quá trình dọn dẹp.

Xem kết quả bằng:

```powershell
aws backup list-restore-testing-plans --region ap-southeast-1
aws backup list-restore-jobs --region ap-southeast-1
```

Khi xử lý sự cố thật, khôi phục vào một RDS instance **mới**, kiểm tra schema và
số bản ghi, sau đó mới đổi DB endpoint qua một lần triển khai được xem xét. Không
ghi đè hoặc xóa database gốc trong lúc chẩn đoán.

## SQLite cục bộ

Công cụ sử dụng online backup API của SQLite, chạy `PRAGMA integrity_check`, in
checksum SHA-256 và từ chối ghi đè mọi file đích đã tồn tại.

```powershell
.venv\Scripts\python.exe scripts\database_backup.py backup
.venv\Scripts\python.exe scripts\database_backup.py verify backups\cloudbox-TIMESTAMP.db
.venv\Scripts\python.exe scripts\database_backup.py restore `
  backups\cloudbox-TIMESTAMP.db `
  --output recovered\database.db
```

Chạy một instance local để xác minh với `DATABASE_PATH` trỏ tới file đã khôi
phục. Chỉ thay `database.db` đang dùng sau khi kiểm tra ứng dụng đạt và đã giữ
thêm một bản sao của database gốc.
