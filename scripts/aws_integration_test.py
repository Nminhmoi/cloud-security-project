"""Read-only AWS control-plane integration test for a CloudBox deployment."""

import argparse
import json
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import urlparse

import boto3
from botocore.exceptions import BotoCoreError, ClientError


class AwsIntegrationError(RuntimeError):
    """Raised when an AWS integration invariant is not satisfied."""


@dataclass(frozen=True)
class CheckResult:
    name: str
    passed: bool
    detail: str


def _require(condition, message):
    if not condition:
        raise AwsIntegrationError(message)


def _contains_wildcard(value):
    values = value if isinstance(value, list) else [value]
    return "*" in values


def normalize_terraform_outputs(payload):
    """Accept `terraform output -json` data or a direct name/value mapping."""
    if not isinstance(payload, dict):
        raise AwsIntegrationError("Terraform outputs must be a JSON object")
    return {
        name: value["value"]
        if isinstance(value, dict) and "value" in value
        else value
        for name, value in payload.items()
    }


def load_terraform_outputs(terraform_dir):
    directory = Path(terraform_dir).resolve()
    try:
        result = subprocess.run(
            ["terraform", f"-chdir={directory}", "output", "-json"],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as error:
        raise AwsIntegrationError(f"Cannot execute Terraform: {error}") from error
    if result.returncode:
        message = result.stderr.strip() or result.stdout.strip()
        raise AwsIntegrationError(f"Cannot read Terraform outputs: {message}")
    try:
        return normalize_terraform_outputs(json.loads(result.stdout))
    except json.JSONDecodeError as error:
        raise AwsIntegrationError("Terraform returned invalid output JSON") from error


def load_outputs_file(filename):
    try:
        payload = json.loads(Path(filename).read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as error:
        raise AwsIntegrationError(f"Cannot read outputs file: {error}") from error
    return normalize_terraform_outputs(payload)


class AwsIntegrationChecker:
    """Validate deployed resources without changing AWS state."""

    REQUIRED_OUTPUTS = {
        "application_log_group_name",
        "application_url",
        "cloudwatch_alarm_names",
        "https_enabled",
        "load_balancer_arn",
        "rds_endpoint",
        "rds_instance_id",
        "rds_master_secret_arn",
        "s3_bucket_name",
        "target_group_arn",
        "vpc_id",
        "web_iam_policy_name",
        "web_iam_role_name",
        "web_instance_profile_name",
        "web_server_id",
    }

    def __init__(self, outputs, session=None, clients=None):
        self.outputs = outputs
        self.session = session
        self.clients = clients or {}

    def client(self, service):
        if service not in self.clients:
            if self.session is None:
                raise AwsIntegrationError(f"No AWS client configured for {service}")
            self.clients[service] = self.session.client(service)
        return self.clients[service]

    def check_outputs(self):
        missing = sorted(
            name
            for name in self.REQUIRED_OUTPUTS
            if self.outputs.get(name) in (None, "", [])
        )
        _require(not missing, "Missing Terraform outputs: " + ", ".join(missing))
        application_url = urlparse(self.outputs["application_url"])
        _require(application_url.hostname, "Application URL has no hostname")
        expected_scheme = "https" if self.outputs["https_enabled"] else "http"
        _require(
            application_url.scheme == expected_scheme,
            f"Application URL must use {expected_scheme}",
        )
        return f"{len(self.REQUIRED_OUTPUTS)} required outputs are present"

    def check_identity(self):
        identity = self.client("sts").get_caller_identity()
        account = identity.get("Account")
        arn = identity.get("Arn")
        _require(account and arn, "STS did not return an account and ARN")
        resource_arns = (
            self.outputs["load_balancer_arn"],
            self.outputs["rds_master_secret_arn"],
            self.outputs["target_group_arn"],
        )
        resource_accounts = {
            resource_arn.split(":", 5)[4]
            for resource_arn in resource_arns
            if resource_arn.startswith("arn:")
        }
        _require(
            resource_accounts == {account},
            "Current AWS account does not own the Terraform resources",
        )
        return f"account={account}, principal={arn}"

    def check_ec2_and_ssm(self):
        instance_id = self.outputs["web_server_id"]
        response = self.client("ec2").describe_instances(InstanceIds=[instance_id])
        instances = [
            item
            for reservation in response.get("Reservations", [])
            for item in reservation.get("Instances", [])
        ]
        _require(len(instances) == 1, f"EC2 instance {instance_id} was not found")
        instance = instances[0]
        _require(instance.get("State", {}).get("Name") == "running", "EC2 is not running")
        _require(
            instance.get("MetadataOptions", {}).get("HttpTokens") == "required",
            "EC2 does not require IMDSv2 tokens",
        )
        profile_arn = instance.get("IamInstanceProfile", {}).get("Arn", "")
        _require(
            profile_arn.endswith("/" + self.outputs["web_instance_profile_name"]),
            "EC2 has the wrong instance profile",
        )

        ssm = self.client("ssm").describe_instance_information(
            Filters=[{"Key": "InstanceIds", "Values": [instance_id]}]
        )
        managed = ssm.get("InstanceInformationList", [])
        _require(managed, "EC2 is not registered with Systems Manager")
        _require(managed[0].get("PingStatus") == "Online", "SSM agent is not online")
        return f"{instance_id} is running, IMDSv2 required, SSM online"

    def check_rds(self):
        identifier = self.outputs["rds_instance_id"]
        response = self.client("rds").describe_db_instances(
            DBInstanceIdentifier=identifier
        )
        databases = response.get("DBInstances", [])
        _require(len(databases) == 1, f"RDS instance {identifier} was not found")
        database = databases[0]
        _require(database.get("DBInstanceStatus") == "available", "RDS is not available")
        _require(database.get("StorageEncrypted") is True, "RDS storage is not encrypted")
        _require(database.get("PubliclyAccessible") is False, "RDS is publicly accessible")
        _require(database.get("BackupRetentionPeriod", 0) >= 1, "RDS backups are disabled")
        _require(
            database.get("Endpoint", {}).get("Address") == self.outputs["rds_endpoint"],
            "RDS endpoint differs from Terraform output",
        )
        return (
            f"{identifier} is private, encrypted, available; "
            f"backup retention={database['BackupRetentionPeriod']} day(s)"
        )

    def check_s3(self):
        client = self.client("s3")
        bucket = self.outputs["s3_bucket_name"]
        location = client.get_bucket_location(Bucket=bucket).get("LocationConstraint")
        location = location or "us-east-1"
        expected_region = self.session.region_name if self.session else location
        _require(location == expected_region, f"S3 bucket is in unexpected region {location}")

        versioning = client.get_bucket_versioning(Bucket=bucket)
        _require(versioning.get("Status") == "Enabled", "S3 versioning is not enabled")
        public = client.get_public_access_block(Bucket=bucket)[
            "PublicAccessBlockConfiguration"
        ]
        settings = (
            "BlockPublicAcls",
            "IgnorePublicAcls",
            "BlockPublicPolicy",
            "RestrictPublicBuckets",
        )
        _require(
            all(public.get(setting) is True for setting in settings),
            "S3 public access block is incomplete",
        )
        policy_status = client.get_bucket_policy_status(Bucket=bucket).get(
            "PolicyStatus", {}
        )
        _require(policy_status.get("IsPublic") is False, "S3 bucket policy is public")
        encryption = client.get_bucket_encryption(Bucket=bucket)
        rules = encryption.get("ServerSideEncryptionConfiguration", {}).get("Rules", [])
        algorithms = {
            rule.get("ApplyServerSideEncryptionByDefault", {}).get("SSEAlgorithm")
            for rule in rules
        }
        _require(
            bool(algorithms & {"AES256", "aws:kms"}),
            "S3 default encryption is not configured",
        )
        return f"{bucket} is private, versioned and encrypted in {location}"

    def check_load_balancer(self):
        elbv2 = self.client("elbv2")
        load_balancers = elbv2.describe_load_balancers(
            LoadBalancerArns=[self.outputs["load_balancer_arn"]]
        ).get("LoadBalancers", [])
        _require(len(load_balancers) == 1, "Application Load Balancer was not found")
        load_balancer = load_balancers[0]
        _require(load_balancer.get("State", {}).get("Code") == "active", "ALB is not active")
        _require(load_balancer.get("Scheme") == "internet-facing", "ALB is not internet-facing")

        listeners = elbv2.describe_listeners(
            LoadBalancerArn=self.outputs["load_balancer_arn"]
        ).get("Listeners", [])
        by_port = {listener.get("Port"): listener for listener in listeners}
        _require(80 in by_port, "ALB has no HTTP listener")
        if self.outputs["https_enabled"]:
            _require(443 in by_port, "HTTPS is enabled but ALB has no HTTPS listener")
            actions = by_port[80].get("DefaultActions", [])
            _require(
                any(
                    action.get("Type") == "redirect"
                    and action.get("RedirectConfig", {}).get("Protocol") == "HTTPS"
                    for action in actions
                ),
                "HTTP listener does not redirect to HTTPS",
            )

        target_health = elbv2.describe_target_health(
            TargetGroupArn=self.outputs["target_group_arn"]
        ).get("TargetHealthDescriptions", [])
        matching = [
            target
            for target in target_health
            if target.get("Target", {}).get("Id") == self.outputs["web_server_id"]
        ]
        _require(matching, "EC2 is not registered in the target group")
        _require(
            matching[0].get("TargetHealth", {}).get("State") == "healthy",
            "EC2 target is not healthy",
        )
        return "ALB is active and the EC2 target is healthy"

    def check_iam(self):
        iam = self.client("iam")
        profile = iam.get_instance_profile(
            InstanceProfileName=self.outputs["web_instance_profile_name"]
        )["InstanceProfile"]
        role_names = {role["RoleName"] for role in profile.get("Roles", [])}
        role_name = self.outputs["web_iam_role_name"]
        _require(role_name in role_names, "Expected IAM role is not in the instance profile")

        attached = iam.list_attached_role_policies(RoleName=role_name).get(
            "AttachedPolicies", []
        )
        _require(
            any(
                policy.get("PolicyArn")
                == "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
                for policy in attached
            ),
            "SSM managed policy is not attached to the EC2 role",
        )
        document = iam.get_role_policy(
            RoleName=role_name,
            PolicyName=self.outputs["web_iam_policy_name"],
        ).get("PolicyDocument", {})
        statements = document.get("Statement", [])
        if isinstance(statements, dict):
            statements = [statements]
        _require(statements, "Application IAM policy has no statements")
        _require(
            not any(
                statement.get("Effect") == "Allow"
                and _contains_wildcard(statement.get("Action"))
                and _contains_wildcard(statement.get("Resource"))
                for statement in statements
            ),
            "Application IAM policy grants unrestricted access",
        )
        return f"instance profile uses {role_name}; no Allow */* statement"

    def check_secrets(self):
        arn = self.outputs["rds_master_secret_arn"]
        metadata = self.client("secretsmanager").describe_secret(SecretId=arn)
        _require(metadata.get("ARN") == arn, "RDS secret metadata does not match output")
        _require(metadata.get("DeletedDate") is None, "RDS secret is scheduled for deletion")
        return "RDS secret exists and is not scheduled for deletion"

    def check_observability(self):
        log_group_name = self.outputs["application_log_group_name"]
        response = self.client("logs").describe_log_groups(
            logGroupNamePrefix=log_group_name
        )
        groups = [
            group
            for group in response.get("logGroups", [])
            if group.get("logGroupName") == log_group_name
        ]
        _require(groups, "Application CloudWatch log group was not found")
        _require(groups[0].get("retentionInDays", 0) > 0, "Log retention is unlimited")

        alarm_names = self.outputs["cloudwatch_alarm_names"]
        alarms = self.client("cloudwatch").describe_alarms(AlarmNames=alarm_names)
        found = {alarm["AlarmName"] for alarm in alarms.get("MetricAlarms", [])}
        _require(found == set(alarm_names), "One or more CloudWatch alarms are missing")

        flow_logs = self.client("ec2").describe_flow_logs(
            Filter=[{"Name": "resource-id", "Values": [self.outputs["vpc_id"]]}]
        ).get("FlowLogs", [])
        _require(
            any(flow.get("FlowLogStatus") == "ACTIVE" for flow in flow_logs),
            "VPC Flow Logs are not active",
        )
        return (
            f"log retention={groups[0]['retentionInDays']} day(s), "
            f"{len(found)} alarm(s), VPC Flow Logs active"
        )

    def run(self):
        checks = [
            ("terraform_outputs", self.check_outputs),
            ("aws_identity", self.check_identity),
            ("ec2_ssm", self.check_ec2_and_ssm),
            ("rds", self.check_rds),
            ("s3", self.check_s3),
            ("load_balancer", self.check_load_balancer),
            ("iam", self.check_iam),
            ("secrets_manager", self.check_secrets),
            ("observability", self.check_observability),
        ]
        results = []
        for name, check in checks:
            try:
                detail = check()
                results.append(CheckResult(name, True, detail))
            except (AwsIntegrationError, BotoCoreError, ClientError, KeyError) as error:
                results.append(CheckResult(name, False, str(error)))
        return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--terraform-dir", default="terraform")
    parser.add_argument(
        "--outputs-file",
        help="Read saved `terraform output -json` data instead of invoking Terraform",
    )
    parser.add_argument("--region", help="Override the AWS region")
    parser.add_argument("--profile", help="Use a named AWS CLI profile")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    args = parser.parse_args()

    try:
        outputs = (
            load_outputs_file(args.outputs_file)
            if args.outputs_file
            else load_terraform_outputs(args.terraform_dir)
        )
        session = boto3.Session(profile_name=args.profile, region_name=args.region)
        if not session.region_name:
            raise AwsIntegrationError("AWS region is missing; pass --region or set AWS_REGION")
        results = AwsIntegrationChecker(outputs, session=session).run()
    except (AwsIntegrationError, BotoCoreError) as error:
        raise SystemExit(f"FAILED: {error}") from error

    if args.json:
        print(json.dumps([asdict(result) for result in results], indent=2))
    else:
        for result in results:
            status = "PASS" if result.passed else "FAIL"
            print(f"[{status}] {result.name}: {result.detail}")
        passed = sum(result.passed for result in results)
        print(f"\n{passed}/{len(results)} AWS integration checks passed")
    if not all(result.passed for result in results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
