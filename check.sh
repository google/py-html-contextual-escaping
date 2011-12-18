#!/bin/bash

export DIR="$(dirname "$0")"

export PYTHONPATH="$DIR/src:$DIR/tests:$PYTHONPATH"

find src tests -name \*.py | xargs pylint-2.6
