#!/bin/bash

if [ -z "$PYLINT" ]; then
  export PYLINT=pylint-2.6
fi

export DIR="$(dirname "$0")"

export PYTHONPATH="$DIR/src:$DIR/tests:$PYTHONPATH"

find src tests -name \*.py | xargs "$PYLINT"
