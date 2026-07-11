"""CloudFront distribution in front of the S3 static-site bucket (Phase G, D9).

Stood up as a **skeleton** on every stage (dev + prod) but deliberately **not wired to a
domain yet** (Ondra, 2026-07-02): no custom-domain alias, no ACM certificate, no WAF. It is
reachable only by its own ``*.cloudfront.net`` URL — a parallel distribution no real user
hits yet.

Its **origin depends on the stage** (matching the bucket's exposure in s3_website.py): on
**dev** it fronts the public S3 *website* endpoint; on **prod** it uses **Origin Access
Control** against the now-private bucket (public access blocked, no website hosting). The
prod OAC switch is what keeps this skeleton functional once the bucket is locked down; it
does **not** migrate prod traffic — the live site still flows through the manually-created
prod CloudFront (managed outside this CDK).

Why this is safe next to the live site:

- It does **not** touch prod's live traffic. The real site still flows through Ondra's
  manually-created CloudFront (managed outside this CDK); DNS is unchanged. A ``cdk
  deploy`` *creates* this distribution and never deletes or adopts the manual one —
  CloudFormation only manages what it created.
- **No alias on purpose.** CloudFront refuses the same CNAME on two distributions, and
  no alias means no DNS conflict. Attaching ``one-tenovice.cz`` + an ACM cert and adding
  response-header / WAF hardening (WAF WebACL bound to *this* CDK distribution, prod-only,
  D21) is the later *wiring* step — a deliberate DNS cutover done once there is time. (The
  OAC/private-bucket switch on prod is already done here, so the bucket stays locked down.)

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

        # Origin depends on the bucket's exposure (s3_website.py):
        # - dev  → the public S3 *website* endpoint (HTTP, public-read), matching how the
        #          dev site is served today.
        # - prod → the private bucket via **Origin Access Control** (REST endpoint). The
        #          prod bucket has public access blocked + no website hosting, so the website
        #          endpoint is gone; OAC is the only way in. CDK auto-adds this distribution's
        #          read grant to the bucket policy (on top of the manual distribution's grant
        #          codified in s3_website.py), so the private bucket ends up allowing both.
        # Prod traffic still flows through the manually-created CloudFront — this skeleton stays
        # dark; the OAC switch just keeps it functional (and ready for a later domain cutover).
        if config.stage == "prod":
            origin = origins.S3BucketOrigin.with_origin_access_control(website_bucket)
        else:
            origin = origins.S3StaticWebsiteOrigin(website_bucket)

        self.distribution = cloudfront.Distribution(
            self,
            "Distribution",
            comment=f"{config.project_name}-{config.stage} (skeleton — not wired to a domain yet)",
            default_root_object="index.html",
            default_behavior=cloudfront.BehaviorOptions(
                origin=origin,
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
