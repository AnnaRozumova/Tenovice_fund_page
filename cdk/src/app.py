"""Docstring"""
import os

import aws_cdk as cdk
from .stack import FundraisingCalculatorStack

app = cdk.App()

# Bind the stack to the account/region CDK is being run against (the standard
# CDK_DEFAULT_* the CLI/pipeline exports at deploy) instead of leaving it
# environment-agnostic. `.get()` keeps synth working locally when they are unset
# (env stays None → agnostic, as before), but a real deploy is now pinned to a
# concrete account so retention/data-loss decisions can't drift to the wrong one.
env = cdk.Environment(
    account=os.environ.get("CDK_DEFAULT_ACCOUNT"),
    region=os.environ.get("CDK_DEFAULT_REGION"),
)

FundraisingCalculatorStack(app, "FundraisingCalculatorStack", env=env)

app.synth()
