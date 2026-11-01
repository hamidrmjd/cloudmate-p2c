# Contributing to CloudMate P2C

## Local setup

Use Python 3.10+, Git, and a Docker host. Set a local development token and start `python3 server.py` as described in README.md. No pip or npm dependencies are needed.

## Changes

1. Create a branch for a focused change.
2. Keep API inputs validated and invoke external tools using argument arrays.
3. Update README.md and REQUIREMENTS.md when behavior or configuration changes.
4. Add meaningful tests for changed deployment or authentication behavior.
5. Run `python3 -m unittest discover -s tests -v` and `python3 -m py_compile server.py`.
6. If Node.js is available, run `node --check dist/app.js`.
7. Open a pull request explaining the problem, change, checks, and any limits.

Do not include tokens, private source, generated checkout data, or credentials. Redact logs in issues. A real Docker test executes repository code on the Docker host; use only repositories and Dockerfiles you trust.

## Packaging

The downloadable server ZIP contains server.py, README.md, requirements.txt, .env.example, and the three dashboard files under dist/. It must not contain the ZIP itself, Git history, tokens, or runtime data. Regenerate it after changing packaged files.

## Licensing

This repository currently has no open-source license. Contributions do not change that status; coordinate reuse permissions with the repository owner.
