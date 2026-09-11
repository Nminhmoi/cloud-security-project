locals {
  name_prefix               = "${var.environment}-cloudbox"
  managed_certificate       = var.certificate_arn == null && var.domain_name != null && var.route53_zone_id != null
  route53_alias_enabled     = var.domain_name != null && var.route53_zone_id != null
  effective_certificate_arn = var.certificate_arn != null ? var.certificate_arn : (local.managed_certificate ? aws_acm_certificate_validation.web[0].certificate_arn : null)
  https_enabled             = var.certificate_arn != null || local.managed_certificate
  application_hostname      = var.domain_name != null ? var.domain_name : aws_lb.web.dns_name
  ses_enabled               = var.ses_sender_email != null
  bucket_name               = "${local.name_prefix}-${data.aws_caller_identity.current.account_id}-${var.aws_region}"
}
