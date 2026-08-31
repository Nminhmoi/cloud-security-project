output "vpc_id" {
  value = aws_vpc.main_vpc.id
}

output "web_server_id" {
  value = aws_instance.web_server.id
}

output "web_server_public_ip" {
  value = aws_instance.web_server.public_ip
}