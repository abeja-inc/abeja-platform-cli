NAME=abejacli

requirements.txt: Pipfile
	pipenv run python pipfile-to-requirements.py > requirements.txt

.PHONY: build install clean dist uninstall test prepare_ci integration_test lint fmt release

build: requirements.txt
	pipenv run python setup.py build

install: clean build
	pipenv run python setup.py install --force

clean: requirements.txt
	pipenv run python setup.py clean

dist: clean
	pipenv run python setup.py bdist_wheel --universal

uninstall:
	pip uninstall $(NAME)

test: lint
	pipenv run pytest tests/unit --cov=abejacli tests/unit

prepare_ci:
	mkdir -p ~/.abeja
	echo '{"personal-access-token": "$(PLATFORM_USER_TOKEN)", "abeja-platform-user": "$(PLATFORM_USER_ID)", "organization-name": "$(PLATFORM_ORG)"}' >> ~/.abeja/config

integration_test:
	pipenv run pytest tests/integration --cov=abejacli tests/integration

lint:
	pipenv run flake8 abejacli tests --max-line-length=120 --max-complexity=25 --ignore E402,E121

fmt:
	pipenv run autopep8 -i -r abejacli tests --max-line-length=120 --exclude=abejacli/template/*
	pipenv run autoflake -i -r abejacli tests --remove-all-unused-imports --remove-unused-variables --exclude=abejacli/template/*

release: dist
	# package_cloud is installed via RubyGems, so we don't execute it with pipenv.
	package_cloud push abeja/platform-public/python ./dist/abejacli-*-py2.py3-none-any.whl
