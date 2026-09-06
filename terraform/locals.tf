locals {
  name_prefix   = "${var.environment}-cloudbox"
  https_enabled = var.certificate_arn != null
  bucket_name   = "${local.name_prefix}-${data.aws_caller_identity.current.account_id}-${var.aws_region}"
}
