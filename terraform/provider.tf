provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Application = "cloudbox"
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}
