"""HTTP API with a single catch-all proxy route → the one FastAPI Lambda (D19).

Every path/method (``ANY /{proxy+}``) is forwarded to the single API function; the
routing happens inside FastAPI. Adding or changing an endpoint is a code change in
FastAPI, with no API-GW/CDK edit. CORS preflight stays at the gateway.

AUTH3 (D18) puts the API behind a **Cognito JWT authorizer** attached to that proxy
route — so by default every request needs a valid token. Three things must escape the
authorizer, so they are declared as **separate, unauthenticated routes** (a static
path beats the greedy ``/{proxy+}``, and a specific method beats ``ANY``, so these win
the route match):

- ``GET /stats`` and ``GET /config`` — the **home page is the only public page**
  (D18); it reads these two without a login.
- ``POST /config`` — the **admin** write. It has its *own* shared-secret auth (D6),
  not Cognito, so it must bypass the JWT authorizer. (``GET`` + ``POST`` are covered by
  one ``ANY /config`` route.)
- ``OPTIONS /{proxy+}`` — the browser's CORS **preflight** carries no token, so if it
  hit the authorizer it would 401 and the browser would block every gated ``POST``.

The stage also gets **API-Gateway throttling** (rate + burst) on every env (D18) so a
request flood can't run up the Lambda bill. WAF stays prod-only and lands with
CloudFront (D21/Phase G — it can't attach to an HTTP API directly).
"""
from constructs import Construct
from aws_cdk import aws_apigatewayv2 as apigwv2
from aws_cdk import aws_apigatewayv2_integrations as integrations
from aws_cdk import aws_cognito as cognito
from aws_cdk import aws_lambda as _lambda
from aws_cdk.aws_apigatewayv2_authorizers import HttpUserPoolAuthorizer

from .config import AppConfig

# Steady-state requests/sec and the spike bucket size, applied to every route via the
# stage default. Generous for < 1000 friends hitting a few endpoints per page load, but
# a hard ceiling vs. the account default (10k rps) so a flood can't run up the bill.
API_THROTTLE_RATE = 20
API_THROTTLE_BURST = 40


class ApiConstruct(Construct):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        config: AppConfig,
        api_function: _lambda.IFunction,
        user_pool: cognito.IUserPool,
        user_pool_client: cognito.IUserPoolClient,
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

        # One integration object, reused by every route (gated + public).
        integration = integrations.HttpLambdaIntegration(
            "ApiIntegration",
            handler=api_function,
        )

        # Cognito JWT authorizer over this stack's user pool (AUTH1) + its public web
        # client. The default identity source is the ``Authorization`` header, which is
        # where the frontend already sends ``Bearer <idToken>`` (AUTH2). The id token's
        # ``aud`` claim is the client id, so listing the client scopes validation to it.
        # NB: the authorizer admits any token from this client (id OR access); an access
        # token lacks the ``email`` claim, so the app keys identity off the ``email``
        # claim and fails closed when it's missing (services/.../api/pledges.py).
        authorizer = HttpUserPoolAuthorizer(
            "JwtAuthorizer",
            user_pool,
            user_pool_clients=[user_pool_client],
        )

        # Public carve-outs (NO authorizer) — declared first for clarity; route match is
        # by specificity, not declaration order. See the module docstring for why each
        # one must escape the JWT authorizer.
        self.http_api.add_routes(
            path="/stats",
            methods=[apigwv2.HttpMethod.GET],
            integration=integration,
        )
        self.http_api.add_routes(
            path="/config",
            methods=[apigwv2.HttpMethod.ANY],
            integration=integration,
        )
        self.http_api.add_routes(
            path="/{proxy+}",
            methods=[apigwv2.HttpMethod.OPTIONS],
            integration=integration,
        )

        # Everything else (the calculator, the pledge create/list, by-email) requires a
        # valid Cognito token — unauthenticated requests get a 401 from the gateway.
        self.http_api.add_routes(
            path="/{proxy+}",
            methods=[apigwv2.HttpMethod.ANY],
            integration=integration,
            authorizer=authorizer,
        )

        # Throttling on the auto-created ``$default`` stage, applied to all routes. The
        # L2 HttpApi exposes no throttle prop, so set it on the underlying CfnStage.
        cfn_stage = self.http_api.default_stage.node.default_child
        cfn_stage.default_route_settings = apigwv2.CfnStage.RouteSettingsProperty(
            throttling_rate_limit=API_THROTTLE_RATE,
            throttling_burst_limit=API_THROTTLE_BURST,
        )
