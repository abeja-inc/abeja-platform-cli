NUM_TEST_PROCESS ?= auto

.PHONY: build install clean dist uninstall test prepare_ci integration_test lint fmt release

build:
	poetry run python setup.py build

clean:
	rm -rf dist

dist: clean
	pip install wheel==0.31.1
	poetry build -f wheel

test: lint
	poetry run pytest -v -n ${NUM_TEST_PROCESS} --cov=abejacli tests/unit

prepare_ci:
	mkdir -p ~/.abeja
	echo '{"personal-access-token": "$(PLATFORM_USER_TOKEN)", "abeja-platform-user": "$(PLATFORM_USER_ID)", "organization-name": "$(PLATFORM_ORG)"}' >> ~/.abeja/config

integration_test:
	poetry run pytest tests/integration --cov=abejacli tests/integration

lint: check-fmt
	poetry run flake8 abejacli tests --max-line-length=120 --max-complexity=25 --ignore E402,E121

fmt:
	poetry run isort -rc -sl .
	poetry run autopep8 -i -r abejacli tests --max-line-length=120 --exclude=abejacli/template/*
	poetry run autoflake -i -r abejacli tests --remove-all-unused-imports --remove-unused-variables
	poetry run isort -rc -m 3 .

check-fmt:
	poetry run isort --check-only .

release: dist
	poetry publish -u ${TWINE_USERNAME} -p ${TWINE_PASSWORD}
