SHELL := /bin/bash

.PHONY: help infra-install infra-synth infra-diff infra-deploy infra-destroy infra-bootstrap test test-unit test-integration test-coverage

help:
	@echo "Targets:"
	@echo "  infra-install     Install CDK dependencies"
	@echo "  infra-bootstrap   CDK bootstrap"
	@echo "  infra-synth       CDK synth"
	@echo "  infra-diff        CDK diff"
	@echo "  infra-deploy      CDK deploy"
	@echo "  infra-destroy     CDK destroy"
	@echo "  test              Run all tests"
	@echo "  test-unit         Run unit tests only"
	@echo "  test-integration  Run integration tests only"
	@echo "  test-coverage     Run tests with coverage report"

infra-install:
	$(MAKE) -C cdk install

infra-bootstrap:
	$(MAKE) -C cdk bootstrap

infra-synth:
	$(MAKE) -C cdk synth

infra-diff:
	$(MAKE) -C cdk diff

infra-deploy:
	$(MAKE) -C cdk deploy

infra-destroy:
	$(MAKE) -C cdk destroy

test:
	cd services/pledges_api && python -m pytest tests/ -v

test-unit:
	cd services/pledges_api && python -m pytest tests/unit/ -v

test-integration:
	cd services/pledges_api && python -m pytest tests/integration/ -v

test-coverage:
	cd services/pledges_api && python -m pytest tests/ -v --cov=src --cov-report=html --cov-report=term