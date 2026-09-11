# Password-reset OTP with Amazon SES

Local development can use `OTP_DELIVERY_MODE=local`. AWS deployments never log
OTP values: delivery is `ses` when `ses_sender_email` is configured, otherwise
it is `disabled` and password reset fails closed with the same browser flow.

## Provision and verify the sender

Pass an address that you control when planning Terraform:

```powershell
$appGitRef = (git rev-parse HEAD).Trim()
terraform -chdir=terraform plan `
  -var="app_git_ref=$appGitRef" `
  -var="ses_sender_email=owner@example.com" `
  -out=tfplan
```

Applying creates an SES email identity in `ap-southeast-1`. Open the verification
email sent by AWS before testing OTP delivery. Confirm its status with:

```powershell
aws ses get-identity-verification-attributes `
  --region ap-southeast-1 `
  --identities owner@example.com
```

The EC2 instance role can send only from the Terraform-managed identity. Boto3
uses the instance profile's temporary credentials; no AWS access key is stored
in `.env` or the container.

## SES sandbox

While the AWS account is in the SES sandbox, recipients must also be verified
unless a mailbox-simulator address is used. For real users, request production
access from the SES console and keep sending enabled only in the intended AWS
Region.

## Smoke test

1. Verify the sender identity and, in sandbox, the recipient identity.
2. Open `/forgot-password` through the ALB.
3. Submit the registered recipient email.
4. Confirm an OTP email arrives and expires after two minutes.
5. Enter an invalid OTP three times and confirm the code is revoked.
6. Complete a valid reset and confirm old sessions no longer work.

Do not paste OTP values into issue trackers, screenshots, CloudWatch logs or the
project report.
