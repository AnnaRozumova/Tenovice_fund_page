"""S3 static website hosting construct"""
from constructs import Construct
from aws_cdk import (
    aws_s3 as s3,
    aws_s3_deployment as s3deploy,
    Aws,
    RemovalPolicy,
    CfnOutput,
)

from .config import AppConfig


class S3WebsiteConstruct(Construct):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        config: AppConfig,
        api_url: str,
        cognito_region: str,
        user_pool_id: str,
        user_pool_client_id: str,
    ) -> None:
        super().__init__(scope, construct_id)

        # Create S3 bucket for static website
        self.website_bucket = s3.Bucket(
            self,
            "WebsiteBucket",
            # S3 bucket names are GLOBALLY unique across all of AWS, so
            # "{project}-{stage}-website" clashes the moment the same app is
            # deployed from a second account (e.g. a per-developer dev account
            # alongside the shared one). Include the account id: it guarantees
            # cross-account uniqueness, while `stage` separates environments
            # within one account. Resolved by CloudFormation at deploy time.
            bucket_name=f"{config.project_name}-{config.stage}-{Aws.ACCOUNT_ID}-website",
            website_index_document="index.html",
            website_error_document="index.html",
            public_read_access=True,
            block_public_access=s3.BlockPublicAccess(
                block_public_acls=False,
                block_public_policy=False,
                ignore_public_acls=False,
                restrict_public_buckets=False,
            ),
            removal_policy=RemovalPolicy.DESTROY if config.stage == "dev" else RemovalPolicy.RETAIN,
            auto_delete_objects=True if config.stage == "dev" else False,
        )

        # Per-stage runtime config, GENERATED at deploy time from THIS stack's own
        # outputs (D24). `web/config.js` ships only safe dev *fallbacks*; this file
        # loads right after it and overrides API_URL + the Cognito ids with the real
        # values of whatever stack is being deployed. So a prod `cdk deploy` bakes prod
        # endpoints automatically — no hand-editing config.js, no chance of a prod site
        # silently pointing at the dev API/pool (the leak that prompted this). Missing
        # locally (served straight from `web/`) → the dev fallbacks in config.js stand.
        # These values are public by design (a browser client id + an API URL), not
        # secrets — see cognito.py (the app client has no secret).
        generated_config = "\n".join(
            [
                "// GENERATED at deploy time by the CDK (s3_website.py). Do not edit by",
                "// hand and do not commit — it is rebuilt on every `cdk deploy` with the",
                "// deploying stack's real API + Cognito. Overrides the fallbacks in config.js.",
                "CONFIG.API_URL = '%s';" % api_url,
                "CONFIG.COGNITO = CONFIG.COGNITO || {};",
                "CONFIG.COGNITO.REGION = '%s';" % cognito_region,
                "CONFIG.COGNITO.USER_POOL_ID = '%s';" % user_pool_id,
                "CONFIG.COGNITO.CLIENT_ID = '%s';" % user_pool_client_id,
                "",
            ]
        )

        # Deploy website files + the generated per-stage config alongside them. Both
        # sources land in the same bucket; `config.generated.js` is not part of `web/`,
        # so there is no key collision with the static assets.
        s3deploy.BucketDeployment(
            self,
            "DeployWebsite",
            sources=[
                s3deploy.Source.asset("../web"),
                s3deploy.Source.data("config.generated.js", generated_config),
            ],
            destination_bucket=self.website_bucket,
        )

        # Output the website URL
        CfnOutput(
            self,
            "WebsiteURL",
            value=self.website_bucket.bucket_website_url,
            description="Static website URL",
        )

        CfnOutput(
            self,
            "BucketName",
            value=self.website_bucket.bucket_name,
            description="S3 bucket name",
        )
