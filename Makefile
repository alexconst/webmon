.PHONY: FORCE help args venv depsdevdb depsdevdbrun depsdev deps run profiling lint tests tests-unit tests-integration tests-smoke debug

# running make with no targets will run the first target (in this case "help")
# this help menu
help:
	@cat $(MAKEFILE_LIST) | grep -E -v '^args:' | grep -B 1 '^[a-z\-]*:' | sed 's/\(^[^#].*\):.*/\1/g' | sed 's/\([^#]\)--/\1XXDEADBEEFXX/g' | awk 'BEGIN {RS="--\n?"; FS="\n"} {printf "\033[36m%-20s\033[0m %s\n", $$2, $$1}' | sed 's/XXDEADBEEFXX/--/g'

args:
# if the first argument is "run" then pass any other arguments to the app
# https://stackoverflow.com/questions/2214575/passing-arguments-to-make-run
# NOTE: to pass --option you need to run it this way: make run -- --option
#$(info "HEY DEBUG: $(RUN_ARGS)")
ifeq (run,$(firstword $(MAKECMDGOALS)))
# use the rest as arguments for "run"
RUN_ARGS := $(wordlist 2,$(words $(MAKECMDGOALS)),$(MAKECMDGOALS))
# ...and turn them into do-nothing targets
$(foreach arg,$(RUN_ARGS),$(eval $(arg): FORCE; @:))
endif


APP=src/webmoncli.py
DEF_ARGS=
CMD_RUN=python $(APP) $(DEF_ARGS) $(RUN_ARGS)
CMD_PROFILING=python -mcProfile -o app.prof $(APP) $(DEF_ARGS) $(RUN_ARGS)
PYTHON_SRC=src
PYTHON_TESTS=tests
PYTHON_DIRS=$(PYTHON_SRC) $(PYTHON_TESTS)


# create python virtual env
venv:
	( \
		test -d venv || python3 -m venv venv ;\
		[ -n "$$VIRTUAL_ENV" ] || . venv/bin/activate ;\
		pip install wheel ;\
	)
# regarding wheel see https://github.com/pypa/pip/issues/8102#issuecomment-619528947

# install python development dependencies
depsdev:
	( \
		[ -n "$$VIRTUAL_ENV" ] || . venv/bin/activate ;\
		pip install -r requirements-dev.txt ;\
	)

# install python runtime dependencies
deps:
	( \
		[ -n "$$VIRTUAL_ENV" ] || . venv/bin/activate ;\
		pip install -r requirements.txt ;\
	)

# pull postgresql docker image and generate config
depsdevdb:
	$(eval POSTGRES_USER = 'pgadmin')
	$(eval POSTGRES_PASSWORD = $(shell tr -dc 'A-Za-z0-9+,-./:;' </dev/urandom | head -c "12"; echo ''))
	$(eval POSTGRES_DB = 'defaultdb')
	$(eval PGHOST = 'localhost')
	$(eval PGPORT = '5432')
	@echo '{\n    "db_type": "postgresql",\n    "db_user": "'$(POSTGRES_USER)'",\n    "db_pass": "'"$(POSTGRES_PASSWORD)"'",\n    "db_name": "'$(POSTGRES_DB)'",\n    "db_host": "'$(PGHOST)'",\n    "db_port": "'$(PGPORT)'",\n    "db_ssl":  "disable"\n}' > 'secrets/db_postgresql_container.json'
	docker pull postgres:17.4-bookworm

# spin docker postgresql container using existing config
depsdevdbrun:
	@( \
		export $$(jq -r 'to_entries|map("\(.key)=\(.value)")|.[]' secrets/db_postgresql_container.json) ;\
		docker run --name postgres-webmon -p 127.0.0.1:5432:5432 --memory="512m" --shm-size="256m" -e POSTGRES_PASSWORD="$$db_pass" -e POSTGRES_USER="$$db_user" -e POSTGRES_DB="$$db_name" -d postgres:17.4-bookworm ;\
		docker ps --filter "name=postgres-webmon" ;\
	)
	@sleep 3s
	@nc -4 -zv localhost 5432

# run the application using pre-defined parameters; to add extra ones do: make run -- 'opt1 --opt2 a=x'
run: args
	@#echo $(CMD_RUN)
	@( \
		[ -n "$$VIRTUAL_ENV" ] || . venv/bin/activate ;\
		$(CMD_RUN) ;\
	)

# profile the application
profiling: args
	@( \
		[ -n "$$VIRTUAL_ENV" ] || . venv/bin/activate ;\
		$(CMD_PROFILING) ;\
		tuna app.prof ;\
	)


# run auto-formaters, linters, static analyzers
lint:
	@( \
		[ -n "$$VIRTUAL_ENV" ] || . venv/bin/activate ;\
		isort --settings-file pyproject.toml $(PYTHON_DIRS) ;\
		yapf --style=pyproject.toml --recursive --in-place $(PYTHON_DIRS) ;\
		pylint --rcfile pyproject.toml $(PYTHON_SRC) ;\
		pylint --rcfile pyproject.toml $(PYTHON_TESTS) ;\
		mypy --show-error-codes $(PYTHON_SRC) ;\
	)

#		black --config pyproject.toml $(PYTHON_DIRS) ;\


# update README.md TOC
docs:
	@which github_markdown_toc.sh >/dev/null || (echo 'Tool for generating the markdown TOC not found' ; exit 1)
	@github_markdown_toc.sh --insert README.md

# run all tests
tests: tests-unit tests-integration tests-smoke


# run unit tests using pytest
tests-unit:
	@( \
		[ -n "$$VIRTUAL_ENV" ] || . venv/bin/activate ;\
		pytest -s -v --log-level=DEBUG tests/unit ;\
	)

# run integration tests using pytest
tests-integration:
	@( \
		[ -n "$$VIRTUAL_ENV" ] || . venv/bin/activate ;\
		pytest -s -v --log-level=DEBUG tests/integration ;\
	)

# run smoke tests using pytest
tests-smoke:
	@( \
		[ -n "$$VIRTUAL_ENV" ] || . venv/bin/activate ;\
		pytest -s -v --log-level=DEBUG tests/smoke;\
	)

# run tests and start pdb when a test fails
debug:
	@( \
		[ -n "$$VIRTUAL_ENV" ] || . venv/bin/activate ;\
		pytest -s -v --log-level=DEBUG --pdb tests/unit tests/integration ;\
	)

# catch unmatched rules (which are triggered when passing extra options to run) to do nothing
%:
	@echo "No such target in the Makefile: $@"

