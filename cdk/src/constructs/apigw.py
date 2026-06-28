"""HTTP API with a single catch-all proxy route → the one FastAPI Lambda (D19).

Every path/method (``ANY /{proxy+}``) is forwarded to the single API function; the
routing happens inside FastAPI. Adding or changing an endpoint is a code change in
FastAPI, with no API-GW/CDK edit. CORS preflight stays at the gateway. (Once auth
lands, the Cognito JWT authorizer attaches to this one route — D18.)
"""
from constructs import Construct
from aws_cdk import aws_apigatewayv2 as apigwv2
from aws_cdk import aws_apigatewayv2_integrations as integrations
from aws_cdk import aws_lambda as _lambda

from .config import AppConfig


class ApiConstruct(Construct):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        config: AppConfig,
        api_function: _lambda.IFunction,
    ) -> None:
        super().__init__(scope, construct_id)

        self.http_api = apigwv2.HttpApi(
            self,
            "HttpApi",
            api_name=config.api_name,
            cors_preflight=apigwv2.CorsPreflightOptions(
                allow_headers=["*"],
                allow_methods=[
                    apigwv2.CorsHttpMethod.GET,
                    apigwv2.CorsHttpMethod.POST,
                    apigwv2.CorsHttpMethod.OPTIONS,
                ],
                allow_origins=["*"],
            ),
        )

        # One catch-all route: ANY method, any path → the FastAPI Lambda. FastAPI
        # does the per-endpoint routing. (Authorizer attaches here later, D18.)
        self.http_api.add_routes(
            path="/{proxy+}",
            methods=[apigwv2.HttpMethod.ANY],
            integration=integrations.HttpLambdaIntegration(
                "ApiIntegration",
                handler=api_function,
            ),
        )
