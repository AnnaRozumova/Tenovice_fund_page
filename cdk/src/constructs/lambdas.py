"""The single API Lambda: one FastAPI app (via Mangum) behind an API-GW proxy.

Replaces the former 7 per-endpoint Lambdas (decision D19). The function bundles its
runtime deps (FastAPI + Mangum, from ``services/pledges_api/requirements.txt``) and
the source (``src/``) into one asset via Docker; the entrypoint is ``app.handler``
(the Mangum adapter). One function serves every route, so per-route authorization is
done in-app (the admin secret) and, once added, by the Cognito authorizer on the
proxy route (D18).
"""
import os

from constructs import Construct
from aws_cdk import BundlingOptions, Duration
from aws_cdk import aws_lambda as _lambda
from aws_cdk import aws_dynamodb as dynamodb

from .config import AppConfig


class LambdasConstruct(Construct):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        config: AppConfig,
        pledges_table: dynamodb.ITable,
    ) -> None:
        super().__init__(scope, construct_id)

        self.api_function = _lambda.Function(
            self,
            "ApiFn",
            function_name=f"{config.project_name}-{config.stage}-api",
            runtime=_lambda.Runtime.PYTHON_3_14,
            handler="app.handler",
            # Bundle runtime deps + source into one asset. pip installs FastAPI/Mangum
            # into /asset-output, then the source is copied alongside them, so the
            # Lambda root holds `app.py` (handler `app.handler`) + the packages.
            code=_lambda.Code.from_asset(
                "../services/pledges_api",
                bundling=BundlingOptions(
                    image=_lambda.Runtime.PYTHON_3_14.bundling_image,
                    command=[
                        "bash",
                        "-c",
                        "pip install -r requirements.txt -t /asset-output "
                        "&& cp -r src/. /asset-output",
                    ],
                ),
            ),
            timeout=Duration.seconds(15),
            environment={
                "PLEDGES_TABLE_NAME": pledges_table.table_name,
                # Admin secret for POST /config — supplied at deploy from the
                # environment (SSM / Secrets Manager via the pipeline, D13); never
                # committed. Empty default → update_config fails closed.
                "ADMIN_SECRET": os.environ.get("ADMIN_SECRET", ""),
            },
        )

        # One Lambda serves public reads, the simulator, and the admin write, so it
        # needs read-write on the table. Authorization is enforced in-app (and, once
        # added, by the Cognito authorizer at the gateway, D18).
        pledges_table.grant_read_write_data(self.api_function)
