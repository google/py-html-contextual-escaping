#!/bin/bash

export DIR="$(dirname "$0")"

TEST_FILTER='^test_escape_text$' \
    PYTHONPATH="$DIR/src:$DIR/tests:$PYTHONPATH" \
    python tests/context_update_test.py