output "vpc_id" {
  value       = aws_vpc.main_vpc.id
  description = "VPC ID"
}

output "web_server_id" {
  value       = aws_instance.web_server.id
  description = "EC2 Instance ID"
}

output "web_server_public_ip" {
  value       = aws_instance.web_server.public_ip
  description = "Web Server Public IP"
}

output "s3_bucket_name" {
  value       = aws_s3_bucket.project_bucket.id
  description = "S3 Bucket Name"
}