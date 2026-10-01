# Documentation guide

[简体中文](README.zh-CN.md) · [Project home](../README.md)

Updated: 2026-10-01. Status: documentation baseline; application not implemented.

## Read the design

| Document | Purpose | Status |
| --- | --- | --- |
| [Product](design/product.md) | Positioning, user journeys, and first-version scope | Accepted product direction |
| [Requirements](design/requirements.md) | Identified requirements and acceptance criteria | Draft specification based on agreed behavior |
| [Architecture](design/architecture.md) | Responsibilities, boundaries, and execution flows | Design draft; major choices accepted |
| [Security and data](design/security-and-data.md) | Permissions, isolation, memory, context, and data lifecycle | Design draft; policy direction accepted |
| [Runnable milestones](development/milestones.md) | Runnable increments, exit criteria, requirement coverage, and evidence | Delivery sequence accepted; next target M0 |
| [ADR-0001](decisions/0001-agent-stack.md) | Python, LangChain Agent, and DeepSeek official API | Accepted |
| [ADR-0002](decisions/0002-local-deployment-and-tool-boundaries.md) | Local deployment and controlled tools | Accepted |
| [ADR-0003](decisions/0003-persistence-and-state-separation.md) | PostgreSQL and separation of state categories | Accepted |

“Accepted” records a design decision. It does not establish that its implementation works. The requirements document is the source of acceptance criteria; verification evidence will be added when implementation exists.

## Documentation organization

Kestri uses [Diátaxis](https://diataxis.fr/) to distinguish learning tutorials, task-oriented how-to guides, factual reference, and explanations. Product requirements, delivery milestones, and ADRs are maintained separately as engineering records. This directory layout is a project convention, not a requirement imposed by Diátaxis.

| Category | Reader need | Availability |
| --- | --- | --- |
| Tutorials | Learn by completing a guided experience | Deferred until a verified end-to-end flow exists |
| How-to guides | Complete a specific task | Deferred until the relevant operation is implemented |
| Reference | Look up exact interfaces, configuration, and behavior | Deferred until implementation defines those facts |
| Explanation | Understand concepts, mechanisms, and tradeoffs | Current design documents provide design-stage explanations |
| Design | Review intended product behavior and system boundaries | Available above |
| Development | Follow runnable delivery increments and verification progress | Milestones available; no implementation started |
| Decisions | Understand why a major choice was made | Available above |

Do not present a proposal as reference documentation for an implemented feature. No placeholder tutorials or unverified installation commands are included.

## Language and maintenance

- English is the primary source. Each `name.md` has a sibling `name.zh-CN.md` translation; `README.md` follows the same rule.
- Each pair links to its counterpart. Chinese navigation links to Chinese documents; English navigation links to English documents.
- Update both versions in the same change. Preserve requirement IDs, decision IDs, technical identifiers, and the meaning of dates and statuses.
- If a translation diverges, correct the pair; do not retain different requirements in different languages.
- Keep headings, scope, tables, and acceptance cases aligned. Translate prose, while preserving exact API identifiers and paths when relevant.
- Store each normative fact in one designated document and link to it elsewhere. Product defines scope, requirements define acceptance, design documents define proposed mechanisms and defaults, and milestones define delivery order and evidence status.
- Label confirmed decisions, adjustable defaults, open questions, implemented behavior, and verification evidence distinctly.
- Cite primary sources for external technical capabilities and record when they were checked. Recheck drifting provider facts during implementation.

## Decision records

ADRs use a numbered filename and record status, context, decision, alternatives, consequences, and review conditions. Record significant choices; routine tuning values belong in design documents. A replacement ADR identifies the decision it supersedes, and both translations are updated.

## Verification policy

Before accepting a documentation change, check local links, English/Chinese pairing, identifier consistency, and formatting. Once software exists, connect acceptance criteria to actual validation evidence. Distinguish offline checks, live API behavior, recovery tests, and deployment acceptance.
