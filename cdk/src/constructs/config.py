"""Docstring"""
from dataclasses import dataclass
from constructs import Construct

@dataclass(frozen=True)
class AppConfig:
    project_name: str
    stage: str
    api_name: str
    pledges_table_name: str

    @staticmethod
    def from_cdk(scope: Construct) -> "AppConfig":
        """
        Reads values from `cdk.json` context (or CLI --context overrides).
        """
        project_name = scope.node.try_get_context("project_name") or "fundraising-calculator"
        stage = scope.node.try_get_context("stage") or "dev"
        api_name = scope.node.try_get_context("api_name") or "fundraising-api"
        pledges_table_name = scope.node.try_get_context("pledges_table_name") or "Pledges"

        return AppConfig(
            project_name=project_name,
            stage=stage,
            api_name=api_name,
            pledges_table_name=pledges_table_name,
        )
