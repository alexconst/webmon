.PHONY: FORCE help _args py-venv py-deps py-depsdev db-cfg db-run db-del app-run app-profile app-debug lint tests tests-unit tests-integration tests-smoke docker-deploy docker-destroy ci-push _ci-push

SHELL := /bin/bash

# running make with no targets will run the first target (in this case "help")
# any build targets starting with an underscore are internal and ignored by the help menu
# this help menu
help:
	@cat $(MAKEFILE_LIST) | grep -E -v '^_' | grep -B 1 '^[a-z\-]*:' | sed 's/\(^[^#].*\):.*/\1/g' | sed 's/\([^#]\)--/\1XXDEADBEEFXX/g' | awk 'BEGIN {RS="--\n?"; FS="\n"} {printf "\033[36m%-20s\033[0m %s\n", $$2, $$1}' | sed 's/XXDEADBEEFXX/--/g'

_args:
# if the first argument is "run" then pass any other arguments to the app
# https://stackoverflow.com/questions/2214575/passing-arguments-to-make-run
# NOTE: to pass --option you need to run it this way: make run -- --option
#$(info "HEY DEBUG: $(RUN_ARGS)")
ifeq (app-run,$(firstword $(MAKECMDGOALS)))
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
py-venv:
	( \
		test -d venv || python3 -m venv venv ;\
		[ -n "$$VIRTUAL_ENV" ] || . venv/bin/activate ;\
		pip install wheel ;\
	)
# regarding wheel see https://github.com/pypa/pip/issues/8102#issuecomment-619528947

# install python runtime dependencies
py-deps:
	( \
		[ -n "$$VIRTUAL_ENV" ] || . venv/bin/activate ;\
		pip install -r requirements/requirements.txt ;\
	)

# install python development dependencies
py-depsdev:
	( \
		[ -n "$$VIRTUAL_ENV" ] || . venv/bin/activate ;\
		pip install -r requirements/requirements-dev.txt ;\
	)

# pull postgresql docker image and generate config
db-cfg:
	$(eval POSTGRES_USER = 'pgadmin')
	$(eval POSTGRES_PASSWORD = $(shell tr -dc 'A-Za-z0-9+,-./:;' </dev/urandom | head -c "12"; echo ''))
	$(eval POSTGRES_DB = 'defaultdb')
	$(eval PGHOST = 'localhost')
	$(eval PGPORT = '5432')
	@echo -e '{\n    "db_type": "postgresql",\n    "db_user": "'$(POSTGRES_USER)'",\n    "db_pass": "'"$(POSTGRES_PASSWORD)"'",\n    "db_name": "'$(POSTGRES_DB)'",\n    "db_host": "'$(PGHOST)'",\n    "db_port": "'$(PGPORT)'",\n    "db_ssl":  "disable"\n}' > 'secrets/db_postgresql_example.json'
	docker pull postgres:17.4-bookworm

# spin docker postgresql container using existing config
db-run:
	@( \
		db_config_file="secrets/db_postgresql_container.json" ;\
		if [ ! -e "$$db_config_file" ]; then \
			mv "secrets/db_postgresql_example.json" "$$db_config_file"; \
		fi ;\
		export $$(jq -r 'to_entries|map("\(.key)=\(.value)")|.[]' $$db_config_file) ;\
		docker run --name postgres-webmon -p 127.0.0.1:5432:5432 --memory="512m" --shm-size="256m" -e POSTGRES_PASSWORD="$$db_pass" -e POSTGRES_USER="$$db_user" -e POSTGRES_DB="$$db_name" -d postgres:17.4-bookworm ;\
		docker ps --filter "name=postgres-webmon" ;\
	)
	@sleep 3s
	@nc -4 -zv localhost 5432

# stop the db container and remove it
db-del:
	@docker rm -f $$(docker container ls -aq --filter "name=postgres-webmon") || true

# run the application using pre-defined parameters; to add extra ones do: make run -- 'opt1 --opt2 a=x'
app-run: _args
	@#echo $(CMD_RUN)
	@( \
		[ -n "$$VIRTUAL_ENV" ] || . venv/bin/activate ;\
		$(CMD_RUN) ;\
	)

# profile the application
app-profile: _args
	@( \
		[ -n "$$VIRTUAL_ENV" ] || . venv/bin/activate ;\
		$(CMD_PROFILING) ;\
		tuna app.prof ;\
	)

# run tests and start pdb when a test fails
app-debug:
	@( \
		[ -n "$$VIRTUAL_ENV" ] || . venv/bin/activate ;\
		pytest -s -v --log-level=DEBUG --pdb tests/unit tests/integration ;\
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


# build documentation (eg: update README.md TOC)
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

# deploy all services using docker-compose (will terminate any previous containers beforehand)
docker-deploy: db-del
	@( \
		db_config_file="secrets/db_postgresql_compose.json" ;\
		db_service_name="postgres" ;\
		if [ ! -e "$$db_config_file" ]; then \
			mv "secrets/db_postgresql_example.json" "$$db_config_file" \
			cat <<< "$$(jq '.db_host = "'$$db_service_name'"' $$db_config_file)" > $$db_config_file ;\
		fi ;\
		export $$(jq -r 'to_entries|map("\(.key)=\(.value)")|.[]' "$$db_config_file") ;\
		docker-compose down ;\
		docker-compose up --build ;\
		docker-compose ps ;\
	)

# terminate all services via docker-compose down
docker-destroy:
	@( \
		docker-compose down ;\
		docker-compose ps ;\
	)

# dependencies for ci-push
_ci-push: db-del docker-destroy db-cfg db-run
	@# containers need to be cycled beforehand because the standalone container cfg (localhost) conflic with the docker compose cfg (postgres)
	@( \
		[ -n "$$VIRTUAL_ENV" ] || . venv/bin/activate ;\
		pip freeze | sort > requirements/requirements.freeze ;\
	)
	@nc -4 -zv localhost 5432 || (echo 'No DB found. Unable to run tests. Please fix the issue.' && exit 1)

# CI: update docs, sync list of installed packages, run tests (cycling containers beforehand), lint, commit, git push origin
ci-push: lint docs _ci-push tests
	git commit -a -v
	#git push origin

# catch unmatched rules (which are triggered when passing extra options to run) to do nothing
%:
	@echo "No such target in the Makefile: $@"

