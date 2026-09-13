import re
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class CiConfigurationTests(unittest.TestCase):
    def read(self, relative_path):
        return (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")

    def test_all_actions_are_pinned_to_full_commit_shas(self):
        workflow_directory = PROJECT_ROOT / ".github" / "workflows"
        workflows = list(workflow_directory.glob("*.yml"))
        self.assertTrue(workflows)

        for workflow in workflows:
            for line_number, line in enumerate(
                workflow.read_text(encoding="utf-8").splitlines(), start=1
            ):
                match = re.search(r"\buses:\s*[^@\s]+@([^\s]+)", line)
                if match:
                    self.assertRegex(
                        match.group(1),
                        r"^[0-9a-f]{40}$",
                        f"{workflow.name}:{line_number} must pin a full SHA",
                    )

    def test_ci_has_read_only_permissions_and_security_gates(self):
        workflow = self.read(".github/workflows/ci.yml")
        self.assertIn("permissions:\n  contents: read", workflow)
        self.assertNotIn("id-token: write", workflow)
        for required_command in (
            "unittest discover -s tests",
            "pip_audit",
            "bandit",
            "terraform -chdir=terraform validate",
            "aquasecurity/trivy-action@",
            "docker build",
        ):
            self.assertIn(required_command, workflow)

    def test_deploy_is_manual_oidc_only_and_apply_is_guarded(self):
        workflow = self.read(".github/workflows/deploy.yml")
        self.assertIn("workflow_dispatch:", workflow)
        self.assertIn("id-token: write", workflow)
        self.assertIn("environment: cloudbox-dev", workflow)
        self.assertIn('GITHUB_REF" != "refs/heads/main', workflow)
        self.assertGreaterEqual(workflow.count("if: ${{ inputs.apply }}"), 5)
        self.assertNotIn("aws-access-key-id", workflow.casefold())
        self.assertNotIn("aws-secret-access-key", workflow.casefold())
        self.assertNotIn("AdministratorAccess", workflow)

    def test_dependabot_covers_every_pipeline_ecosystem(self):
        configuration = self.read(".github/dependabot.yml")
        for ecosystem in ("pip", "github-actions", "docker", "terraform"):
            self.assertIn(f"package-ecosystem: {ecosystem}", configuration)

    def test_security_tool_versions_are_pinned(self):
        requirements = self.read("requirements-dev.txt")
        self.assertRegex(requirements, r"(?m)^bandit==\d+\.\d+\.\d+$")
        self.assertRegex(requirements, r"(?m)^pip-audit==\d+\.\d+\.\d+$")

    def test_trivy_exceptions_are_scoped_and_documented(self):
        workflow = self.read(".github/workflows/ci.yml")
        ignore_file = self.read(".trivyignore.yaml")

        self.assertIn("trivyignores: .trivyignore.yaml", workflow)
        for check_id, path in (
            ("AWS-0053", "terraform/load-balancer.tf"),
            ("AWS-0054", "terraform/load-balancer.tf"),
            ("AWS-0104", "terraform/security-groups.tf"),
            ("AWS-0132", "terraform/storage.tf"),
        ):
            self.assertIn(f"id: {check_id}", ignore_file)
            self.assertIn(f'      - "{path}"', ignore_file)
        self.assertEqual(ignore_file.count("statement:"), 4)


if __name__ == "__main__":
    unittest.main()
