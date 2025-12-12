# abeja-cli

This package provides a unified command line interface to ABEJA Platform.

[![CircleCI](https://circleci.com/gh/abeja-inc/abeja-platform-cli/tree/master.svg?style=svg)](https://circleci.com/gh/abeja-inc/abeja-platform-cli/tree/master)

[![python3.9](https://img.shields.io/badge/python-3.9-blue.svg?style=flat-square)]()

# Development

## Setup

```sh
$ poetry install

# configure pre-commit
$ poetry run pre-commit install

```

## Run command locally

```bash
$ poetry run python -m abejacli.run
```

## Test

```sh
$ make test
```

## Release

### Deploy to Development Environment

When creating a PR from `feature/xxx` to `develop` branch, include version updates in the PR:
- Update `CHANGELOG.md`: Add your changes to the latest version section (do not create a new version section if the current version hasn't been released to staging yet)
- Update `pyproject.toml` version (e.g., `2.2.7` → `2.2.8`)

> **Note**: If the current version in `pyproject.toml` has never been released to staging, you don't need to create a new version section in `CHANGELOG.md` or update `pyproject.toml`. Instead, add your changes to the existing latest version section in `CHANGELOG.md`. Only create a new version section and update `pyproject.toml` when the previous version has been released to staging. Alternatively, update the version only when creating a PR to `staging` to avoid version gaps in PyPI releases.

Then create a PR and merge from `feature/xxx` to `develop` branch.

### Deploy to Staging Environment

Create a PR and merge from `develop` to `staging` branch.

After pushing to staging branch, RC package is automatically published to PyPI with the next available RC version (e.g., `2.2.8rc1`, `2.2.8rc2`, ...). The RC version number is automatically determined by querying PyPI for existing RC versions.

### Deploy to Production Environment

Create a PR and merge from `staging` to `master` branch.

After pushing to master branch, the final package (e.g., `2.2.8`) is published to PyPI.

## Environment Vars

By specifying environment variables, you can overwrite the constant variables, or variables already configured.

| Key                     | description                          | Example                                                    |
| ----------------------- | ------------------------------------ | ---------------------------------------------------------- |
| `ABEJA_API_URL`         | base url of platform to request      | `https://api.dev.abeja.io`                                 |
| `SAMPLE_MODEL_PATH`     | path to url of s3 bucket             | `https://s3-us-west-2.amazonaws.com/abeja-platform-config` |
| `ABEJA_PLATFORM_USER`   | platform user id to overwrite        | `1234567890123`                                            |
| `PERSONAL_ACCESS_TOKEN` | platform personal token to overwrite | `some_token`                                               |
| `ORGANIZATION_NAME`     | organization name to overwrite       | `some_org`                                                 |
