#!/usr/bin/env python

from pylint import lint

linter = lint.PyLinter()
linter.load_default_plugins()
linter.check(['autoesc', 'tests'])
