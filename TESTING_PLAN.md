# Testing Plan

## Overview

This document outlines the testing strategy for the fundraising calculator application, covering unit tests, integration tests, and end-to-end tests.

## Testing Layers

### 1. Unit Tests (Priority: High)

Test individual components in isolation without AWS dependencies.

**What to test:**
- `domain/models.py`: Pledge model conversion methods
- `domain/validation.py`: Input validation logic
- Response formatting

**Framework:** pytest

**Setup:**
```bash
cd services/pledges_api
python -m pip install pytest pytest-cov
```

**Test structure:**
```
services/pledges_api/
├── src/
│   ├── domain/
│   ├── handlers/
│   └── utils/
└── tests/
    ├── unit/
    │   ├── test_models.py
    │   ├── test_validation.py
    │   └── test_response.py
    └── integration/
        ├── test_create_pledge.py
        ├── test_get_pledge.py
        ├── test_update_pledge.py
        └── test_get_stats.py
```

**Run command:**
```bash
pytest tests/unit/ -v
```

### 2. Integration Tests (Priority: High)

Test Lambda handlers with mocked AWS services (DynamoDB).

**Framework:** pytest + moto (AWS mocking library)

**Setup:**
```bash
python -m pip install pytest moto boto3
```

**What to test:**
- Each Lambda handler with various inputs
- Success cases
- Error cases (validation failures, not found, server errors)
- Edge cases (empty STATS record, special characters in fields)

**Run command:**
```bash
pytest tests/integration/ -v
```

### 3. CDK Infrastructure Tests (Priority: Medium)

Test CDK stack synthesis and resource configuration.

**Framework:** pytest + aws-cdk-lib assertions

**Setup:**
```bash
cd cdk
python -m pip install pytest
```

**Test structure:**
```
cdk/
├── src/
└── tests/
    ├── test_stack.py
    └── test_constructs.py
```

**What to test:**
- Stack synthesizes without errors
- Correct number of Lambda functions created
- DynamoDB table has correct configuration
- API Gateway has correct routes
- IAM permissions are properly configured

**Run command:**
```bash
cd cdk
pytest tests/ -v
```

### 4. API End-to-End Tests (Priority: Medium)

Test the deployed API endpoints with real HTTP requests.

**Tools:** pytest + requests library

**Setup:**
```bash
python -m pip install pytest requests
```

**Test structure:**
```
tests/
└── e2e/
    ├── test_api_pledges.py
    └── test_api_stats.py
```

**What to test:**
- Full pledge lifecycle (create → get → update → get)
- Stats endpoint returns correct data after pledges created
- CORS headers present
- Error responses

**Run command:**
```bash
export API_URL="https://your-api-id.execute-api.region.amazonaws.com"
pytest tests/e2e/ -v
```

### 5. Manual Testing (Priority: Low/Ongoing)

Use curl or Postman for exploratory testing.

**Example curl commands:**

```bash
# Set your API URL
API_URL="https://your-api-id.execute-api.region.amazonaws.com"

# Get stats
curl -X GET "$API_URL/stats"

# Create pledge
curl -X POST "$API_URL/pledges" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "John Doe",
    "email": "john@example.com",
    "amount": 100,
    "is_monthly": true,
    "message": "Great cause!"
  }'

# Get pledge (replace PLEDGE_ID)
curl -X GET "$API_URL/pledges/PLEDGE_ID"

# Update pledge (replace PLEDGE_ID)
curl -X PUT "$API_URL/pledges/PLEDGE_ID" \
  -H "Content-Type: application/json" \
  -d '{
    "amount": 150
  }'
```

## Test Data Strategy

### Mock Data for Unit/Integration Tests
- Valid pledges with various field combinations
- Invalid inputs (missing fields, wrong types, out of range values)
- Edge cases (empty strings, very long strings, special characters)

### Test Data for E2E Tests
- Use unique identifiers (timestamps, UUIDs) to avoid conflicts
- Clean up test data after tests complete (optional DELETE endpoint)
- Consider separate test environment/stage

## CI/CD Integration (Future)

### GitHub Actions Workflow (Example)

```yaml
name: Test

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          cd services/pledges_api
          pip install pytest pytest-cov moto boto3

      - name: Run unit tests
        run: |
          cd services/pledges_api
          pytest tests/unit/ -v --cov=src --cov-report=term

      - name: Run integration tests
        run: |
          cd services/pledges_api
          pytest tests/integration/ -v

      - name: Test CDK synth
        run: |
          cd cdk
          pip install -e .
          cdk synth
```

## Implementation Priority

1. **Phase 1 (Critical):**
   - Unit tests for validation logic
   - Integration tests for create_pledge handler
   - Manual testing setup

2. **Phase 2 (Important):**
   - Integration tests for remaining handlers
   - Unit tests for models
   - E2E tests for happy path

3. **Phase 3 (Nice to have):**
   - CDK infrastructure tests
   - E2E tests for error cases
   - Load testing

## Coverage Goals

- **Unit tests:** 80%+ coverage of business logic
- **Integration tests:** All handlers covered with success and failure cases
- **E2E tests:** Critical user flows tested

## Load Testing (Optional)

For performance testing, consider:

**Tools:** Apache JMeter, Locust, or Artillery

**Scenarios:**
- Concurrent pledge creation
- Stats endpoint under load
- Burst traffic patterns

## Notes

- DynamoDB stats update in create_pledge is not atomic; consider testing race conditions
- STATS record should be initialized before tests that read it
- Consider using DynamoDB Local or LocalStack for offline testing
- Lambda cold start times should be measured in E2E tests
