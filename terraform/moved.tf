# Giữ nguyên địa chỉ tài nguyên trong trạng thái từ bản Terraform đầu tiên. Một số
# tài nguyên vẫn cần được thay thế do thay đổi thuộc tính cấu hình bất biến;
# luôn xem lại kế hoạch đã lưu trước khi áp dụng.
moved {
  from = aws_vpc.main_vpc
  to   = aws_vpc.main
}

moved {
  from = aws_internet_gateway.igw
  to   = aws_internet_gateway.main
}

moved {
  from = aws_subnet.public_subnet
  to   = aws_subnet.public[0]
}

moved {
  from = aws_route_table.public_rt
  to   = aws_route_table.public
}

moved {
  from = aws_route_table_association.public_assoc
  to   = aws_route_table_association.public[0]
}

moved {
  from = aws_security_group.web_sg
  to   = aws_security_group.web
}

moved {
  from = aws_iam_role.ec2_ssm_role
  to   = aws_iam_role.ec2
}

moved {
  from = aws_iam_role_policy_attachment.ssm_policy_attach
  to   = aws_iam_role_policy_attachment.ssm
}

moved {
  from = aws_iam_instance_profile.ec2_profile
  to   = aws_iam_instance_profile.ec2
}

moved {
  from = aws_instance.web_server
  to   = aws_instance.web
}

moved {
  from = aws_s3_bucket.project_bucket
  to   = aws_s3_bucket.documents
}

moved {
  from = aws_s3_bucket_server_side_encryption_configuration.s3_encrypt
  to   = aws_s3_bucket_server_side_encryption_configuration.documents
}

moved {
  from = aws_s3_bucket_public_access_block.s3_public_block
  to   = aws_s3_bucket_public_access_block.documents
}
