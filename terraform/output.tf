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
