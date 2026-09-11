# CloudBox AWS infrastructure

This root module creates a two-AZ VPC, an internet-facing ALB, one EC2
application host managed through SSM, private RDS MySQL, private versioned S3
document storage, Secrets Manager entries, VPC Flow Logs, and CloudWatch
alarms. EC2 port 5000 is reachable only from the ALB. The database is never
public.

The configuration is split by concern (`data.tf`, `locals.tf`, `network.tf`,
`security-groups.tf`, `database.tf`, `storage.tf`, `iam.tf`,
`load-balancer.tf`, `compute.tf`, and `observability.tf`) but remains one root
module. Moving a resource block between these files does not change its
Terraform address. EC2 bootstrap logic lives in
`templates/cloud-init.sh.tftpl` so it can be reviewed and tested separately.

## 1. Create the remote-state bucket once

The backend bucket must exist before `terraform init`. Choose a globally unique
name and create it outside this root module:

```bash
export TF_STATE_BUCKET="your-account-cloudbox-terraform-state"
export AWS_REGION="ap-southeast-1"

aws s3api create-bucket \
  --bucket "$TF_STATE_BUCKET" \
  --region "$AWS_REGION" \
  --create-bucket-configuration LocationConstraint="$AWS_REGION"
aws s3api put-public-access-block \
  --bucket "$TF_STATE_BUCKET" \
  --public-access-block-configuration \
  BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
aws s3api put-bucket-versioning \
  --bucket "$TF_STATE_BUCKET" \
  --versioning-configuration Status=Enabled
aws s3api put-bucket-encryption \
  --bucket "$TF_STATE_BUCKET" \
  --server-side-encryption-configuration \
  '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'
```

For `us-east-1`, omit `--create-bucket-configuration`.

## 2. Initialize and validate

Run from the `terraform` directory. Native S3 lockfiles protect concurrent
state updates; no DynamoDB table is required.

```bash
terraform init -migrate-state \
  -backend-config="bucket=$TF_STATE_BUCKET" \
  -backend-config="key=cloudbox/dev/terraform.tfstate" \
  -backend-config="region=$AWS_REGION"
terraform fmt -check
terraform validate
```

Commit `.terraform.lock.hcl`; never commit `.terraform/`, state, plan files, or
secret `.tfvars` files.

## 3. Plan a pinned application revision

Deploy an exact commit rather than a moving branch:

```bash
export APP_GIT_REF="$(git -C .. rev-parse HEAD)"
terraform plan -var="app_git_ref=$APP_GIT_REF" -out=tfplan
terraform apply tfplan
```

The referenced commit must already exist on GitHub because EC2 checks it out
during cloud-init. Existing deployments use the state address migrations in
`moved.tf`, but EC2 and the original S3 bucket may still require replacement
because immutable settings changed. Inspect the saved plan carefully and copy
any existing bucket objects before approving a replacement.

For HTTPS with an existing certificate in the same region, add:

```bash
-var="domain_name=cloudbox.example.com" \
-var="certificate_arn=arn:aws:acm:REGION:ACCOUNT:certificate/ID"
```

When neither an existing certificate nor managed domain settings are supplied,
the ALB exposes HTTP for development and the output `https_enabled` is false.
Do not treat that mode as production-ready.

Alternatively, Terraform can request and DNS-validate a certificate, create the
Route 53 alias, and return the custom HTTPS URL:

```bash
-var="domain_name=cloudbox.example.com" \
-var="route53_zone_id=Z1234567890"
```

The hosted zone must be public and the domain must be under your control. See
`../docs/HTTPS_DEPLOYMENT.md` for prerequisites and the post-deployment smoke
test.

For production also set:

```bash
-var="db_multi_az=true" \
-var="deletion_protection=true" \
-var="alarm_email=operator@example.com"
```

The SNS email subscription must be confirmed before alarms can deliver mail.

Password-reset OTP uses Amazon SES when a verified sender is configured:

```bash
-var="ses_sender_email=owner@example.com"
```

Terraform creates the email identity, but its verification email must be
confirmed. SES sandbox accounts can send only to verified recipients. Without
this variable, OTP delivery on AWS is disabled and the OTP is never written to
application logs.

RDS automated point-in-time recovery retains seven days by default. Optional
AWS Backup and weekly restore testing are explicitly opt-in because they create
billable backup storage or temporary restore resources:

```bash
-var="db_backup_retention_days=14" \
-var="enable_aws_backup=true" \
-var="aws_backup_retention_days=35" \
-var="enable_restore_testing=true"
```

See `../docs/BACKUP_AND_RECOVERY.md` and `../docs/SES_OTP.md` for verification and
recovery procedures.

## 4. Operations

Use `terraform output application_url` to find the public entry point. Connect
to the EC2 host with AWS Systems Manager Session Manager; SSH is intentionally
not exposed. Bootstrap diagnostics are available in
`/var/log/cloud-init-output.log`, and application container logs are sent to
the CloudWatch log group output by this configuration.
