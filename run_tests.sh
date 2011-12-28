#!/bin/bash

# Usage:
#   TESTFILTER='<a regex>' ./run_tests.sh
# The test filter is optional and is a regular expression in egrep format that
# should match the name of py files under tests.

export DIR="$(dirname "$0")"

for testmodule in tests/*_test.py; do
    if [ -z "$TESTFILTER" ] || (echo "$testmodule" | egrep -q "$TESTFILTER")
    then
	echo
	echo $testmodule
	echo $testmodule | tr ' -~' '='
	PYTHONPATH="$DIR/src:$DIR/tests:$PYTHONPATH" python "$testmodule"
    fi
done
