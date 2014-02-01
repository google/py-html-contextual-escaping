#!/bin/bash

if [ -z "$PYLINT" ]; then
  export PYLINT=pylint-2.7
fi

export DIR="$(dirname "$0")"

export PYTHONPATH="$DIR/autoesc:$DIR/tests:$PYTHONPATH"

find autoesc tests -name \*.py | xargs "$PYLINT"
