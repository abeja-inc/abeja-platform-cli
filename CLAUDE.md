# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ABEJA Platform CLI (`abejacli`) is a command-line interface tool for the ABEJA Platform, providing unified access to various platform services including datasets, models, training, datalake, and more.

## Development Commands

### Setup
```bash
# Install dependencies using Poetry
poetry install

# Configure pre-commit hooks (runs fmt, lint, and test automatically)
poetry run pre-commit install
```

### Common Development Commands
```bash
# Run CLI locally
poetry run python -m abejacli.run

# Run tests with coverage
make test

# Run specific tests in parallel (default: auto)
NUM_TEST_PROCESS=4 make test

# Run integration tests
make integration_test

# Format code (automatically fixes formatting issues)
make fmt

# Check formatting without making changes
make check-fmt

# Run linter (flake8)
make lint

# Build wheel distribution
make dist

# Clean build artifacts
make clean
```

### Testing
```bash
# Run unit tests with pytest in parallel
poetry run pytest -v -n auto --cov=abejacli tests/unit

# Run a single test file
poetry run pytest tests/unit/path/to/test_file.py

# Run integration tests (requires platform credentials)
poetry run pytest tests/integration --cov=abejacli tests/integration
```

## Code Architecture

### Core Structure
- **`abejacli/run.py`**: Main entry point for the CLI application, orchestrates all commands and subcommands using Click framework
- **`abejacli/session.py`**: Handles API authentication and HTTP requests to the ABEJA Platform API
- **`abejacli/configuration/`**: Manages user configuration and credentials stored in `~/.abeja/config`
- **`abejacli/click_custom.py`**: Custom Click types and validators for CLI arguments

### Service Modules
Each service has its own directory with a consistent structure:
- **`bucket/`**: S3-compatible bucket operations (upload/download)
- **`dataset/`**: Dataset management commands
- **`datalake/`**: Data lake file operations
- **`training/`**: Training job management
- **`model/`**: Model deployment and local testing
- **`registry/`**: Docker registry operations
- **`secret/`** & **`secret_version/`**: Secret management
- **`labs/`**: Experimental features and integration services
- **`dx_template/`**: Template management
- **`startapp/`**: Application scaffolding

### Docker Integration
- **`abejacli/docker/`**: Contains Docker-related functionality for running models locally
- Uses Docker SDK for Python to manage containers
- Supports local model testing with `ModelRunCommand`

### Configuration Management
The CLI uses a hierarchical configuration system:
1. Default values in `abejacli/config.py`
2. User configuration from `~/.abeja/config` (JSON format)
3. Environment variables (e.g., `ABEJA_API_URL`, `PERSONAL_ACCESS_TOKEN`)

### API Communication Pattern
All API calls follow this pattern:
1. Load configuration via `ConfigSet` and `ConfigSetLoader`
2. Use session functions (`api_get`, `api_post`, etc.) from `session.py`
3. Format responses using formatters in each module
4. Handle retries automatically for transient failures

## Environment Variables

Key environment variables that override configuration:
- `ABEJA_API_URL`: Base URL for platform API (default: production API)
- `ABEJA_PLATFORM_USER`: Platform user ID
- `PERSONAL_ACCESS_TOKEN`: Authentication token
- `ORGANIZATION_NAME`: Default organization name

## Python Version Support

Supports Python 3.8, 3.9, 3.10, and 3.11 (as specified in `pyproject.toml`)

## Pre-commit Hooks

The repository uses pre-commit hooks that automatically run:
1. `make fmt`: Code formatting (isort, autopep8, autoflake)
2. `make lint`: Linting with flake8
3. `make test`: Unit tests with pytest

These run automatically on git commit if configured with `poetry run pre-commit install`.

## Release Process

Uses git-flow for release management. See README.md for detailed release instructions including version bumping and CircleCI deployment.