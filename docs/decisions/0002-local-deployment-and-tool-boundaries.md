# ADR-0002: Deploy locally with Docker Compose and controlled tools

[简体中文](0002-local-deployment-and-tool-boundaries.zh-CN.md) · [Documentation](../README.md)

- Status: Accepted
- Decision date: 2026-09-30
- Updated: 2026-10-01
- Implementation: M1 Compose and controlled research tools available; see [current evidence](../development/m1-validation.md)

## Context

The owner wants a local general personal agent accessible through Telegram while avoiding accidental damage to existing files. Initial workflows require public web retrieval, task management, memory, and workspace results; they do not require arbitrary code or direct computer control.

## Decision

Use Docker Compose for the local application and PostgreSQL. Use Telegram private chat with long polling and an owner user-ID allowlist. Long polling avoids requiring an inbound public webhook for this deployment. Telegram documents both polling and webhooks in its [Bots FAQ](https://core.telegram.org/bots/faq#how-do-i-get-updates).

Expose only controlled application tools in the first version. Give the application a dedicated workspace, rather than broad host-directory access. Do not expose arbitrary shell/code execution, connected-account mutation, or the Docker daemon socket.

Keep service credentials and personal databases outside the model-visible workspace. Application policy validates every model tool request. Controlled search and extraction may access the public internet with explicit URL/output/time policies; filesystem work stays within task scope.

When code execution becomes necessary, introduce an independent short-lived sandbox limited to task files, without service credentials or personal state. Exact provisioning and sandbox technology configuration require a later design. See [security and data](../design/security-and-data.md) for policy details.

## Alternatives considered

| Alternative | Tradeoff |
| --- | --- |
| Native-only deployment | Convenient for development, but lacks the selected deployment filesystem/process boundary |
| Put the whole application and arbitrary scripts in one container | Makes application credentials and persistent data available to script execution |
| Broad writable home-directory mount | Convenient access creates unnecessary risk to existing files |
| Dedicated VM immediately | Stronger separation may be useful later, but adds operating-system maintenance before a workflow requires arbitrary execution |
| Cloud-hosted agent | Changes the local-operation goal and does not eliminate the risks of connected-account permissions |
| Telegram webhook | Requires an inbound reachable endpoint, which the first local deployment does not need |

## Consequences

The initial deployment depends on Docker availability and an awake, connected host. Laptop downtime affects scheduled work and is handled through a bounded missed-run policy, rather than a promise of always-on execution.

The workspace remains real persistent user data. A writable bind mount can modify host files; Docker isolation does not make mounted originals safe automatically. The [official bind-mount documentation](https://docs.docker.com/engine/storage/bind-mounts/) explains this behavior.

Controlled tools run with application-process authority; they need careful validation and are not equivalent to a separate untrusted-code sandbox. Credentials in application configuration are hidden from the model by design, but not protected from an application compromise.

The design reduces exposed capabilities while preserving reusable information workflows. It does not establish absolute safety. Recovery, boundary checks, resource limits, and installed deployment behavior must be validated.

## Review conditions

Reconsider isolation when scripts, plugins, browser sessions, or computer-control tools are introduced. Reconsider deployment when always-on operation or additional interfaces become actual requirements. Expanded host/account access requires explicit permissions and updated acceptance criteria.
