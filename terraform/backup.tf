# --- Optional long-retention RDS backups and restore testing ---
data "aws_iam_policy_document" "backup_assume" {
  count = var.enable_aws_backup ? 1 : 0

  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["backup.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "backup" {
  count = var.enable_aws_backup ? 1 : 0

  name               = "${local.name_prefix}-backup-role"
  assume_role_policy = data.aws_iam_policy_document.backup_assume[0].json
}

resource "aws_iam_role_policy_attachment" "backup" {
  count = var.enable_aws_backup ? 1 : 0

  role       = aws_iam_role.backup[0].name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSBackupServiceRolePolicyForBackup"
}

resource "aws_iam_role_policy_attachment" "restore" {
  count = var.enable_restore_testing ? 1 : 0

  role       = aws_iam_role.backup[0].name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSBackupServiceRolePolicyForRestores"
}

resource "aws_backup_vault" "database" {
  count = var.enable_aws_backup ? 1 : 0

  name          = "${local.name_prefix}-database-vault"
  force_destroy = false
}

resource "aws_backup_plan" "database" {
  count = var.enable_aws_backup ? 1 : 0

  name = "${local.name_prefix}-database-daily"

  rule {
    rule_name         = "daily-rds-snapshot"
    target_vault_name = aws_backup_vault.database[0].name
    schedule          = "cron(0 20 * * ? *)"
    start_window      = 60
    completion_window = 180

    lifecycle {
      delete_after = var.aws_backup_retention_days
    }
  }
}

resource "aws_backup_selection" "database" {
  count = var.enable_aws_backup ? 1 : 0

  name         = "${local.name_prefix}-rds"
  plan_id      = aws_backup_plan.database[0].id
  iam_role_arn = aws_iam_role.backup[0].arn
  resources    = [aws_db_instance.mysql.arn]

  depends_on = [aws_iam_role_policy_attachment.backup]
}

resource "aws_backup_restore_testing_plan" "database" {
  count = var.enable_restore_testing ? 1 : 0

  name                = "${replace(local.name_prefix, "-", "_")}_rds_restore_test"
  schedule_expression = "cron(0 3 ? * SUN *)"
  start_window_hours  = 1

  recovery_point_selection {
    algorithm             = "LATEST_WITHIN_WINDOW"
    include_vaults        = [aws_backup_vault.database[0].arn]
    recovery_point_types  = ["SNAPSHOT"]
    selection_window_days = 7
  }
}

resource "aws_backup_restore_testing_selection" "database" {
  count = var.enable_restore_testing ? 1 : 0

  name                      = "cloudbox_rds"
  restore_testing_plan_name = aws_backup_restore_testing_plan.database[0].name
  protected_resource_type   = "RDS"
  protected_resource_arns   = [aws_db_instance.mysql.arn]
  iam_role_arn              = aws_iam_role.backup[0].arn
  validation_window_hours   = 1

  depends_on = [aws_iam_role_policy_attachment.restore]
}
