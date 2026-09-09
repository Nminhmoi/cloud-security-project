# Security audit utilities

This directory contains project checks and policy examples. The deployed AWS
configuration remains defined by `terraform/`; JSON files in `policies/` are
reviewable examples and are not attached to AWS resources automatically.

Run every security test from the repository root:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s security -t . -v
```

Lint all IAM policy examples:

```powershell
.\.venv\Scripts\python.exe -m security.iam.iam_validator
```

Audit a local SQLite database without modifying it:

```powershell
.\.venv\Scripts\python.exe -m security.iam.user_evaluator --db database.db
.\.venv\Scripts\python.exe -m security.monitoring.security_monitoring --db database.db
```

For RDS, set `DATABASE_URL` or pass `--database-url`. Do not place credentials
in shell history or commit them to the repository.

The monitor is a point-in-time database audit. It returns `INCOMPLETE` until
the application records failed-login telemetry. The custom failed-login alarm
JSON is also only a configuration example until the application publishes its
metric and Terraform creates the corresponding CloudWatch alarm.

The IAM validator enforces this project's local rules. It does not prove that
a policy is safe and does not replace AWS IAM Access Analyzer.
