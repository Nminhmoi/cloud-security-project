# AWS integration testing

CloudBox includes two complementary post-deployment tests:

- `scripts/aws_integration_test.py` checks the deployed AWS control plane.
- `scripts/smoke_test_deployment.py` checks the public HTTP/HTTPS behavior.

The AWS test is read-only. It does not upload an object, send an OTP, create a
snapshot, or otherwise mutate AWS resources. It validates:

- the active AWS account and principal;
- EC2 running state, required IMDSv2 tokens, instance profile, and SSM status;
- private encrypted RDS, automated backup retention, and endpoint identity;
- private, encrypted, versioned S3 storage in the expected region;
- ALB listeners and healthy EC2 target registration;
- the EC2 IAM profile, SSM policy, and absence of an unrestricted `Allow */*`
  statement in the application policy;
- RDS Secrets Manager metadata without reading the secret value;
- application log retention, CloudWatch alarms, and active VPC Flow Logs.

## Prerequisites

Apply the current Terraform code once so the integration-specific outputs are
stored in state. Then authenticate the AWS CLI with a read-capable deployment
operator identity:

```powershell
aws sts get-caller-identity
terraform -chdir=terraform output
```

The operator needs read actions for STS, EC2, SSM, RDS, S3 bucket
configuration, ELBv2, IAM, Secrets Manager metadata, CloudWatch Logs, and
CloudWatch alarms. The test never calls `secretsmanager:GetSecretValue`.

## Run the test

From the repository root:

```powershell
.venv\Scripts\python.exe scripts\aws_integration_test.py `
  --region ap-southeast-1
```

For a named AWS profile:

```powershell
.venv\Scripts\python.exe scripts\aws_integration_test.py `
  --profile cloudbox-dev `
  --region ap-southeast-1
```

Run the public endpoint smoke test immediately afterwards:

```powershell
$applicationUrl = terraform -chdir=terraform output -raw application_url
.venv\Scripts\python.exe scripts\smoke_test_deployment.py $applicationUrl --allow-http
```

Remove `--allow-http` once HTTPS is configured. A production acceptance run
must use HTTPS and must not pass that flag.

Use `--json` for CI or archived evidence. An output snapshot can also be
captured and tested with `--outputs-file`, but Terraform output JSON can reveal
infrastructure identifiers and should not be committed:

```powershell
terraform -chdir=terraform output -json | Out-File tf-output.json -Encoding utf8
.venv\Scripts\python.exe scripts\aws_integration_test.py `
  --outputs-file tf-output.json `
  --region ap-southeast-1 `
  --json
Remove-Item -LiteralPath tf-output.json
```

The command exits with status `1` if any invariant fails, making it suitable
for a protected deployment job once CI uses short-lived AWS credentials.
