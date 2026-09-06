terraform {
  # Supply bucket, key, and region during init so backend infrastructure can
  # be created separately and no account-specific values are committed.
  backend "s3" {
    encrypt      = true
    use_lockfile = true
  }
}
