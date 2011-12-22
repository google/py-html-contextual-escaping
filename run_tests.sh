#!/bin/bash

export DIR="$(dirname "$0")"

for testmodule in tests/*_test.py; do
    PYTHONPATH="$DIR/src:$DIR/tests:$PYTHONPATH" python "$testmodule"
done
