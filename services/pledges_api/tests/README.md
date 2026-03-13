# Tests

This directory contains tests for the pledges API Lambda functions.

## Setup

Install test dependencies:

```bash
pip install -r requirements-test.txt
```

## Running Tests

### All tests
```bash
pytest
```

### Unit tests only
```bash
pytest tests/unit/ -v
```

### Integration tests only
```bash
pytest tests/integration/ -v
```

### With coverage report
```bash
pytest --cov=src --cov-report=html --cov-report=term
```

View coverage report:
```bash
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
```

## Test Structure

- `unit/` - Unit tests for models, validation, and utilities (no AWS dependencies)
- `integration/` - Integration tests for Lambda handlers (uses moto for AWS mocking)

## Writing New Tests

### Unit Test Example

```python
import sys
sys.path.insert(0, '../../src')

from domain.validation import validate_pledge_input

def test_something():
    # Your test here
    pass
```

### Integration Test Example

```python
import pytest
from moto import mock_aws
import boto3

@pytest.fixture
def dynamodb_table():
    with mock_aws():
        # Setup mock resources
        yield table

def test_handler(dynamodb_table):
    # Your test here
    pass
```
