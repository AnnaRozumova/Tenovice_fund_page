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
- **S3Website** (`cdk/src/constructs/s3_website.py`): Creates S3 bucket configured for static website hosting and deploys web files

### Data Flow

1. Lambda functions are sourced from `services/pledges_api/src/`
2. Lambda code is packaged during CDK synth/deploy
3. API Gateway routes requests to Lambda integrations
4. Lambdas interact with DynamoDB table (name passed via environment variable `PLEDGES_TABLE_NAME`)

### Current Implementation Status

The API has been simplified to 3 endpoints:
- **GET /stats** - Get aggregated statistics
- **POST /pledges** - Upsert a pledge (create or update by email)
- **GET /pledges** - List all pledges anonymously

### Email-Based Upsert Pattern

The application uses email as the unique identifier for pledges:
- **First submission:** Creates a new pledge
- **Subsequent submissions with same email:** Updates the existing pledge
- Stats are automatically adjusted (delta calculation for updates)
- No tokens or authentication required - email is the key

### Anonymity and Privacy

**Data storage:**
- Name and email are stored in DynamoDB (for internal use/contact)
- GSI (Global Secondary Index) on email field enables upsert by email

**Public APIs:**
- All public endpoints (GET /pledges, GET /pledges/{id}) return ONLY anonymous data
- Personal information (name, email) is NEVER exposed
- Public responses include: amount, is_monthly, created_at, updated_at, message

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

**Primary key:**
- Partition key: `pledgeID` (String, UUID)

**Global Secondary Index (GSI):**
- Index name: `EmailIndex`
- Partition key: `email` (String)
- Enables upsert by email (query existing pledge before create/update)

**Special record:** `pledgeID="STATS"` stores aggregate statistics:
- `pledged_total`: Total amount pledged (number)
- `pledgers_count`: Number of unique pledgers (number)
- `monthly_total`: Monthly recurring total (number)
- `updated_at`: Timestamp of last update (string)

**Regular pledge records contain:**
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

## Frontend / Static Website

**Location:** `web/` directory

The frontend is a plain HTML/CSS/JS static website hosted on S3:
- No build tools required (no npm, no Vite)
- Automatically deployed via CDK when you run `make infra-deploy`
- Files are uploaded from `web/` directory to S3 bucket

**Configuration:** Edit `web/config.js`:
- `API_URL` - Your API Gateway endpoint
- `CURRENT_BALANCE` - Real money on account (hardcoded)
- `FUNDRAISING_GOAL` - Target amount (hardcoded)

**S3 Bucket:**
- Bucket name: `{project_name}-{stage}-website`
- Configured for static website hosting
- Public read access enabled
- Website URL output after deployment

**To update website after changes:**
```bash
make infra-deploy  # Redeploys everything including website files
```

Or manually sync files:
```bash
aws s3 sync web/ s3://fundraising-calculator-dev-website --delete
```
