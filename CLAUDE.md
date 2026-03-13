# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A fundraising calculator application built with AWS CDK (Python) and Lambda functions. Currently implements a statistics endpoint for tracking pledge data stored in DynamoDB.

## Development Commands

All commands should be run from the project root unless otherwise specified.

### Infrastructure (CDK)

```bash
# Install CDK dependencies
make infra-install

# Bootstrap AWS account/region (first-time setup)
make infra-bootstrap

# Synthesize CloudFormation template
make infra-synth

# Show diff against deployed stack
make infra-diff

# Deploy to AWS
make infra-deploy

# Destroy stack
make infra-destroy
```

### CDK-specific (from cdk/ directory)

```bash
cd cdk

# Format Python code with ruff
make fmt

# Lint Python code with ruff
make lint
```

### Testing

```bash
# Run all tests
make test

# Run unit tests only
make test-unit

# Run integration tests only
make test-integration

# Run tests with coverage report
make test-coverage
```

For E2E tests against deployed API:
```bash
export API_URL="https://your-api-id.execute-api.region.amazonaws.com"
cd tests
pip install -r requirements-e2e.txt
pytest e2e/ -v
```

## Architecture

The application uses a modular CDK construct pattern:

- **Stack** (`cdk/src/stack.py`): Main stack that orchestrates all constructs
- **Config** (`cdk/src/constructs/config.py`): Reads configuration from `cdk.json` context
- **DynamoDb** (`cdk/src/constructs/dynamodb.py`): Creates the Pledges table with partition key `pledgeID`
- **Lambdas** (`cdk/src/constructs/lambdas.py`): Defines Lambda functions and grants DynamoDB permissions
- **Api** (`cdk/src/constructs/apigw.py`): Creates API Gateway V2 (HTTP API) with CORS and route integrations

### Data Flow

1. Lambda functions are sourced from `services/pledges_api/src/`
2. Lambda code is packaged during CDK synth/deploy
3. API Gateway routes requests to Lambda integrations
4. Lambdas interact with DynamoDB table (name passed via environment variable `PLEDGES_TABLE_NAME`)

### Current Implementation Status

All API endpoints are fully implemented and wired up:
- **GET /stats** - Get aggregated statistics
- **POST /pledges** - Create a new pledge
- **GET /pledges/{pledgeID}** - Get a specific pledge by ID
- **PUT /pledges/{pledgeID}** - Update a specific pledge

## Configuration

Configuration is managed via CDK context in `cdk/cdk.json`:

- `stage`: Deployment stage (default: "dev")
- `project_name`: Project prefix for resource names (default: "fundraising-calculator")
- `api_name`: API Gateway name (default: "fundraising-api")
- `pledges_table_name`: DynamoDB table suffix (default: "Pledges")

Override context values using `cdk deploy --context key=value` or by modifying `cdk.json`.

### Environment-specific Behavior

- **dev stage**: DynamoDB table uses `RemovalPolicy.DESTROY` (table deleted on stack deletion)
- **other stages**: DynamoDB table uses `RemovalPolicy.RETAIN` (table preserved on stack deletion)

## Adding New Lambda Handlers

To add a new Lambda function:

1. Create handler in `services/pledges_api/src/handlers/`
2. Add function definition to `LambdasConstruct` in `cdk/src/constructs/lambdas.py`
3. Add function to `LambdaHandlers` dataclass (set Optional if not always present)
4. Grant necessary DynamoDB permissions (e.g., `table.grant_read_data()`, `table.grant_write_data()`)
5. Add API route in `ApiConstruct` in `cdk/src/constructs/apigw.py`
6. Update CORS methods in `apigw.py` if adding POST/PUT/DELETE

## DynamoDB Schema

Table name: `{project_name}-{stage}-{pledges_table_name}`

- Partition key: `pledgeID` (String)
- Special record: `pledgeID="STATS"` stores aggregate statistics:
  - `pledged_total`: Total amount pledged (number)
  - `pledgers_count`: Number of unique pledgers (number)
  - `monthly_total`: Monthly recurring total (number)
  - `updated_at`: Timestamp of last update (string)

Regular pledge records contain:
- `pledgeID`: Unique identifier (UUID)
- `name`: Pledger name (2-100 chars)
- `email`: Pledger email (normalized to lowercase)
- `amount`: Pledge amount (1-1,000,000)
- `is_monthly`: Boolean indicating if monthly recurring
- `created_at`: ISO timestamp
- `updated_at`: ISO timestamp (only present after updates)
- `message`: Optional message (max 500 chars)

## Testing

Test structure:
- `services/pledges_api/tests/unit/` - Unit tests (no AWS dependencies)
- `services/pledges_api/tests/integration/` - Integration tests (mocked AWS via moto)
- `tests/e2e/` - End-to-end tests (against deployed API)

See `TESTING_PLAN.md` for detailed testing strategy and `services/pledges_api/tests/README.md` for test setup instructions.
