"""Docstring"""
from constructs import Construct
from aws_cdk import aws_apigatewayv2 as apigwv2
from aws_cdk import aws_apigatewayv2_integrations as integrations

from .config import AppConfig
from .lambdas import LambdaHandlers


class ApiConstruct(Construct):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        config: AppConfig,
        handlers: LambdaHandlers,
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
                    apigwv2.CorsHttpMethod.PUT,
                    apigwv2.CorsHttpMethod.OPTIONS,
                ],
                allow_origins=["*"],
            ),
        )

        self.http_api.add_routes(
            path="/stats",
            methods=[apigwv2.HttpMethod.GET],
            integration=integrations.HttpLambdaIntegration(
                "GetStatsIntegration",
                handler=handlers.get_stats,
            ),
        )

        if handlers.list_pledges:
            self.http_api.add_routes(
                path="/pledges",
                methods=[apigwv2.HttpMethod.GET],
                integration=integrations.HttpLambdaIntegration(
                    "ListPledgesIntegration",
                    handler=handlers.list_pledges,
                ),
            )

        if handlers.create_pledge:
            self.http_api.add_routes(
                path="/pledges",
                methods=[apigwv2.HttpMethod.POST],
                integration=integrations.HttpLambdaIntegration(
                    "CreatePledgeIntegration",
                    handler=handlers.create_pledge,
                ),
            )

        if handlers.get_pledge:
            self.http_api.add_routes(
                path="/pledges/{pledgeID}",
                methods=[apigwv2.HttpMethod.GET],
                integration=integrations.HttpLambdaIntegration(
                    "GetPledgeIntegration",
                    handler=handlers.get_pledge,
                ),
            )

        if handlers.update_pledge:
            self.http_api.add_routes(
                path="/pledges/{pledgeID}",
                methods=[apigwv2.HttpMethod.PUT],
                integration=integrations.HttpLambdaIntegration(
                    "UpdatePledgeIntegration",
                    handler=handlers.update_pledge,
                ),
            )
