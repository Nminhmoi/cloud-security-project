output "vpc_id" {
  value       = aws_vpc.main.id
  description = "VPC ID"
}

output "web_server_id" {
  value       = aws_instance.web.id
  description = "EC2 instance ID; connect through AWS Systems Manager Session Manager"
}

output "web_instance_profile_name" {
  value       = aws_iam_instance_profile.ec2.name
  description = "Instance profile attached to the CloudBox EC2 host"
}

output "web_iam_role_name" {
  value       = aws_iam_role.ec2.name
  description = "Least-privilege application role attached to the EC2 host"
}

output "web_iam_policy_name" {
  value       = aws_iam_role_policy.ec2_application.name
  description = "Inline application policy attached to the EC2 role"
}

output "application_url" {
  value       = "${local.https_enabled ? "https" : "http"}://${local.application_hostname}"
  description = "CloudBox load balancer URL"
}

output "load_balancer_arn" {
  value       = aws_lb.web.arn
  description = "Application Load Balancer ARN used by integration checks"
}

output "target_group_arn" {
  value       = aws_lb_target_group.web.arn
  description = "Application target group ARN used by integration checks"
}

output "rds_endpoint" {
  value       = aws_db_instance.mysql.address
  description = "Private RDS endpoint"
}

output "rds_instance_id" {
  value       = aws_db_instance.mysql.id
  description = "RDS instance identifier used by operations and integration checks"
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
  value       = local.https_enabled
  description = "Whether the ALB redirects HTTP to HTTPS"
}

output "tls_certificate_arn" {
  value       = local.effective_certificate_arn
  description = "ACM certificate attached to the ALB HTTPS listener"
}

output "custom_domain_name" {
  value       = var.domain_name
  description = "Optional custom DNS name routed to the CloudBox ALB"
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

output "application_log_group_name" {
  value       = aws_cloudwatch_log_group.application.name
  description = "CloudWatch Logs group receiving application container logs"
}

output "cloudwatch_alarm_names" {
  value = [
    aws_cloudwatch_metric_alarm.ec2_cpu.alarm_name,
    aws_cloudwatch_metric_alarm.rds_storage.alarm_name,
  ]
  description = "CloudWatch alarms validated by the AWS integration test"
}
