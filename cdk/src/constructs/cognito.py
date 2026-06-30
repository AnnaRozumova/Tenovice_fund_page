"""Cognito user pool + app client for site authentication (AUTH1, decision D18).

The whole API (the calculator included) moves behind a login; only the home page
stays public (D18, scope widened 2026-06-28). This construct creates just the
**identity store** — a Cognito user pool and a public (no-secret) app client:

- AUTH1 (here): the pool + client only. **No authorizer is attached to the API
  yet**, so the existing API and site keep working unchanged. Deploy is safe.
- AUTH2 (frontend): custom on-site login / registration / password-recovery
  screens talk to this pool via SRP using the app client id.
- AUTH3 (enforce): a Cognito JWT authorizer is attached to the single
  ``ANY /{proxy+}`` route (apigw.py) and reads this pool — only then does the API
  start requiring a token.

Sign-in is by **email** (the email is the username; D18). Self sign-up is on with
email verification, and account recovery is email-only ("forgot password"). The
app client has **no secret** (it runs in the browser) and uses the **SRP** auth
flow, which ``amazon-cognito-identity-js`` uses for custom screens — so the
password is never sent to our code, only an SRP proof to Cognito.

Email delivery uses Cognito's built-in sender (no SES wiring), which is capped at
~50 emails/day — fine at our scale (< 1000 friends, infrequent registration). A
prod move to SES is a later follow-up if volume ever needs it.
"""
from constructs import Construct
from aws_cdk import (
    aws_cognito as cognito,
    aws_lambda as _lambda,
    Duration,
    RemovalPolicy,
    CfnOutput,
)

from .config import AppConfig


class CognitoConstruct(Construct):
    def __init__(self, scope: Construct, construct_id: str, *, config: AppConfig) -> None:
        super().__init__(scope, construct_id)

        is_dev = config.stage == "dev"

        # Custom Message trigger: localized (CZ/EN) verification + password-reset
        # emails (AUTH2). Pure stdlib handler → no bundling. The auth screens store
        # the chosen language in the user's `locale` attribute; the handler reads it.
        self.custom_message_fn = _lambda.Function(
            self,
            "CustomMessageFn",
            function_name=f"{config.project_name}-{config.stage}-cognito-message",
            runtime=_lambda.Runtime.PYTHON_3_14,
            handler="index.handler",
            code=_lambda.Code.from_asset("../services/cognito_custom_message"),
            timeout=Duration.seconds(5),
        )

        self.user_pool = cognito.UserPool(
            self,
            "UserPool",
            user_pool_name=f"{config.project_name}-{config.stage}-users",
            # Localized verification / reset emails (AUTH2).
            lambda_triggers=cognito.UserPoolTriggers(
                custom_message=self.custom_message_fn,
            ),
            # Users register themselves; email is the username and gets verified.
            self_sign_up_enabled=True,
            sign_in_aliases=cognito.SignInAliases(email=True),
            auto_verify=cognito.AutoVerifiedAttrs(email=True),
            standard_attributes=cognito.StandardAttributes(
                email=cognito.StandardAttribute(required=True, mutable=True),
            ),
            # Baseline (Martin's call): 10+ chars with an uppercase, a lowercase and
            # a digit — no symbol required. Stricter than Cognito's 8-char default but
            # easier to remember for a < 1000-friends login than a 12-char + symbol rule.
            password_policy=cognito.PasswordPolicy(
                min_length=10,
                require_lowercase=True,
                require_uppercase=True,
                require_digits=True,
                require_symbols=False,
            ),
            # "Forgot password" recovery goes to the verified email only.
            account_recovery=cognito.AccountRecovery.EMAIL_ONLY,
            # Built-in Cognito email sender (no SES); ~50/day cap is fine at our scale.
            email=cognito.UserPoolEmail.with_cognito(),
            mfa=cognito.Mfa.OFF,
            # Dev pools are disposable like the rest of the dev stack; prod is retained.
            removal_policy=RemovalPolicy.DESTROY if is_dev else RemovalPolicy.RETAIN,
            # Prod guard: RETAIN only stops stack-deletion, not an in-place REPLACE
            # (e.g. a future change to an immutable pool prop would orphan every
            # account). Deletion protection blocks that. Dev stays disposable.
            deletion_protection=not is_dev,
        )

        # Public browser client: no secret, SRP flow (amazon-cognito-identity-js).
        self.user_pool_client = self.user_pool.add_client(
            "WebClient",
            user_pool_client_name=f"{config.project_name}-{config.stage}-web",
            generate_secret=False,
            auth_flows=cognito.AuthFlow(user_srp=True),
            # Don't leak whether an email is registered (uniform errors on sign-in /
            # forgot-password) — matters because email is the identity.
            prevent_user_existence_errors=True,
            access_token_validity=Duration.hours(1),
            id_token_validity=Duration.hours(1),
            refresh_token_validity=Duration.days(30),
        )

        # Outputs consumed by the frontend (AUTH2 config) and the authorizer (AUTH3).
        CfnOutput(
            self,
            "UserPoolId",
            value=self.user_pool.user_pool_id,
            description="Cognito user pool id",
        )
        CfnOutput(
            self,
            "UserPoolClientId",
            value=self.user_pool_client.user_pool_client_id,
            description="Cognito app client id (public browser client)",
        )
