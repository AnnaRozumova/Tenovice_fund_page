"""Docstring"""
from constructs import Construct
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import RemovalPolicy

from .config import AppConfig


class DynamoDbConstruct(Construct):
    def __init__(self, scope: Construct, construct_id: str, *, config: AppConfig) -> None:
        super().__init__(scope, construct_id)

        is_dev = config.stage == "dev"

        self.pledges_table = dynamodb.Table(
            self,
            "PledgesTable",
            table_name=f"{config.project_name}-{config.stage}-{config.pledges_table_name}",
            partition_key=dynamodb.Attribute(
                name="pledgeID",
                type=dynamodb.AttributeType.STRING,
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY if is_dev else RemovalPolicy.RETAIN,
            # Data-loss guards on the real pledge data (mirrors cognito.py's pool guard).
            # RETAIN alone only blocks a stack DELETE, not an in-place REPLACE (the
            # table_name + partition key are immutable, so a future change to either
            # replaces the table). deletion_protection blocks that replace/delete on
            # prod; point-in-time recovery keeps a 35-day continuous backup to restore
            # from. Both are off on disposable dev so `cdk destroy` still works there.
            deletion_protection=not is_dev,
            point_in_time_recovery_specification=dynamodb.PointInTimeRecoverySpecification(
                point_in_time_recovery_enabled=not is_dev,
            ),
        )

        # Add GSI for querying by email
        self.pledges_table.add_global_secondary_index(
            index_name="EmailIndex",
            partition_key=dynamodb.Attribute(
                name="email",
                type=dynamodb.AttributeType.STRING,
            ),
            projection_type=dynamodb.ProjectionType.ALL,
        )
