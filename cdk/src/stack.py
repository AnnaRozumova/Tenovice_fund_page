"""Docstring"""
from aws_cdk import Stack, CfnOutput
from constructs import Construct

from .constructs.config import AppConfig
from .constructs.dynamodb import DynamoDbConstruct
from .constructs.lambdas import LambdasConstruct
from .constructs.apigw import ApiConstruct
from .constructs.s3_website import S3WebsiteConstruct
from .constructs.cognito import CognitoConstruct

class FundraisingCalculatorStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        config = AppConfig.from_cdk(self)

        db = DynamoDbConstruct(self, "DynamoDb", config=config)
        lambdas = LambdasConstruct(
            self, "Lambdas", config=config, pledges_table=db.pledges_table
        )
        api = ApiConstruct(self, "Api", config=config, api_function=lambdas.api_function)
        S3WebsiteConstruct(self, "Website", config=config)
        # Identity store only (AUTH1). The JWT authorizer that puts this pool in
        # front of the API lands in AUTH3 — for now the API stays open.
        CognitoConstruct(self, "Cognito", config=config)

        CfnOutput(self, "HttpApiUrl", value=api.http_api.api_endpoint)
