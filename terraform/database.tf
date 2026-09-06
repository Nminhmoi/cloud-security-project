# --- Secrets and RDS ---
resource "aws_secretsmanager_secret" "app" {
  name                    = "${local.name_prefix}/flask-secret-key"
  recovery_window_in_days = 7
  tags                    = { Name = "${local.name_prefix}-app-secret" }
}

resource "aws_db_subnet_group" "main" {
  name       = "${local.name_prefix}-db-subnets"
  subnet_ids = aws_subnet.database[*].id
  tags       = { Name = "${local.name_prefix}-db-subnets" }
}

resource "aws_db_parameter_group" "mysql" {
  name   = "${local.name_prefix}-mysql84"
  family = "mysql8.4"

  parameter {
    name  = "require_secure_transport"
    value = "ON"
  }

  tags = { Name = "${local.name_prefix}-mysql84" }
}

resource "aws_db_instance" "mysql" {
  identifier = "${local.name_prefix}-mysql"

  engine                      = "mysql"
  engine_version              = "8.4"
  instance_class              = var.db_instance_class
  allocated_storage           = 20
  max_allocated_storage       = 100
  storage_type                = "gp3"
  storage_encrypted           = true
  db_name                     = "cloudbox"
  username                    = "cloudboxadmin"
  manage_master_user_password = true
  port                        = 3306
  publicly_accessible         = false
  multi_az                    = var.db_multi_az
  db_subnet_group_name        = aws_db_subnet_group.main.name
  parameter_group_name        = aws_db_parameter_group.mysql.name
  vpc_security_group_ids      = [aws_security_group.database.id]
  backup_retention_period     = 7
  backup_window               = "18:00-19:00"
  maintenance_window          = "sun:19:00-sun:20:00"
  auto_minor_version_upgrade  = true
  copy_tags_to_snapshot       = true
  deletion_protection         = var.deletion_protection
  skip_final_snapshot         = !var.deletion_protection
  final_snapshot_identifier   = "${local.name_prefix}-mysql-final"

  tags = { Name = "${local.name_prefix}-mysql" }
}
