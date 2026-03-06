SHELL := /bin/bash

.PHONY: help infra-install infra-synth infra-diff infra-deploy infra-destroy infra-bootstrap

help:
	@echo "Targets:"
	@echo "  infra-install     Install CDK dependencies"
	@echo "  infra-bootstrap   CDK bootstrap"
	@echo "  infra-synth       CDK synth"
	@echo "  infra-diff        CDK diff"
	@echo "  infra-deploy      CDK deploy"
	@echo "  infra-destroy     CDK destroy"

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