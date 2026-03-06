"""Docstring"""
from constructs import Construct
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import RemovalPolicy

from .config import AppConfig


class DynamoDbConstruct(Construct):
    def __init__(self, scope: Construct, construct_id: str, *, config: AppConfig) -> None:
        super().__init__(scope, construct_id)

        self.pledges_table = dynamodb.Table(
            self,
            "PledgesTable",
            table_name=f"{config.project_name}-{config.stage}-{config.pledges_table_name}",
            partition_key=dynamodb.Attribute(
                name="pledgeID",
                type=dynamodb.AttributeType.STRING,
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY if config.stage == "dev" else RemovalPolicy.RETAIN,
        )
