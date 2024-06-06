.PHONY: help args venv depsdev deps run profiling test debug

# running make with no targets will run the first target (in this case "help")
# this help menu
help:
	@cat $(MAKEFILE_LIST) | grep -v '^args:' | grep -B 1 '^[a-z\-]*:' | sed 's/\(^[^#].*\):.*/\1/g' | sed 's/\([^#]\)--/\1XXDEADBEEFXX/g' | awk 'BEGIN {RS="--\n?"; FS="\n"} {printf "\033[36m%-20s\033[0m %s\n", $$2, $$1}' | sed 's/XXDEADBEEFXX/--/g'

args:
# if the first argument is "run" then pass any other arguments to the app
# https://stackoverflow.com/questions/2214575/passing-arguments-to-make-run
# NOTE: to pass --option you need to run it this way: make run -- --option
#$(info "HEY DEBUG: $(RUN_ARGS)")
ifeq (run,$(firstword $(MAKECMDGOALS)))
# use the rest as arguments for "run"
RUN_ARGS := $(wordlist 2,$(words $(MAKECMDGOALS)),$(MAKECMDGOALS))
# ...and turn them into do-nothing targets
$(eval $(RUN_ARGS):;@:)
endif


APP=src/webmon.py
DEF_ARGS=
CMD_RUN=python $(APP) $(DEF_ARGS) $(RUN_ARGS)
CMD_PROFILING=python -mcProfile -o app.prof $(APP) $(DEF_ARGS) $(RUN_ARGS)


# create python virtual env: MY TEST
venv:
	( \
		test -d venv || python3 -m venv venv ;\
		[ -n "$$VIRTUAL_ENV" ] || . venv/bin/activate ;\
		pip install wheel ;\
	)
# regarding wheel see https://github.com/pypa/pip/issues/8102#issuecomment-619528947

# install development dependencies
depsdev:
	( \
		[ -n "$$VIRTUAL_ENV" ] || . venv/bin/activate ;\
		pip install -r requirements-dev.txt ;\
	)

# install runtime dependencies
deps:
	( \
		[ -n "$$VIRTUAL_ENV" ] || . venv/bin/activate ;\
		pip install -r requirements.txt ;\
	)

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

# run tests using pytest
test:
	@( \
		[ -n "$$VIRTUAL_ENV" ] || . venv/bin/activate ;\
		pytest -s -v --log-level=DEBUG tests ;\
	)

# run tests and start pdb when a test fails
debug:
	@( \
		[ -n "$$VIRTUAL_ENV" ] || . venv/bin/activate ;\
		pytest -s -v --log-level=DEBUG --pdb tests ;\
	)

# catch unmatched rules (which are triggered when passing extra options to run) to do nothing
%:
	@:


