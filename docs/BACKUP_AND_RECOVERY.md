# Backup and recovery

CloudBox uses separate recovery controls for local SQLite and Amazon RDS. A
backup is only considered useful after its integrity or restore path has been
tested.

## Amazon RDS

RDS automated backups and point-in-time recovery are enabled for seven days by
default. Terraform also retains automated backups when the managed DB instance
is deleted. Change the retention window with:

```powershell
terraform -chdir=terraform plan `
  -var="app_git_ref=$appGitRef" `
  -var="db_backup_retention_days=14"
```

For an additional daily snapshot retained in a dedicated AWS Backup vault,
enable the optional plan. Its default retention is 35 days. The plan starts at
20:00 UTC, outside the RDS automated backup window of 18:00-19:00 UTC.

```powershell
terraform -chdir=terraform plan `
  -var="app_git_ref=$appGitRef" `
  -var="enable_aws_backup=true" `
  -var="aws_backup_retention_days=35"
```

AWS Backup storage is billable. The vault has `force_destroy=false`, so
Terraform cannot silently delete recovery points still retained in it.

### Verify recovery points

These commands are read-only:

```powershell
aws rds describe-db-instance-automated-backups `
  --region ap-southeast-1 `
  --db-instance-identifier dev-cloudbox-mysql

aws backup list-recovery-points-by-backup-vault `
  --region ap-southeast-1 `
  --backup-vault-name dev-cloudbox-database-vault
```

Record the latest successful recovery point, creation time and lifecycle in the
project test evidence.

### Automated restore drill

Restore testing creates a temporary RDS resource and therefore costs money. It
is disabled by default. Enable it only together with AWS Backup:

```powershell
terraform -chdir=terraform plan `
  -var="app_git_ref=$appGitRef" `
  -var="enable_aws_backup=true" `
  -var="enable_restore_testing=true"
```

The test runs weekly, selects the latest snapshot from the previous seven days,
restores it, keeps a one-hour validation window and lets AWS Backup clean up the
temporary resource. Never remove the `awsbackup-restore-test` tag from a test
resource because AWS uses it during cleanup.

Inspect results with:

```powershell
aws backup list-restore-testing-plans --region ap-southeast-1
aws backup list-restore-jobs --region ap-southeast-1
```

Before a real incident cutover, restore into a **new** RDS instance, validate
schema and row counts, then change the application DB endpoint in a reviewed
deployment. Do not overwrite or delete the original database during diagnosis.

## Local SQLite

The helper uses SQLite's online backup API, runs `PRAGMA integrity_check`, prints
a SHA-256 checksum and refuses to overwrite any destination.

```powershell
.venv\Scripts\python.exe scripts\database_backup.py backup
.venv\Scripts\python.exe scripts\database_backup.py verify backups\cloudbox-TIMESTAMP.db
.venv\Scripts\python.exe scripts\database_backup.py restore `
  backups\cloudbox-TIMESTAMP.db `
  --output recovered\database.db
```

Start a local validation instance with `DATABASE_PATH` pointing to the restored
file. Replace the active `database.db` only after application checks pass and a
second copy of the original has been retained.
