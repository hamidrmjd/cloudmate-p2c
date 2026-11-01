# CloudMate P2C — Product requirements

## Purpose

Enable a single operator to deploy a trusted public GitHub application as a Docker container on a self-managed server through a browser interface.

## Functional requirements

| ID | Requirement | Current implementation |
| --- | --- | --- |
| FR-01 | Authenticate requests to the deployment API. | Shared bearer token from `CLOUDMATE_TOKEN`. |
| FR-02 | Connect the dashboard to its own or another configured API origin. | Same-origin or HTTPS API URL with session token. |
| FR-03 | Accept a public GitHub repository and branch. | URL and branch validation; optional public GitHub API inspection. |
| FR-04 | Detect supported containerization strategy. | Existing Dockerfile first, then Node.js, then Python. |
| FR-05 | Generate a Dockerfile when supported. | npm and requirements.txt/app.py templates. |
| FR-06 | Execute asynchronous clone, build, and container startup. | Two-worker queue using Git and Docker CLIs. |
| FR-07 | Publish the application on a selected host port. | Docker port mapping; host port range 1024–65535. |
| FR-08 | Show job lifecycle and diagnostics. | Polled statuses, buffered build output, recent application stdout. |
| FR-09 | Stop a deployed container. | Authenticated stop endpoint and UI action. |
| FR-10 | Search and filter deployment records. | Name/repository search and status filter. |
| FR-11 | Show actual data rather than demonstration projects. | Empty workspace until API records are returned. |

## Runtime requirements

- Python 3.10+ with no third-party Python packages.
- Git and a running, accessible Docker Engine.
- A modern browser; management API reachable locally, through SSH, or HTTPS.
- Sufficient host disk and build resources for the selected application.
- Network access to source, image, and dependency registries.
- Applications bind to 0.0.0.0 on their configured container port.

## Acceptance criteria

1. An unauthenticated API request is rejected.
2. Invalid repository URLs, invalid branch syntax, and out-of-range ports are rejected.
3. A supported deployment is queued and invokes clone, build, then run in order.
4. A clone/build failure records Failed and does not continue to later deployment stages.
5. A container that exits during the initial startup check is marked Failed.
6. A running container's recent output is available to the authenticated operator.
7. The stop action uses the recorded container ID and marks the job Stopped after success.
8. The interface does not claim a server is connected until the Docker health check succeeds.

The test suite currently covers criteria 3, clone failure in 4, and 5 using mocked commands. The remaining criteria require broader integration verification.

## Operational boundaries

This prototype is single-host and single-operator. It does not provide tenant isolation, persistent history, continuous health monitoring, automatic rollback, private repository access, or production availability guarantees. See README.md for configuration, security assumptions, and roadmap.
