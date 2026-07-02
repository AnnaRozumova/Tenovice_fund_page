"""CloudFront distribution in front of the S3 static-site bucket (Phase G, D9).

Stood up now as a **skeleton** on every stage (dev + prod) but deliberately **not wired
to anything yet** (Ondra, 2026-07-02): no custom-domain alias, no ACM certificate, no
Origin Access Control, no WAF. It just fronts the existing public S3 website bucket and
is reachable only by its own ``*.cloudfront.net`` URL — a parallel distribution no real
user hits yet.

Why this is safe next to the live site:

- It does **not** touch prod's live traffic. The real site still flows through Ondra's
  manually-created CloudFront (managed outside this CDK); DNS is unchanged. A ``cdk
  deploy`` *creates* this distribution and never deletes or adopts the manual one —
  CloudFormation only manages what it created.
- **No alias on purpose.** CloudFront refuses the same CNAME on two distributions, and
  no alias means no DNS conflict. Attaching ``one-tenovice.cz`` + an ACM cert, switching
  the origin to OAC (private bucket), and adding response-header / WAF hardening is the
  later *wiring* step — a deliberate DNS cutover done once there is time.

Cost: a CloudFront distribution has no fixed or hourly charge — only per-request and data
transfer, both ~zero for a distribution no DNS points at (and under the perpetual free
tier). Standing it up on dev + prod is effectively free.
"""
from constructs import Construct
from aws_cdk import (
    aws_s3 as s3,
    aws_cloudfront as cloudfront,
    aws_cloudfront_origins as origins,
    CfnOutput,
)

from .config import AppConfig


class CloudFrontConstruct(Construct):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        config: AppConfig,
        website_bucket: s3.IBucket,
    ) -> None:
        super().__init__(scope, construct_id)

        # Origin = the existing S3 *website* endpoint (HTTP-only, public-read), matching
        # how the site is served today. Moving to a private bucket + Origin Access Control
        # is deferred to the wiring step: OAC needs the REST endpoint and a coordinated
        # cutover so the live site can't 403 mid-switch.
        self.distribution = cloudfront.Distribution(
            self,
            "Distribution",
            comment=f"{config.project_name}-{config.stage} (skeleton — not wired to a domain yet)",
            default_root_object="index.html",
            default_behavior=cloudfront.BehaviorOptions(
                origin=origins.S3StaticWebsiteOrigin(website_bucket),
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
            ),
        )

        CfnOutput(
            self,
            "CloudFrontDomainName",
            value=self.distribution.distribution_domain_name,
            description="CloudFront *.cloudfront.net domain (test URL until wired to the real domain)",
        )
        CfnOutput(
            self,
            "CloudFrontDistributionId",
            value=self.distribution.distribution_id,
            description="CloudFront distribution id (for invalidations and later wiring)",
        )
