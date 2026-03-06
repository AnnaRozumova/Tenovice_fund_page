"""Docstring"""
import aws_cdk as cdk
from .stack import FundraisingCalculatorStack

app = cdk.App()

FundraisingCalculatorStack(app, "FundraisingCalculatorStack")

app.synth()
