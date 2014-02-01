#!/bin/bash

# Usage:
#   TESTFILTER='<a regex>' ./run_tests.sh
# The test filter is optional and is a regular expression in egrep format that
# should match the name of py files under tests.

export DIR="$(dirname "$0")"

if [ -z "$PYTHON" ]; then
    if [ -n "$(which coverage-2.7)" ]; then
	rm -f .coverage
	export PYTHON="coverage-2.7 run -a --branch --source=$DIR/autoesc"
    else
	export PYTHON="python -3 -OO -t"
    fi
fi

for testmodule in tests/*_test.py; do
    if [ -z "$TESTFILTER" ] || (echo "$testmodule" | egrep -q "$TESTFILTER")
    then
	echo
	echo $testmodule
	echo $testmodule | tr ' -~' '='
	PYTHONPATH="$DIR/autoesc:$DIR/tests:$PYTHONPATH" $PYTHON "$testmodule"
    fi
done

if [ -e .coverage ]; then
    mkdir -p test_output
    coverage-2.7 html -d test_output/coverage
fi
