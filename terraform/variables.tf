variable "aws_region" {
  type        = string
  default     = "ap-southeast-1"
  description = "AWS Region"
}

variable "environment" {
  type        = string
  default     = "dev"
  description = "Environment name"

  validation {
    condition     = can(regex("^[a-z0-9-]{2,16}$", var.environment))
    error_message = "environment must contain 2-16 lowercase letters, digits, or hyphens."
  }
}

variable "vpc_cidr" {
  type        = string
  default     = "10.0.0.0/16"
  description = "VPC CIDR block"

  validation {
    condition     = can(cidrnetmask(var.vpc_cidr))
    error_message = "vpc_cidr must be a valid IPv4 CIDR block."
  }
}

variable "public_subnet_cidrs" {
  type        = list(string)
  default     = ["10.0.1.0/24", "10.0.2.0/24"]
  description = "Two public subnet CIDRs in separate Availability Zones"

  validation {
    condition     = length(var.public_subnet_cidrs) >= 2 && alltrue([for cidr in var.public_subnet_cidrs : can(cidrnetmask(cidr))])
    error_message = "Provide at least two valid public subnet CIDRs."
  }
}

variable "private_db_subnet_cidrs" {
  type        = list(string)
  default     = ["10.0.11.0/24", "10.0.12.0/24"]
  description = "Two private database subnet CIDRs in separate Availability Zones"

  validation {
    condition     = length(var.private_db_subnet_cidrs) >= 2 && alltrue([for cidr in var.private_db_subnet_cidrs : can(cidrnetmask(cidr))])
    error_message = "Provide at least two valid private database subnet CIDRs."
  }
}

variable "instance_type" {
  type        = string
  default     = "t3.small"
  description = "EC2 instance type"
}

variable "app_git_ref" {
  type        = string
  description = "Exact 40-character Git commit SHA deployed to EC2"

  validation {
    condition     = can(regex("^[0-9a-f]{40}$", var.app_git_ref))
    error_message = "app_git_ref must be an exact 40-character lowercase Git commit SHA."
  }
}

variable "certificate_arn" {
  type        = string
  default     = null
  nullable    = true
  description = "ACM certificate ARN for HTTPS. Null keeps an HTTP-only dev listener."

  validation {
    condition     = var.certificate_arn == null || can(regex("^arn:aws:acm:", var.certificate_arn))
    error_message = "certificate_arn must be null or a valid ACM certificate ARN."
  }
}

variable "domain_name" {
  type        = string
  default     = null
  nullable    = true
  description = "Optional public FQDN for CloudBox, for example cloudbox.example.com"

  validation {
    condition     = var.domain_name == null || can(regex("^(?=.{1,253}$)([a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\\.)+[a-zA-Z]{2,63}$", var.domain_name))
    error_message = "domain_name must be null or a valid fully qualified domain name."
  }

  validation {
    condition = (
      var.domain_name == null && var.route53_zone_id == null && var.certificate_arn == null
      ) || (
      var.domain_name != null && (var.certificate_arn != null || var.route53_zone_id != null)
    )
    error_message = "HTTPS requires domain_name plus certificate_arn or route53_zone_id; TLS cannot use the default ALB hostname."
  }
}

variable "route53_zone_id" {
  type        = string
  default     = null
  nullable    = true
  description = "Optional public Route 53 hosted zone ID used for ACM validation and the ALB alias"
}

variable "db_instance_class" {
  type        = string
  default     = "db.t3.micro"
  description = "RDS MySQL instance class"
}

variable "db_backup_retention_days" {
  type        = number
  default     = 7
  description = "Number of days RDS automated backups and point-in-time recovery are retained"

  validation {
    condition     = var.db_backup_retention_days >= 1 && var.db_backup_retention_days <= 35
    error_message = "db_backup_retention_days must be between 1 and 35."
  }
}

variable "enable_aws_backup" {
  type        = bool
  default     = false
  description = "Create an additional daily AWS Backup snapshot plan for RDS; this incurs backup storage charges"
}

variable "aws_backup_retention_days" {
  type        = number
  default     = 35
  description = "Retention period for RDS recovery points stored in the AWS Backup vault"

  validation {
    condition     = var.aws_backup_retention_days >= 7 && var.aws_backup_retention_days <= 3650
    error_message = "aws_backup_retention_days must be between 7 and 3650."
  }
}

variable "enable_restore_testing" {
  type        = bool
  default     = false
  description = "Run a weekly AWS Backup RDS restore test; this creates temporary billable resources"

  validation {
    condition     = !var.enable_restore_testing || var.enable_aws_backup
    error_message = "enable_restore_testing requires enable_aws_backup=true."
  }
}

variable "ses_sender_email" {
  type        = string
  default     = null
  nullable    = true
  description = "Email identity used by Amazon SES for password-reset OTP; null disables OTP delivery on AWS"

  validation {
    condition     = var.ses_sender_email == null || can(regex("^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$", var.ses_sender_email))
    error_message = "ses_sender_email must be null or a valid email address."
  }
}

variable "db_multi_az" {
  type        = bool
  default     = false
  description = "Enable Multi-AZ for RDS; recommended for production"
}

variable "deletion_protection" {
  type        = bool
  default     = false
  description = "Protect RDS from accidental deletion"
}

variable "force_destroy_bucket" {
  type        = bool
  default     = false
  description = "Allow deletion of a non-empty document bucket only in disposable dev environments"
}

variable "alarm_email" {
  type        = string
  default     = null
  nullable    = true
  description = "Optional email address for CloudWatch alarm notifications"

  validation {
    condition     = var.alarm_email == null || can(regex("^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$", var.alarm_email))
    error_message = "alarm_email must be null or a valid email address."
  }
}
