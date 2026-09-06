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

variable "db_instance_class" {
  type        = string
  default     = "db.t3.micro"
  description = "RDS MySQL instance class"
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
