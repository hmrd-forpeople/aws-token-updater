# aws-token-updater

[![Changelog](https://img.shields.io/github/v/release/hmrd-forpeople/aws-token-updater?include_prereleases&label=changelog)](https://github.com/hmrd-forpeople/aws-token-updater/releases)
[![Tests](https://github.com/hmrd-forpeople/aws-token-updater/actions/workflows/test.yml/badge.svg)](https://github.com/hmrd-forpeople/aws-token-updater/actions/workflows/test.yml)
[![License](https://img.shields.io/badge/license-CC0%201.0-blue.svg)](https://github.com/hmrd-forpeople/aws-token-updater/blob/master/LICENSE)

A program to update AWS tokens from a VM on the host using kion

## Installation

Install this from the releases page

## Usage

For help, run:
```bash
aws-token-updater --help
```

## Development

To contribute to this tool, first, install `uv`. See [the uv documentation](https://docs.astral.sh/uv/getting-started/installation/) for how.

Then create a new virtual environment and sync the dependencies:
```bash
cd aws-token-updater
uv sync
```

To run the tests:
```bash
uv run python -m pytest
```
