"""S3 static website hosting construct"""
from constructs import Construct
from aws_cdk import (
    aws_s3 as s3,
    aws_s3_deployment as s3deploy,
    RemovalPolicy,
    CfnOutput,
)

from .config import AppConfig


class S3WebsiteConstruct(Construct):
    def __init__(self, scope: Construct, construct_id: str, *, config: AppConfig) -> None:
        super().__init__(scope, construct_id)

        # Create S3 bucket for static website
        self.website_bucket = s3.Bucket(
            self,
            "WebsiteBucket",
            bucket_name=f"{config.project_name}-{config.stage}-website",
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

        # Deploy website files
        s3deploy.BucketDeployment(
            self,
            "DeployWebsite",
            sources=[s3deploy.Source.asset("../web")],
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
