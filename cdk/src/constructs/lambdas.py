"""Docstring"""
from dataclasses import dataclass
from typing import Optional

from constructs import Construct
from aws_cdk import Duration
from aws_cdk import aws_lambda as _lambda
from aws_cdk import aws_dynamodb as dynamodb

from .config import AppConfig


@dataclass(frozen=True)
class LambdaHandlers:
    get_stats: _lambda.Function
    create_pledge: Optional[_lambda.Function] = None
    get_pledge: Optional[_lambda.Function] = None
    update_pledge: Optional[_lambda.Function] = None


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

        get_stats = _lambda.Function(
            self,
            "GetStatsFn",
            function_name=f"{config.project_name}-{config.stage}-get-stats",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="handlers.get_stats.handler",
            code=_lambda.Code.from_asset("../services/pledges_api/src"),
            timeout=Duration.seconds(10),
            environment={
                "PLEDGES_TABLE_NAME": pledges_table.table_name,
            },
        )

        pledges_table.grant_read_data(get_stats)

        self.handlers = LambdaHandlers(get_stats=get_stats)
