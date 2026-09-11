import unittest
from unittest.mock import Mock

from scripts.aws_integration_test import (
    AwsIntegrationChecker,
    AwsIntegrationError,
    normalize_terraform_outputs,
)


class AwsIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.outputs = {
            "application_log_group_name": "/cloudbox/dev/application",
            "application_url": "http://cloudbox.example.elb.amazonaws.com",
            "cloudwatch_alarm_names": ["dev-ec2-high-cpu", "dev-rds-low-storage"],
            "https_enabled": False,
            "load_balancer_arn": "arn:aws:elasticloadbalancing:region:123:loadbalancer/app/dev/id",
            "rds_endpoint": "database.example.rds.amazonaws.com",
            "rds_instance_id": "dev-cloudbox-mysql",
            "rds_master_secret_arn": "arn:aws:secretsmanager:region:123:secret:rds",
            "s3_bucket_name": "dev-cloudbox-documents",
            "target_group_arn": "arn:aws:elasticloadbalancing:region:123:targetgroup/dev/id",
            "vpc_id": "vpc-123",
            "web_iam_policy_name": "dev-cloudbox-application-policy",
            "web_iam_role_name": "dev-cloudbox-ec2-role",
            "web_instance_profile_name": "dev-cloudbox-ec2-profile",
            "web_server_id": "i-123",
        }
        self.clients = self.build_clients()

    def build_clients(self):
        clients = {name: Mock() for name in (
            "cloudwatch",
            "ec2",
            "elbv2",
            "iam",
            "logs",
            "rds",
            "s3",
            "secretsmanager",
            "ssm",
            "sts",
        )}
        clients["sts"].get_caller_identity.return_value = {
            "Account": "123",
            "Arn": "arn:aws:iam::123:user/deployer",
        }
        clients["ec2"].describe_instances.return_value = {
            "Reservations": [{
                "Instances": [{
                    "InstanceId": "i-123",
                    "State": {"Name": "running"},
                    "MetadataOptions": {"HttpTokens": "required"},
                    "IamInstanceProfile": {
                        "Arn": "arn:aws:iam::123:instance-profile/dev-cloudbox-ec2-profile"
                    },
                }]
            }]
        }
        clients["ec2"].describe_flow_logs.return_value = {
            "FlowLogs": [{"FlowLogStatus": "ACTIVE"}]
        }
        clients["ssm"].describe_instance_information.return_value = {
            "InstanceInformationList": [{"PingStatus": "Online"}]
        }
        clients["rds"].describe_db_instances.return_value = {
            "DBInstances": [{
                "DBInstanceStatus": "available",
                "StorageEncrypted": True,
                "PubliclyAccessible": False,
                "BackupRetentionPeriod": 7,
                "Endpoint": {"Address": "database.example.rds.amazonaws.com"},
            }]
        }
        clients["s3"].get_bucket_location.return_value = {
            "LocationConstraint": "ap-southeast-1"
        }
        clients["s3"].get_bucket_versioning.return_value = {"Status": "Enabled"}
        clients["s3"].get_public_access_block.return_value = {
            "PublicAccessBlockConfiguration": {
                "BlockPublicAcls": True,
                "IgnorePublicAcls": True,
                "BlockPublicPolicy": True,
                "RestrictPublicBuckets": True,
            }
        }
        clients["s3"].get_bucket_policy_status.return_value = {
            "PolicyStatus": {"IsPublic": False}
        }
        clients["s3"].get_bucket_encryption.return_value = {
            "ServerSideEncryptionConfiguration": {
                "Rules": [{
                    "ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}
                }]
            }
        }
        clients["elbv2"].describe_load_balancers.return_value = {
            "LoadBalancers": [{
                "State": {"Code": "active"},
                "Scheme": "internet-facing",
            }]
        }
        clients["elbv2"].describe_listeners.return_value = {
            "Listeners": [{"Port": 80, "DefaultActions": [{"Type": "forward"}]}]
        }
        clients["elbv2"].describe_target_health.return_value = {
            "TargetHealthDescriptions": [{
                "Target": {"Id": "i-123"},
                "TargetHealth": {"State": "healthy"},
            }]
        }
        clients["iam"].get_instance_profile.return_value = {
            "InstanceProfile": {"Roles": [{"RoleName": "dev-cloudbox-ec2-role"}]}
        }
        clients["iam"].list_attached_role_policies.return_value = {
            "AttachedPolicies": [{
                "PolicyArn": "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
            }]
        }
        clients["iam"].get_role_policy.return_value = {
            "PolicyDocument": {
                "Statement": [{
                    "Effect": "Allow",
                    "Action": ["s3:GetObject"],
                    "Resource": ["arn:aws:s3:::dev-cloudbox-documents/*"],
                }]
            }
        }
        clients["secretsmanager"].describe_secret.return_value = {
            "ARN": "arn:aws:secretsmanager:region:123:secret:rds"
        }
        clients["logs"].describe_log_groups.return_value = {
            "logGroups": [{
                "logGroupName": "/cloudbox/dev/application",
                "retentionInDays": 30,
            }]
        }
        clients["cloudwatch"].describe_alarms.return_value = {
            "MetricAlarms": [
                {"AlarmName": "dev-ec2-high-cpu"},
                {"AlarmName": "dev-rds-low-storage"},
            ]
        }
        return clients

    def test_normalizes_real_terraform_output_shape(self):
        normalized = normalize_terraform_outputs({
            "application_url": {
                "sensitive": False,
                "type": "string",
                "value": "https://cloudbox.example.com",
            },
            "https_enabled": True,
        })
        self.assertEqual(normalized["application_url"], "https://cloudbox.example.com")
        self.assertIs(normalized["https_enabled"], True)

        with self.assertRaisesRegex(AwsIntegrationError, "JSON object"):
            normalize_terraform_outputs([])

    def test_all_read_only_integration_checks_pass(self):
        checker = AwsIntegrationChecker(self.outputs, clients=self.clients)
        results = checker.run()

        self.assertEqual(len(results), 9)
        self.assertTrue(all(result.passed for result in results), results)
        self.clients["secretsmanager"].describe_secret.assert_called_once_with(
            SecretId=self.outputs["rds_master_secret_arn"]
        )

    def test_detects_public_s3_bucket(self):
        self.clients["s3"].get_bucket_policy_status.return_value = {
            "PolicyStatus": {"IsPublic": True}
        }
        checker = AwsIntegrationChecker(self.outputs, clients=self.clients)

        with self.assertRaisesRegex(AwsIntegrationError, "policy is public"):
            checker.check_s3()

    def test_reports_failed_invariant_without_stopping_other_checks(self):
        self.clients["rds"].describe_db_instances.return_value["DBInstances"][0][
            "PubliclyAccessible"
        ] = True
        checker = AwsIntegrationChecker(self.outputs, clients=self.clients)

        results = {result.name: result for result in checker.run()}
        self.assertFalse(results["rds"].passed)
        self.assertIn("publicly accessible", results["rds"].detail)
        self.assertTrue(results["s3"].passed)

    def test_rejects_wrong_account_and_url_scheme(self):
        checker = AwsIntegrationChecker(self.outputs, clients=self.clients)
        self.clients["sts"].get_caller_identity.return_value["Account"] = "999"
        with self.assertRaisesRegex(AwsIntegrationError, "does not own"):
            checker.check_identity()

        self.outputs["https_enabled"] = True
        with self.assertRaisesRegex(AwsIntegrationError, "must use https"):
            checker.check_outputs()

    def test_https_requires_listener_and_redirect(self):
        self.outputs["https_enabled"] = True
        self.clients["elbv2"].describe_listeners.return_value = {
            "Listeners": [
                {
                    "Port": 80,
                    "DefaultActions": [{
                        "Type": "redirect",
                        "RedirectConfig": {"Protocol": "HTTPS"},
                    }],
                },
                {"Port": 443, "DefaultActions": [{"Type": "forward"}]},
            ]
        }
        checker = AwsIntegrationChecker(self.outputs, clients=self.clients)
        self.assertIn("target is healthy", checker.check_load_balancer())

    def test_rejects_unrestricted_iam_statement_in_list_form(self):
        self.clients["iam"].get_role_policy.return_value = {
            "PolicyDocument": {
                "Statement": [{
                    "Effect": "Allow",
                    "Action": ["*"],
                    "Resource": ["*"],
                }]
            }
        }
        checker = AwsIntegrationChecker(self.outputs, clients=self.clients)
        with self.assertRaisesRegex(AwsIntegrationError, "unrestricted"):
            checker.check_iam()


if __name__ == "__main__":
    unittest.main()
