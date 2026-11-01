# CloudMate P2C — Project to Container

**Turn a public GitHub project into a running Docker container on your own server.**

CloudMate P2C is a self-hosted deployment dashboard. Give it a public GitHub repository, choose a branch and ports, and it clones the source, detects a supported runtime, builds a Docker image, and starts the application on your Docker host. The dashboard shows deployment progress, build output, and application logs.

> **Status: early prototype.** Intended for a single operator deploying trusted repositories on a dedicated host. It is not a multi-tenant platform or a production-hardened service. The repository includes mocked deployment tests; a real Docker deployment has not yet been verified in the development environment.

## Contents

- [Features](#features)
- [Requirements](#requirements)
- [Quick start](#quick-start)
- [Deploy a project](#deploy-a-project)
- [Supported runtimes](#supported-runtimes)
- [Remote server access](#remote-server-access)
- [Configuration](#configuration)
- [How it works](#how-it-works)
- [API](#api)
- [Development and tests](#development-and-tests)
- [Troubleshooting](#troubleshooting)
- [Security and limitations](#security-and-limitations)
- [Roadmap](#roadmap)

## Features

- Browser dashboard with real deployment records, search, and status filters.
- Public GitHub repository inspection, including its default branch.
- Automatic detection of an existing Dockerfile, Node.js, or Python project.
- Generated Dockerfile templates for supported Node.js and Python applications.
- Asynchronous deployments with up to two workers.
- Unique Docker image and container names for each deployment.
- Configurable application and published host ports.
- Build output and polled container logs.
- Authenticated API and container stop controls.
- Default loopback binding for local access or SSH forwarding.
- No third-party Python dependencies and no frontend build step.

## Requirements

### Deployment host

| Requirement | Details |
| --- | --- |
| Operating system | Linux is the intended deployment environment. macOS with Docker Desktop may be used for development, but has not been verified. |
| Python | Python **3.10 or newer**. Only the standard library is used. |
| Git | Git executable available on `PATH`. |
| Docker | A running Docker Engine compatible with `build`, `run`, `inspect`, `logs`, and `stop`. |
| Docker access | The server process user must be allowed to access the Docker daemon. Docker access grants substantial host privileges. |
| Network | Outbound access to GitHub, container registries, and your application's package registries. |
| Published ports | An available host port from **1024–65535** per deployment. Open the chosen application port in your firewall only when required. |
| Resources | Enough disk, RAM, and CPU to clone and build your application. Each started container is limited to **512 MB RAM and 1 CPU**; builds have no equivalent resource limit. |
| Browser | A modern JavaScript-enabled browser. HTTPS or localhost is recommended. |

`requirements.txt` intentionally lists no pip dependencies. Git and Docker are external system requirements, not Python packages.

### Application repository

- A **public** repository at `https://github.com/OWNER/REPOSITORY`.
- A valid branch name, such as `main`.
- A supported project layout or a repository-provided Dockerfile.
- A server process that listens on **`0.0.0.0`**, rather than only localhost inside the container.
- The correct application port. CloudMate does not automatically infer listening ports.
- No requirement for interactive setup or private registry credentials in the current version.

## Quick start

Clone this repository, or download and extract its source, then enter the project directory.

```sh
# Confirm the required tools are available.
python3 --version
git --version
docker info

# Generate a token for this shell session. Keep it available for the dashboard.
export CLOUDMATE_TOKEN="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"

# Start the dashboard and deployment API on loopback.
python3 server.py
```

Open **http://127.0.0.1:8787** in your browser.

1. Choose **Connect server**.
2. Leave **Server API URL** empty when using the dashboard served by `server.py`.
3. Enter the value of `CLOUDMATE_TOKEN` from your server shell.
4. Choose **Test & connect**.
5. Choose **Deploy a project** to start your first deployment.

To display the generated token in your own terminal when entering it in the dashboard:

```sh
printf '%s\n' "$CLOUDMATE_TOKEN"
```

The token is retained in the browser's session storage. The API address is retained in local storage. Starting a new shell without re-exporting the token requires generating or supplying it again. For a persistent installation, configure the token in your service manager's protected environment.

`.env.example` documents the settings; the application **does not automatically load `.env` files**. Export values in your shell or configure them in your service manager.

## Deploy a project

1. Paste the public GitHub repository URL.
2. Select **Inspect repository** to retrieve its default branch, or enter the branch manually.
3. Select **Detect automatically**, **Node.js**, **Python**, or **Existing Dockerfile**.
4. Enter the port your application listens on inside its container.
5. Choose an available published server port, such as `8080`.
6. Select **Build & deploy**.
7. Open the project's **View logs** panel to follow the job.
8. When its status is **Running**, access `http://YOUR_SERVER:HOST_PORT`, subject to your firewall and routing configuration.

Deployment states:

```text
Queued → Cloning → Building → Starting → Running
                  Any error → Failed
                   Stop action → Stopped
```

“Running” means the container process was running two seconds after startup. It does not verify an HTTP endpoint or continuously monitor the process afterward.

Use the **Stop container** control in the logs panel to stop an existing deployment. A new deployment creates a separate image and container; it does not replace the previous one. Select another host port or stop the previous container first.

## Supported runtimes

| Runtime | Detection | Behavior and prerequisites |
| --- | --- | --- |
| Existing Dockerfile | Root `Dockerfile` | Builds the repository's Dockerfile. Use this for custom frameworks, entry points, or system packages. |
| Node.js | Root `package.json` | Requires `package-lock.json`; runs `npm ci`, optional `npm run build`, then `npm start`, using `node:22-alpine`. Sets `NODE_ENV`, `HOSTNAME`, and `PORT`. |
| Python | Root `requirements.txt` | Installs dependencies using `python:3.12-slim`, then runs `python app.py`. Your app must configure its own binding address and listening port. |

Automatic detection checks in this order: **Dockerfile → package.json → requirements.txt**. Projects without any of these files fail with a runtime-detection message.

The generated Node.js template supports npm projects only. Yarn, pnpm, monorepos, compiled Python system dependencies, alternate Python entry points, and static sites should provide an appropriate Dockerfile. Template base-image versions are defaults in this source, not a statement about current upstream support.

## Remote server access

### Recommended prototype setup: SSH tunnel

Run CloudMate P2C on the Docker server using the default loopback binding. From your own computer:

```sh
ssh -L 8787:127.0.0.1:8787 USER@YOUR_SERVER
```

Open **http://127.0.0.1:8787** locally. Leave the API URL empty and supply your server token. The server remains bound to loopback, and SSH carries your connection.

The tunnel forwards the management dashboard, not your application ports. Access application ports separately, or forward those ports through SSH too.

### Separate dashboard and API

For an externally hosted dashboard:

1. Place the Python server behind an HTTPS reverse proxy.
2. Keep its upstream bound to loopback where possible.
3. Set `CLOUDMATE_ORIGIN` to the exact dashboard origin, with no trailing slash.
4. In the dashboard, enter your API's HTTPS URL and server token.

For example:

```sh
export CLOUDMATE_ORIGIN=https://dashboard.example.com
export CLOUDMATE_TOKEN='your-long-random-secret'
python3 server.py
```

In the dashboard, connect to an API URL such as `https://deploy.example.com`. Origin restrictions supplement token authentication; they do not replace it. The current Python HTTP server is intended for a trusted prototype environment; keep public access behind appropriate network controls and a reverse proxy.

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `CLOUDMATE_TOKEN` | Required | Shared bearer token for all API calls. Startup fails if missing. Use a long, random value. |
| `CLOUDMATE_BIND` | `127.0.0.1` | Interface for the management server. |
| `PORT` | `8787` | Management dashboard/API port. |
| `CLOUDMATE_ORIGIN` | Empty | One additional permitted browser origin for a separately hosted dashboard. |
| `CLOUDMATE_DATA` | `./data` beside `server.py` | Directory for repository checkouts and build files. |

Internal defaults currently require source changes: two deployment workers, ten-minute command timeout for builds, two-minute clone timeout, a maximum of 100 job records per process, 512 MB RAM and 1 CPU per application container, and a four-second dashboard polling interval.

## How it works

```text
Browser dashboard
       │ authenticated HTTP API
       ▼
Python server on your Docker host
       │
       ├─ Git clone into data/<deployment-id>
       ├─ Detect runtime / generate Dockerfile
       ├─ Docker build → image
       └─ Docker run → published application port
```

The browser never executes Docker. Git, image builds, and containers run on the machine hosting `server.py`. Merely publishing the static dashboard does not provide a Docker host.

### Repository layout

```text
cloudmate-p2c/
├── server.py              # HTTP API, deployment worker, static file server
├── dist/
│   ├── index.html         # Dashboard markup
│   ├── style.css          # Responsive styles
│   ├── app.js             # API client and interface behavior
│   └── cloudmate-p2c-server.zip # Portable server package
├── tests/
│   └── test_server.py     # Mocked deployment lifecycle tests
├── requirements.txt       # Documents standard-library-only Python setup
├── .env.example           # Configuration reference; not auto-loaded
├── DESCRIPTION.md         # Short project description
├── REQUIREMENTS.md        # Product requirements and acceptance criteria
├── CONTRIBUTING.md        # Development and contribution guidance
└── README.md
```

## API

Every `/api/*` request requires:

```http
Authorization: Bearer YOUR_CLOUDMATE_TOKEN
```

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/api/health` | Docker availability and version. |
| `GET` | `/api/projects` | In-memory job records, statuses, and build output. |
| `POST` | `/api/projects` | Validate and enqueue a deployment. Returns HTTP 202. |
| `GET` | `/api/projects/{id}/logs` | Build output plus recent container stdout. |
| `POST` | `/api/projects/{id}/stop` | Stop the deployment's container. |

Example deployment request, issued on the management server:

```sh
curl --fail-with-body http://127.0.0.1:8787/api/projects \
  -H "Authorization: Bearer $CLOUDMATE_TOKEN" \
  -H 'Content-Type: application/json' \
  --data '{
    "repo": "https://github.com/OWNER/REPOSITORY",
    "branch": "main",
    "runtime": "auto",
    "port": 3000,
    "hostPort": 8080
  }'
```

Runtime values: `auto`, `docker`, `node`, or `python`. Container ports must be 1–65535; published host ports must be 1024–65535. Repository paths and branch names are validated. Git and Docker commands use argument lists rather than shell interpolation.

## Development and tests

No npm installation, frontend compilation, or pip installation is required.

```sh
python3 -m unittest discover -s tests -v
python3 -m py_compile server.py

# Optional, if Node.js is available, check frontend syntax:
node --check dist/app.js
```

Current tests mock Git and Docker commands. They verify a successful deployment flow, clone failure behavior, and detection of a container that exits at startup. They do **not** verify a real Docker build, network routing, application health, browser behavior, or public deployment security.

See [CONTRIBUTING.md](CONTRIBUTING.md) for contribution guidance and [REQUIREMENTS.md](REQUIREMENTS.md) for the implementation scope.

## Troubleshooting

| Problem | Checks |
| --- | --- |
| Server refuses to start | Set `CLOUDMATE_TOKEN` before starting Python. Check the management port is available. |
| Docker is offline | Run `docker info` as the same user as CloudMate. Start the daemon and check its socket permissions. |
| API connection fails | Check the API URL, bearer token, reverse proxy, HTTPS certificate, and `CLOUDMATE_ORIGIN`. An HTTPS dashboard cannot call an ordinary remote HTTP API. |
| Repository inspection fails | Confirm the repository is public and its URL is correct. GitHub API rate limits may block inspection; enter the branch manually. |
| Clone fails | Check GitHub access, the branch name, and outbound network access. |
| Node build fails | Ensure `package-lock.json` is committed and `npm start` works. Inspect dependency and build output. |
| Python container exits | Ensure `app.py` exists and runs the server. Use a Dockerfile for another entry point. |
| Container is running but unreachable | Check that the app binds to `0.0.0.0`, the application port matches the form, and the host firewall permits the published port. |
| Published port is busy | Select a different host port or stop the container/process already using it. |
| Log panel updates in chunks | Build commands buffer their output until they finish; this is not streaming build output. |
| Projects disappear after restart | Job records are currently in memory. Containers and checkout directories remain on the server. |

## Security and limitations

- **Deploy trusted code only.** Repository Dockerfiles, build scripts, and package installation hooks execute code. Docker access is powerful; resource limits on application containers do not sandbox image builds against hostile projects.
- The shared server token grants deployment and stop access to this host. There are no per-user roles, token scopes, or audit records.
- Use an SSH tunnel for remote prototype access. If exposing a management endpoint, use HTTPS, network restrictions, and a reverse proxy.
- Do not commit tokens, `.env` files, private keys, or application secrets. There is no application environment-variable editor or secrets store in this version.
- Generated templates copy repository contents into the image. Include a suitable `.dockerignore` to exclude secrets and unnecessary files.
- Job history is not persisted, and container status is not reconciled continuously or recovered when the Python server restarts.
- Public repositories only. No GitHub OAuth flow, private repositories, submodule setup, or private registry authentication.
- No automatic app TLS, domain setup, reverse proxy routing, rollback, zero-downtime replacement, persistent volumes, health checks, or scheduled redeployments.
- Build output is buffered and bounded in memory; recent application logs are polled. The live log endpoint currently returns container stdout; build/startup diagnostics may also include stderr.
- Checkouts, images, and stopped containers require manual cleanup. The stop action does not delete them.
- The interface uses externally hosted Google Fonts when available; system fonts are the fallback.

## Roadmap

Planned work, **not implemented**:

- Durable deployment history and container reconciliation after restarts.
- Real Docker integration tests and browser verification.
- Streaming logs and application health checks.
- Secure secret injection and configurable start commands.
- GitHub authentication for private repositories.
- Redeployments, rollback, and managed cleanup.
- Domain routing, application HTTPS, and persistent storage options.
- Stronger host isolation and production deployment hardening.

## Contributing

Bug reports and focused contributions are welcome. Include reproduction steps, expected behavior, and redacted logs. Never post tokens or other secrets in issues. See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

No open-source license has been selected yet. Public visibility alone does not grant an open-source license; the copyright holder must choose one before broader reuse permissions are granted.
