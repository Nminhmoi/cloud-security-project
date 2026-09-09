#!/usr/bin/env python3
"""Validate the project IAM policy examples against explicit local rules.

This deterministic linter is not a replacement for AWS IAM Access Analyzer.
It reports the checks it performed instead of claiming universal security.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


ACTION_PATTERN = re.compile(r"^[a-z0-9-]+:[A-Za-z0-9*?]+$")
ARN_PATTERN = re.compile(
    r"^arn:(aws|aws-us-gov|aws-cn):[a-z0-9-]*:[a-z0-9-]*:(?:[0-9]{12})?:.+$"
)


def _as_list(value):
    if isinstance(value, str):
        return [value]
    return value if isinstance(value, list) else []


class IAMPolicyValidator:
    """Lint an IAM identity-policy document using project security rules."""

    VALID_VERSIONS = {"2012-10-17", "2008-10-17"}

    def __init__(self, policy_path):
        self.policy_path = Path(policy_path)
        self.filename = self.policy_path.name
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.passed_checks: list[str] = []

    def validate(self):
        self.errors.clear()
        self.warnings.clear()
        self.passed_checks.clear()

        if not self.policy_path.is_file():
            self.errors.append(f"Policy file does not exist: {self.policy_path}")
            return False

        try:
            with self.policy_path.open("r", encoding="utf-8") as policy_file:
                data = json.load(policy_file)
        except json.JSONDecodeError as error:
            self.errors.append(f"Invalid JSON: {error}")
            return False
        except OSError as error:
            self.errors.append(f"Cannot read policy: {error}")
            return False

        statements = self._check_structure(data)
        for index, statement in enumerate(statements, 1):
            self._check_statement(statement, index)
        self._check_s3_transport_deny(statements)
        return not self.errors

    def _check_structure(self, data):
        if not isinstance(data, dict):
            self.errors.append("Policy root must be a JSON object")
            return []

        version = data.get("Version")
        if version not in self.VALID_VERSIONS:
            self.errors.append(
                "Version must be one of: " + ", ".join(sorted(self.VALID_VERSIONS))
            )
        else:
            self.passed_checks.append(f"Supported policy version: {version}")

        raw_statements = data.get("Statement")
        if isinstance(raw_statements, dict):
            statements = [raw_statements]
        elif isinstance(raw_statements, list) and raw_statements:
            statements = raw_statements
        else:
            self.errors.append("Statement must be a non-empty object or list")
            return []

        self.passed_checks.append(f"Policy contains {len(statements)} statement(s)")
        return statements

    def _check_statement(self, statement, index):
        label = f"statement #{index}"
        if not isinstance(statement, dict):
            self.errors.append(f"[{label}] Statement must be an object")
            return

        sid = statement.get("Sid")
        if sid is not None and not isinstance(sid, str):
            self.errors.append(f"[{label}] Sid must be a string")
        label = sid or label

        effect = statement.get("Effect")
        if effect not in {"Allow", "Deny"}:
            self.errors.append(f"[{label}] Effect must be Allow or Deny")

        has_action = "Action" in statement
        has_not_action = "NotAction" in statement
        if has_action == has_not_action:
            self.errors.append(f"[{label}] Specify exactly one of Action or NotAction")
            actions = []
        else:
            action_key = "Action" if has_action else "NotAction"
            actions = _as_list(statement.get(action_key))
            if not actions or not all(isinstance(action, str) for action in actions):
                self.errors.append(f"[{label}] {action_key} must contain action strings")

        for action in actions:
            if action == "*":
                if effect == "Allow":
                    self.errors.append(f"[{label}] Allow Action '*' is prohibited")
                else:
                    self.warnings.append(f"[{label}] Deny Action '*' is broad")
            elif not ACTION_PATTERN.fullmatch(action):
                self.errors.append(f"[{label}] Invalid IAM action: {action}")
            elif effect == "Allow" and ("*" in action or "?" in action):
                self.warnings.append(f"[{label}] Allowed action uses wildcard: {action}")

        has_resource = "Resource" in statement
        has_not_resource = "NotResource" in statement
        if has_resource == has_not_resource:
            self.errors.append(
                f"[{label}] Specify exactly one of Resource or NotResource"
            )
            resources = []
        else:
            resource_key = "Resource" if has_resource else "NotResource"
            resources = _as_list(statement.get(resource_key))
            if not resources or not all(
                isinstance(resource, str) for resource in resources
            ):
                self.errors.append(
                    f"[{label}] {resource_key} must contain resource strings"
                )

        for resource in resources:
            if resource == "*":
                if effect == "Allow":
                    self.warnings.append(f"[{label}] Allowed Resource is global")
            elif not ARN_PATTERN.fullmatch(resource):
                self.errors.append(f"[{label}] Invalid resource ARN: {resource}")

        condition = statement.get("Condition")
        if condition is not None and not isinstance(condition, dict):
            self.errors.append(f"[{label}] Condition must be an object")

    def _check_s3_transport_deny(self, statements):
        allowed_s3_resources = set()
        transport_denied_resources = set()

        for statement in statements:
            if not isinstance(statement, dict):
                continue
            actions = _as_list(statement.get("Action"))
            if statement.get("Effect") == "Allow" and any(
                action.startswith("s3:") for action in actions
            ):
                allowed_s3_resources.update(_as_list(statement.get("Resource")))

            bool_condition = statement.get("Condition", {}).get("Bool", {})
            secure_transport = bool_condition.get("aws:SecureTransport")
            denies_s3 = any(action in {"s3:*", "*"} for action in actions)
            resources = _as_list(statement.get("Resource"))
            if (
                statement.get("Effect") == "Deny"
                and denies_s3
                and str(secure_transport).lower() == "false"
            ):
                transport_denied_resources.update(
                    resource
                    for resource in resources
                    if resource.startswith("arn:aws:s3:::")
                )

        missing_transport_denies = (
            allowed_s3_resources - transport_denied_resources
        )
        if missing_transport_denies:
            self.errors.append(
                "S3 permissions require an aws:SecureTransport=false Deny "
                "covering every allowed S3 resource: "
                + ", ".join(sorted(missing_transport_denies))
            )
        elif allowed_s3_resources:
            self.passed_checks.append("S3 insecure transport is explicitly denied")

    def print_report(self):
        print("\n" + "=" * 64)
        print(f"IAM POLICY CHECK: {self.filename}")
        print("=" * 64)
        for check in self.passed_checks:
            print(f"[PASS] {check}")
        for warning in self.warnings:
            print(f"[WARN] {warning}")
        for error in self.errors:
            print(f"[FAIL] {error}")

        if self.errors:
            print(
                f"RESULT: INVALID under project rules "
                f"({len(self.errors)} error(s), {len(self.warnings)} warning(s))"
            )
        else:
            print(
                f"RESULT: VALID under project rules "
                f"(0 errors, {len(self.warnings)} warning(s))"
            )
        print("Note: this local linter is not AWS IAM Access Analyzer.")


def scan_directory(directory):
    policy_directory = Path(directory)
    if not policy_directory.is_dir():
        print(f"Policy directory does not exist: {policy_directory}")
        return False

    policy_files = sorted(policy_directory.glob("*_policy.json"))
    if not policy_files:
        print(f"No *_policy.json files found in {policy_directory}")
        return False

    all_valid = True
    for policy_path in policy_files:
        validator = IAMPolicyValidator(policy_path)
        all_valid = validator.validate() and all_valid
        validator.print_report()
    return all_valid


def main():
    parser = argparse.ArgumentParser(description="Lint project IAM policy JSON files")
    parser.add_argument("--policy", "-p", help="Path to one IAM policy JSON file")
    parser.add_argument(
        "--accounts",
        "-a",
        action="store_true",
        help="Run the read-only user account audit",
    )
    args = parser.parse_args()

    policies_directory = Path(__file__).resolve().parents[1] / "policies"
    if args.accounts:
        from security.iam.user_evaluator import list_user_accounts

        return 0 if list_user_accounts() else 1
    if args.policy:
        validator = IAMPolicyValidator(args.policy)
        valid = validator.validate()
        validator.print_report()
        return 0 if valid else 1
    return 0 if scan_directory(policies_directory) else 1


if __name__ == "__main__":
    sys.exit(main())
