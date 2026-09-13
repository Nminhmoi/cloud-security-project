# CI/CD and security gates

CloudBox uses two GitHub Actions workflows:

- `.github/workflows/ci.yml` runs on pull requests and pushes to `main`.
- `.github/workflows/deploy.yml` runs only through an explicit manual dispatch.

All third-party actions are pinned to full commit SHAs. Dependabot checks those
pins and the Python, Docker, and Terraform dependencies every week.

## Continuous integration

The CI workflow has four required jobs:

1. `Python tests` compiles the source and runs the application and security
   unit tests on Python 3.12, matching the Docker image.
2. `Python security` runs `pip-audit` against runtime dependencies and Bandit
   against application scripts. High-severity Bandit findings fail the job.
3. `Terraform` checks formatting and validates the root module without
   connecting to its remote backend or AWS account.
4. `Container and IaC security` uses Trivy to detect committed secrets,
   infrastructure misconfiguration, and high/critical fixed vulnerabilities
   in the built application image.

The runtime image pins the Python base-image digest, installs current Debian
security updates during the build, and removes Python packaging tools after
application dependencies are installed. Dependabot proposes base-image digest
updates so those changes remain explicit and reviewable.

Trivy exceptions are kept in `.trivyignore.yaml`. Every exception is limited
to one file and includes its reason. The current exceptions document deliberate
development-only choices: the user-facing ALB is public, HTTP remains available
until a domain and ACM certificate are configured, bootstrap traffic is limited
to outbound TCP 80/443, and S3 uses the no-additional-cost SSE-S3 option. Review
these exceptions before treating the environment as production.

Configure the `main` branch protection rule to require all four jobs before a
pull request can merge. CI receives only `contents: read`; it has no AWS token
permission and no deployment secrets.

To run the Python gates locally:

```powershell
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.venv\Scripts\python.exe -m unittest discover -s tests -v
.venv\Scripts\python.exe -m unittest discover -s security -p "test_*.py" -v
.venv\Scripts\python.exe -m pip_audit -r app\requirements.txt --strict --progress-spinner off
.venv\Scripts\python.exe -m bandit -r app scripts security `
  -x security/iam/test_iam.py,security/monitoring/test_monitoring.py `
  --severity-level high
trivy fs --scanners secret,misconfig --severity HIGH,CRITICAL `
  --ignorefile .trivyignore.yaml --skip-dirs .venv .
```

## Controlled AWS deployment

The deployment workflow uses GitHub OIDC to obtain short-lived AWS
credentials. Do not add `AWS_ACCESS_KEY_ID` or `AWS_SECRET_ACCESS_KEY` as
repository secrets.

Create a GitHub environment named `cloudbox-dev` and configure:

| Type | Name | Example or purpose |
| --- | --- | --- |
| Variable | `AWS_REGION` | `ap-southeast-1` |
| Variable | `AWS_ACCOUNT_ID` | Expected 12-digit AWS account ID |
| Variable | `AWS_ROLE_ARN` | OIDC deployment role ARN |
| Variable | `TF_STATE_BUCKET` | Existing private Terraform state bucket |
| Variable | `TF_STATE_KEY` | `cloudbox/dev/terraform.tfstate` |
| Secret | `TF_VARS_JSON` | Optional JSON object containing non-default Terraform variables |

Do not put `app_git_ref` in `TF_VARS_JSON`; the workflow always pins it to the
selected GitHub commit. A development value could be:

```json
{
  "environment": "dev",
  "instance_type": "t3.micro",
  "db_instance_class": "db.t3.micro",
  "deletion_protection": false
}
```

Require reviewers for the `cloudbox-dev` environment and restrict its
deployment branch to `main`. The workflow also rejects `apply=true` outside
`refs/heads/main`.

## AWS OIDC trust

Create the GitHub OIDC provider for `https://token.actions.githubusercontent.com`
with audience `sts.amazonaws.com`, then give the deployment role a trust policy
restricted to this repository and protected environment:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::ACCOUNT_ID:oidc-provider/token.actions.githubusercontent.com"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
          "token.actions.githubusercontent.com:sub": "repo:OWNER/REPOSITORY:environment:cloudbox-dev"
        }
      }
    }
  ]
}
```

Attach a deployment policy limited to the AWS services and resources managed
by this Terraform module. Avoid `AdministratorAccess`; keep this deployment
role separate from the much smaller EC2 application role.

## Running CD

Open **Actions → Deploy CloudBox to AWS → Run workflow**:

- Leave `apply` disabled to obtain a Terraform plan only.
- Enable `apply` only after reviewing the plan and expected cost.

An apply waits for the ALB target, runs the read-only AWS integration test, and
then runs the public endpoint smoke test. It never stores the Terraform plan as
an artifact because plan files can contain secret-derived values.
