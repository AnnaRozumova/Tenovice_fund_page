"""Docstring"""
from dataclasses import dataclass
from constructs import Construct

# The only recognized deployment stages. `dev` is disposable (DESTROY + auto-delete,
# no deletion protection); anything else is treated as a protected prod-like env
# (RETAIN + deletion protection + PITR). Retention across the stateful resources
# (dynamodb.py, s3_website.py, cognito.py) keys off `stage == "dev"`, so a typo like
# "Dev"/"prod " would silently pick the wrong policy — validate it up front instead.
VALID_STAGES = ("dev", "prod")


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

        if stage not in VALID_STAGES:
            raise ValueError(
                f"Unknown stage {stage!r}. Pass --context stage=<{'|'.join(VALID_STAGES)}>; "
                "an unrecognized value would silently flip data-retention policies."
            )

        return AppConfig(
            project_name=project_name,
            stage=stage,
            api_name=api_name,
            pledges_table_name=pledges_table_name,
        )
