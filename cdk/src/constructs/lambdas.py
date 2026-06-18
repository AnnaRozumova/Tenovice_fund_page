"""Docstring"""
import os
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
    list_pledges: Optional[_lambda.Function] = None
    get_pledge_by_email: Optional[_lambda.Function] = None
    get_config: Optional[_lambda.Function] = None
    update_config: Optional[_lambda.Function] = None


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

        create_pledge = _lambda.Function(
            self,
            "CreatePledgeFn",
            function_name=f"{config.project_name}-{config.stage}-create-pledge",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="handlers.create_pledge.handler",
            code=_lambda.Code.from_asset("../services/pledges_api/src"),
            timeout=Duration.seconds(10),
            environment={
                "PLEDGES_TABLE_NAME": pledges_table.table_name,
            },
        )

        pledges_table.grant_read_write_data(create_pledge)

        list_pledges = _lambda.Function(
            self,
            "ListPledgesFn",
            function_name=f"{config.project_name}-{config.stage}-list-pledges",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="handlers.list_pledges.handler",
            code=_lambda.Code.from_asset("../services/pledges_api/src"),
            timeout=Duration.seconds(10),
            environment={
                "PLEDGES_TABLE_NAME": pledges_table.table_name,
            },
        )

        pledges_table.grant_read_data(list_pledges)

        get_pledge_by_email = _lambda.Function(
            self,
            "GetPledgeByEmailFn",
            function_name=f"{config.project_name}-{config.stage}-get-pledge-by-email",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="handlers.get_pledge_by_email.handler",
            code=_lambda.Code.from_asset("../services/pledges_api/src"),
            timeout=Duration.seconds(10),
            environment={
                "PLEDGES_TABLE_NAME": pledges_table.table_name,
            },
        )

        pledges_table.grant_read_data(get_pledge_by_email)

        get_config = _lambda.Function(
            self,
            "GetConfigFn",
            function_name=f"{config.project_name}-{config.stage}-get-config",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="handlers.get_config.handler",
            code=_lambda.Code.from_asset("../services/pledges_api/src"),
            timeout=Duration.seconds(10),
            environment={
                "PLEDGES_TABLE_NAME": pledges_table.table_name,
            },
        )

        pledges_table.grant_read_data(get_config)

        # The admin secret is supplied at deploy time from the environment, which the
        # CI/CD pipeline (D13) sources from SSM / Secrets Manager — it is never
        # committed. Defaults to empty, in which case update_config fails closed.
        update_config = _lambda.Function(
            self,
            "UpdateConfigFn",
            function_name=f"{config.project_name}-{config.stage}-update-config",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="handlers.update_config.handler",
            code=_lambda.Code.from_asset("../services/pledges_api/src"),
            timeout=Duration.seconds(10),
            environment={
                "PLEDGES_TABLE_NAME": pledges_table.table_name,
                "ADMIN_SECRET": os.environ.get("ADMIN_SECRET", ""),
            },
        )

        pledges_table.grant_read_write_data(update_config)

        self.handlers = LambdaHandlers(
            get_stats=get_stats,
            create_pledge=create_pledge,
            list_pledges=list_pledges,
            get_pledge_by_email=get_pledge_by_email,
            get_config=get_config,
            update_config=update_config,
        )
