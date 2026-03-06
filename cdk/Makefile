SHELL := /bin/bash

.PHONY: help install synth diff deploy destroy bootstrap fmt lint

help:
	@echo "Targets:"
	@echo "  install    Install infra deps"
	@echo "  synth      Synthesize CloudFormation template"
	@echo "  diff       Show diff against deployed stack"
	@echo "  deploy     Deploy stack to AWS"
	@echo "  destroy    Destroy stack in AWS"
	@echo "  bootstrap  CDK bootstrap for this account/region"
	@echo "  fmt        Format python (ruff)"
	@echo "  lint       Lint python (ruff)"

install:
	python -m pip install -U pip
	python -m pip install -e .

bootstrap:
	cdk bootstrap

synth:
	cdk synth

diff:
	cdk diff

deploy:
	cdk deploy

destroy:
	cdk destroy

fmt:
	python -m pip install -U ruff
	ruff format src

lint:
	python -m pip install -U ruff
	ruff check src