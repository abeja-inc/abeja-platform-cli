# abeja-cli

This package provides a unified command line interface to ABEJA Platform.

[![CircleCI](https://circleci.com/gh/abeja-inc/abeja-platform-cli/tree/master.svg?style=svg)](https://circleci.com/gh/abeja-inc/abeja-platform-cli/tree/master)

[![python3.6](https://img.shields.io/badge/python-3.6-blue.svg?style=flat-square)]()

# Development

## Setup

```sh
$ poetry install

# configure pre-commit
$ poetry run pre-commit install

# install git-flow
$ brew install git-flow-avh # for macOS
$ apt-get install git-flow # for Linux
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
Synchronize master and develop branch.

```bash
$ git checkout master
$ git pull
$ git checkout develop
$ git pull
```

Create release branch and prepare for release.

```bash
$ git flow release start X.X.X
$ vim CHANGELOG.md
# update to new version
$ poetry version X.X.X
$ git add pyproject.toml
$ git add CHANGELOG.md
$ git commit -m "bump version"
$ git flow release publish X.X.X
```

After pushing to relase branch, RC package is published to packagecloud.

Check CircleCI result.
If the build succeeded then execute:

```bash
$ git flow release finish X.X.X
$ git push origin develop
$ git push origin master
$ git push origin X.X.X
```

## Environment Vars

By specifying environment variables, you can overwrite the constant variables, or variables already configured.

| Key                     | description                          | Example                                                    |
| ----------------------- | ------------------------------------ | ---------------------------------------------------------- |
| `ABEJA_API_URL`         | base url of platform to request      | `https://api.dev.abeja.io`                                 |
| `SAMPLE_MODEL_PATH`     | path to url of s3 bucket             | `https://s3-us-west-2.amazonaws.com/abeja-platform-config` |
| `ABEJA_PLATFORM_USER`   | platform user id to overwrite        | `1234567890123`                                            |
| `PERSONAL_ACCESS_TOKEN` | platform personal token to overwrite | `some_token`                                               |
| `ORGANIZATION_NAME`     | organization name to overwrite       | `some_org`                                                 |
