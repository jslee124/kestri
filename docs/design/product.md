# Product definition

[简体中文](product.zh-CN.md) · [Documentation](../README.md)

Updated: 2026-10-01. Status: accepted product direction; M0 through M3 verified; full first-version acceptance remains M4. See [milestones](../development/milestones.md).

## Positioning

Kestri is a general personal AI agent running locally and accessible remotely through Telegram. It combines user-initiated conversation with explicitly delegated recurring work. It aims to become a useful daily assistant while providing experience in agent application engineering and a demonstrable portfolio project.

The initial user is the project owner. The first version supports one configured owner through a private Telegram chat. Multi-user hosting, organization accounts, and commercial operations are outside the initial scope.

## Product principles

- Start with actual daily use and add capabilities when a workflow needs them.
- Offer reusable information tools. News is the first scenario, not a fixed product vertical.
- Keep the user in control of recurring tasks and personal memory.
- Make task agreements, results, sources, and failures inspectable.
- Enforce permissions in application code and isolation boundaries.
- Treat local operation and external API processing as separate aspects of the product.

## Initial journeys

### Research a question

The user asks an everyday question or requests a comparison. Kestri briefly acknowledges substantial work, searches public sources, reads relevant material, and responds with a concise synthesis and supporting links. It distinguishes sourced facts, interpretation, and missing evidence.

An actionable request proceeds directly. Clarification is reserved for missing information that materially changes the outcome; other assumptions are stated. The user can follow up, reply to a particular result, or stop the current run. Tool-by-tool progress messages are not the normal interaction.

An unqualified “stop” targets the active foreground run. A stop request made as a reply to a known run message targets that run. If the intended target remains unclear, clarify before acting; stopping a run does not delete its recurring task.

### Delegate a recurring briefing

The user requests a recurring briefing in natural language. Once required information and the user's timezone are available, Kestri creates the task and echoes the agreement without a redundant approval step. The acknowledgement states timing, timezone, content preferences, and missed-run behavior.

The user can list, modify, pause, resume, or delete tasks. A reply to a task message helps identify the target; unresolved ambiguity requires clarification. Each execution has its own internal context and delivers into the same Telegram chat.

Pausing blocks future scheduled starts; an existing run continues. Stopping the current run is a separate operation. Routine successful background execution sends the final briefing, while terminal failures receive one concise notification. Preferences phrased for a specific briefing remain task-scoped.

### Manage personal memory

The user explicitly asks Kestri to remember a preference or fact. Kestri acknowledges the exact content saved. The user can inspect, correct, and forget it. Relevant memory can influence future conversations and tasks.

In the first version, inferred preferences require a suggestion and user acceptance before storage. Memory does not authorize new tasks or access. Forgetting a memory prevents its automatic reconstruction from older retained conversations; removing the surrounding archive is a separate data operation.

## First-version scope

| Included | Deferred |
| --- | --- |
| Telegram text conversation and reply association | Desktop GUI, TUI, voice, group chats |
| Public web search, extraction, synthesis, and source links | Interactive browser automation and logged-in browsing |
| Recurring tasks and a news-briefing acceptance scenario | Unrequested proactive goal generation |
| Explicit personal memory and user management | Default automatic preference mining and vector retrieval |
| Context compression and durable restart recovery | Arbitrary shell, scripts, plugins, and computer control |
| Workspace results and bounded operation records | Broad access to existing host directories and connected account mutations |
| Task cancellation and usage visibility | Automatic multi-model routing and multi-agent orchestration |

The dedicated workspace stores research materials and generated results. Importing sensitive original files or adding host read-only directories requires a later access design; they are not prerequisites for the first journeys.

## Success criteria

The owner can use all three journeys in one chat, understand what was remembered or delegated, and verify why a result was produced. Restarts preserve agreements and personal memory. Failure, cancellation, and recovery behavior are explainable through retained operation records.

Detailed acceptance criteria live in [requirements](requirements.md). Success must be supported by actual validation evidence; a demo alone does not establish reliability or isolation.

## Product questions still open

- The actual briefing topics and delivery time for the first personal trial.
- The exact presentation of task lists, memory lists, and operational controls.
- The interaction for deleting archives or exporting and restoring data.
- How to communicate uncertain delivery without duplicate or excessive notifications.

These questions do not change the accepted product positioning. [Runnable milestones](../development/milestones.md) define incremental delivery and completion criteria; detailed implementation scheduling is outside this product definition.
