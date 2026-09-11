# HTTPS deployment

CloudBox supports an existing ACM certificate or a Terraform-managed ACM
certificate with Route 53 DNS validation. HTTP-only mode remains available for
temporary development environments but is not production-ready.

## Prerequisites

You need a public domain you control. AWS cannot issue a public ACM certificate
for the default `*.elb.amazonaws.com` load-balancer name. For the fully managed
path, the domain's public hosted zone must be in Route 53 in the same AWS
account.

Find the hosted zone ID:

```powershell
aws route53 list-hosted-zones-by-name --dns-name example.com
```

## Terraform-managed certificate and DNS

Commit and push the application before planning:

```powershell
$appGitRef = (git rev-parse HEAD).Trim()
terraform -chdir=terraform plan `
  -var="app_git_ref=$appGitRef" `
  -var="domain_name=cloudbox.example.com" `
  -var="route53_zone_id=Z1234567890" `
  -out=tfplan
```

Terraform requests an ACM certificate, writes the validation CNAME, waits for
issuance, creates an alias to the ALB, enables the TLS 1.2/1.3 listener and
changes port 80 to an HTTPS redirect. ACM can renew the certificate while its
DNS validation record remains present.

## Existing certificate

If a certificate and DNS record are managed elsewhere, pass its ARN:

```powershell
terraform -chdir=terraform plan `
  -var="app_git_ref=$appGitRef" `
  -var="domain_name=cloudbox.example.com" `
  -var="certificate_arn=arn:aws:acm:ap-southeast-1:ACCOUNT:certificate/ID"
```

The certificate must be in the same Region as the ALB and must cover the custom
hostname. Configure the external DNS provider to point that hostname to the ALB.

## Verification

After apply and target health recovery:

```powershell
terraform -chdir=terraform output application_url
.venv\Scripts\python.exe scripts\smoke_test_deployment.py `
  https://cloudbox.example.com
```

The smoke test is read-only. It verifies trusted certificate validation, TLS
1.2/1.3, at least 14 days before certificate expiry, the HTTP-to-HTTPS redirect,
HSTS/CSP and other security headers, a `Secure`/`HttpOnly`/`SameSite` session
cookie, and the CSRF endpoint.

Also confirm plain HTTP redirects:

```powershell
curl.exe -I http://cloudbox.example.com
```

Expected: `HTTP/1.1 301` with a `Location` beginning with `https://`.
