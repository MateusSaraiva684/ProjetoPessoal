#!/usr/bin/env python3
"""Compatibilidade: use `python cli.py create-admin` para gerenciar o admin."""

import sys
if __name__ == "__main__":
    from cli import main
    sys.exit(main())
