NUM_TEST_PROCESS ?= auto
FMT_TARGET ?= .

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
	poetry run isort -sl $(FMT_TARGET)
	poetry run autopep8 -i -r --max-line-length=120 --exclude=abejacli/template/* $(FMT_TARGET)
	poetry run autoflake -i -r --remove-all-unused-imports --remove-unused-variables $(FMT_TARGET)
	poetry run isort -m 3 $(FMT_TARGET)

check-fmt:
	poetry run isort --check-only .

release: dist
	poetry publish -u ${TWINE_USERNAME} -p ${TWINE_PASSWORD}
