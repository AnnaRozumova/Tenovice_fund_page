"""Docstring"""
from aws_cdk import Stack, CfnOutput
from constructs import Construct

from .constructs.config import AppConfig
from .constructs.dynamodb import DynamoDbConstruct
from .constructs.lambdas import LambdasConstruct
from .constructs.apigw import ApiConstruct
from .constructs.s3_website import S3WebsiteConstruct

class FundraisingCalculatorStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        config = AppConfig.from_cdk(self)

        db = DynamoDbConstruct(self, "DynamoDb", config=config)
        lambdas = LambdasConstruct(
            self, "Lambdas", config=config, pledges_table=db.pledges_table
        )
        api = ApiConstruct(self, "Api", config=config, handlers=lambdas.handlers)
        website = S3WebsiteConstruct(self, "Website", config=config)

        CfnOutput(self, "HttpApiUrl", value=api.http_api.api_endpoint)
