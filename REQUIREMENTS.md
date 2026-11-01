# CloudMate P2C — Product requirements

## Purpose

Enable a single operator to run trusted public GitHub command-line tools in Docker containers on a self-managed server through a browser interface. Command-line execution is the default; exposing an existing web dashboard is optional.

## Functional requirements

| ID | Requirement | Current implementation |
| --- | --- | --- |
| FR-01 | Authenticate requests to the deployment API. | Shared bearer token from `CLOUDMATE_TOKEN`. |
| FR-02 | Connect the dashboard to its own or another configured API origin. | Same-origin or HTTPS API URL with session token. |
| FR-03 | Accept a public GitHub repository and branch. | URL and branch validation; optional public GitHub API inspection. |
| FR-04 | Detect supported containerization strategy. | Explicit binary path, otherwise Dockerfile, Node.js, or Python. |
| FR-05 | Generate a Dockerfile when supported. | Linux binary, npm, and requirements.txt/app.py templates. |
| FR-06 | Execute asynchronous clone, build, and container startup. | Two-worker queue using Git and Docker CLIs. |
| FR-07 | Publish a dashboard only when explicitly enabled. | CLI mode defaults to no published ports; dashboard host port range 1024–65535. |
| FR-08 | Show job lifecycle and diagnostics. | Polled statuses, buffered build output, recent application stdout. |
| FR-09 | Stop a deployed container. | Authenticated stop endpoint and UI action. |
| FR-10 | Search and filter deployment records. | Name/repository search and status filter. |
| FR-11 | Show actual data rather than demonstration projects. | Empty workspace until API records are returned. |
| FR-12 | Accept a prebuilt binary tool and literal arguments. | Repository-relative Linux ELF executable and up to 64 argument strings. |
| FR-13 | Support tools that finish successfully. | Exit 0 is Completed; nonzero is Failed; CLI restart policy is no. |
| FR-14 | Update a running tool after it exits. | Reconcile active container state when listing projects. |

## Runtime requirements

- Python 3.10+ with no third-party Python packages.
- Git and a running, accessible Docker Engine.
- A modern browser; management API reachable locally, through SSH, or HTTPS.
- Sufficient host disk and build resources for the selected application.
- Network access to source, image, and dependency registries.
- Dashboard applications bind to 0.0.0.0 on their configured container port. CLI tools require no ports.
- Binary executables must match the Docker host architecture; custom dependencies require a Dockerfile.

## Acceptance criteria

1. An unauthenticated API request is rejected.
2. Invalid repository URLs, invalid branch syntax, and out-of-range ports are rejected.
3. A supported deployment is queued and invokes clone, build, then run in order.
4. A clone/build failure records Failed and does not continue to later deployment stages.
5. An exited dashboard or nonzero tool exit is Failed; a successful CLI exit is Completed.
6. A running container's recent output is available to the authenticated operator.
7. The stop action uses the recorded container ID and marks the job Stopped after success.
8. The interface does not claim a server is connected until the Docker health check succeeds.

Additional acceptance criteria: CLI mode never maps a port or automatically restarts a finished tool; exit code 0 completes a tool; dashboard ports remain optional and explicit; executable paths reject traversal and symlinks. The mocked test suite covers deployment commands, completion semantics, runtime templates, argument validation, path validation, and state reconciliation. Authentication and browser integration still need broader verification.

## Operational boundaries

This prototype is single-host and single-operator. It does not provide tenant isolation, persistent history, continuous health monitoring, automatic rollback, private repository access, or production availability guarantees. See README.md for configuration, security assumptions, and roadmap.
