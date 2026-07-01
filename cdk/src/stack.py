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
        # The identity store (AUTH1) must exist before the API so its JWT authorizer
        # (AUTH3) can reference the user pool + web client.
        cognito = CognitoConstruct(self, "Cognito", config=config)
        api = ApiConstruct(
            self,
            "Api",
            config=config,
            api_function=lambdas.api_function,
            user_pool=cognito.user_pool,
            user_pool_client=cognito.user_pool_client,
        )
        # The website gets a per-stage config.generated.js baked from these outputs, so
        # each deploy self-configures its frontend (no hand-edited API_URL — see D24).
        S3WebsiteConstruct(
            self,
            "Website",
            config=config,
            api_url=api.http_api.api_endpoint,
            cognito_region=self.region,
            user_pool_id=cognito.user_pool.user_pool_id,
            user_pool_client_id=cognito.user_pool_client.user_pool_client_id,
        )

        CfnOutput(self, "HttpApiUrl", value=api.http_api.api_endpoint)
