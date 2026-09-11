output "vpc_id" {
  value       = aws_vpc.main.id
  description = "VPC ID"
}

output "web_server_id" {
  value       = aws_instance.web.id
  description = "EC2 instance ID; connect through AWS Systems Manager Session Manager"
}

output "application_url" {
  value       = "${var.certificate_arn == null ? "http" : "https"}://${aws_lb.web.dns_name}"
  description = "CloudBox load balancer URL"
}

output "rds_endpoint" {
  value       = aws_db_instance.mysql.address
  description = "Private RDS endpoint"
}

output "rds_master_secret_arn" {
  value       = aws_db_instance.mysql.master_user_secret[0].secret_arn
  description = "Secrets Manager ARN containing the RDS-generated master credentials"
}

output "s3_bucket_name" {
  value       = aws_s3_bucket.documents.id
  description = "Private versioned S3 document bucket"
}

output "https_enabled" {
  value       = var.certificate_arn != null
  description = "Whether the ALB redirects HTTP to HTTPS"
}

output "rds_automated_backup_retention_days" {
  value       = aws_db_instance.mysql.backup_retention_period
  description = "RDS point-in-time recovery retention period"
}

output "aws_backup_vault_name" {
  value       = var.enable_aws_backup ? aws_backup_vault.database[0].name : null
  description = "Optional AWS Backup vault containing additional RDS recovery points"
}

output "restore_testing_enabled" {
  value       = var.enable_restore_testing
  description = "Whether weekly automated RDS restore testing is enabled"
}

output "otp_delivery_mode" {
  value       = local.ses_enabled ? "ses" : "disabled"
  description = "Password-reset OTP delivery mode on AWS"
}
