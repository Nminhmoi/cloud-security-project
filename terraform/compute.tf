# --- EC2 application host ---
data "aws_ami" "ubuntu" {
  most_recent = true

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-*"]
  }
  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
  owners = ["099720109477"]
}

resource "aws_instance" "web" {
  ami                         = data.aws_ami.ubuntu.id
  instance_type               = var.instance_type
  subnet_id                   = aws_subnet.public[0].id
  associate_public_ip_address = true
  vpc_security_group_ids      = [aws_security_group.web.id]
  iam_instance_profile        = aws_iam_instance_profile.ec2.name

  user_data_replace_on_change = true
  user_data = templatefile("${path.module}/templates/cloud-init.sh.tftpl", {
    app_git_ref           = var.app_git_ref
    app_secret_arn        = aws_secretsmanager_secret.app.arn
    aws_region            = var.aws_region
    document_bucket       = aws_s3_bucket.documents.id
    https_enabled         = local.https_enabled
    application_log_group = aws_cloudwatch_log_group.application.name
    rds_host              = aws_db_instance.mysql.address
    rds_port              = aws_db_instance.mysql.port
    rds_secret_arn        = aws_db_instance.mysql.master_user_secret[0].secret_arn
    otp_delivery_mode     = local.ses_enabled ? "ses" : "disabled"
    ses_sender_email      = coalesce(var.ses_sender_email, "")
  })

  metadata_options {
    http_endpoint = "enabled"
    http_tokens   = "required"
    # Containers need one additional network hop to obtain temporary role
    # credentials from IMDSv2. No static AWS keys are injected into containers.
    http_put_response_hop_limit = 2
  }

  root_block_device {
    encrypted             = true
    volume_type           = "gp3"
    volume_size           = 20
    delete_on_termination = true
  }

  depends_on = [
    aws_iam_role_policy_attachment.ssm,
    aws_iam_role_policy.ec2_application,
    aws_s3_bucket_policy.documents,
  ]

  tags = { Name = "${local.name_prefix}-web" }
}
