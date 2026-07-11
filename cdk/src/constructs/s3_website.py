"""S3 static site bucket.

Per stage the bucket has a **different exposure**:

- **dev** — a public S3 *website* bucket (HTTP website endpoint, public-read), exactly as
  before. The dev CloudFront skeleton fronts that website endpoint; a private bucket would
  buy nothing on a disposable env, so dev is left untouched.
- **prod** — a **private** bucket (all public access blocked, no website hosting), read
  **only through CloudFront via OAC**. The live prod site is currently served by a
  **manually-created** CloudFront distribution (outside this CDK) whose OAC reads this
  exact bucket (its name follows the CDK scheme, so `cdk deploy -c stage=prod` *does* manage
  it). We codify that manual state here — private bucket + the OAC read grant for the manual
  distribution — so a prod deploy re-writes the **same** policy instead of reverting the
  bucket to public and dropping the grant (which would 403 the live site). The CDK CloudFront
  skeleton (cloudfront.py) adds its own OAC grant on top, so the policy ends up allowing both
  distributions. Prod traffic still flows through the manual distribution — no migration yet.
"""
from constructs import Construct
from aws_cdk import (
    aws_s3 as s3,
    aws_s3_deployment as s3deploy,
    aws_iam as iam,
    Aws,
    RemovalPolicy,
    CfnOutput,
)

from .config import AppConfig

# The manually-created prod CloudFront distribution that serves one-tenovice.cz today
# (created outside this CDK, reads this bucket via OAC). Prod-only: the prod account is
# 541668764077 and this id is stable. Codifying its read grant keeps a prod `cdk deploy`
# from clobbering the bucket policy Ondra set by hand. If the manual distribution is ever
# replaced, update this ARN.
MANUAL_PROD_CLOUDFRONT_ARN = "arn:aws:cloudfront::541668764077:distribution/E1RYSEQBJ360SU"


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

        is_prod = config.stage == "prod"

        # S3 bucket names are GLOBALLY unique across all of AWS, so
        # "{project}-{stage}-website" clashes the moment the same app is deployed from a
        # second account (e.g. a per-developer dev account alongside the shared one).
        # Include the account id: it guarantees cross-account uniqueness, while `stage`
        # separates environments within one account. Resolved by CloudFormation at deploy time.
        bucket_name = f"{config.project_name}-{config.stage}-{Aws.ACCOUNT_ID}-website"
        # dev is disposable (wiped on destroy); prod is retained.
        removal_policy = RemovalPolicy.DESTROY if config.stage == "dev" else RemovalPolicy.RETAIN
        auto_delete_objects = not is_prod

        if is_prod:
            # Private: no public access at all, no website hosting. Readable only through
            # CloudFront (OAC) — see the module docstring + the OAC grant just below.
            self.website_bucket = s3.Bucket(
                self,
                "WebsiteBucket",
                bucket_name=bucket_name,
                block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
                removal_policy=removal_policy,
                auto_delete_objects=auto_delete_objects,
            )
            # Codify the read grant for the manually-created prod CloudFront distribution
            # (OAC). Its principal is the CloudFront service, scoped to that one distribution
            # via AWS:SourceArn — the exact statement Ondra set by hand, so a deploy is
            # idempotent instead of destructive. The CDK CloudFront skeleton adds its own
            # grant separately (cloudfront.py), giving a two-statement policy that allows
            # both distributions.
            self.website_bucket.add_to_resource_policy(
                iam.PolicyStatement(
                    sid="AllowManualCloudFrontServicePrincipalReadOnly",
                    effect=iam.Effect.ALLOW,
                    principals=[iam.ServicePrincipal("cloudfront.amazonaws.com")],
                    actions=["s3:GetObject"],
                    resources=[self.website_bucket.arn_for_objects("*")],
                    conditions={
                        "StringEquals": {"AWS:SourceArn": MANUAL_PROD_CLOUDFRONT_ARN}
                    },
                )
            )
        else:
            # dev: public S3 *website* bucket, unchanged (the dev CloudFront skeleton fronts
            # the website endpoint, which requires public read).
            self.website_bucket = s3.Bucket(
                self,
                "WebsiteBucket",
                bucket_name=bucket_name,
                website_index_document="index.html",
                website_error_document="index.html",
                public_read_access=True,
                block_public_access=s3.BlockPublicAccess(
                    block_public_acls=False,
                    block_public_policy=False,
                    ignore_public_acls=False,
                    restrict_public_buckets=False,
                ),
                removal_policy=removal_policy,
                auto_delete_objects=auto_delete_objects,
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

        # Output the website URL. A prod bucket has no S3 website endpoint (private,
        # CloudFront-only), so emit its regional domain with a note instead — the real
        # entry point on prod is the CloudFront domain (see cloudfront.py output).
        if is_prod:
            CfnOutput(
                self,
                "WebsiteURL",
                value=f"https://{self.website_bucket.bucket_regional_domain_name}",
                description="Private S3 bucket domain — not directly browsable; served via CloudFront",
            )
        else:
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
