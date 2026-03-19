# Architecture

Technical architecture of Email Agent.

## System Overview

```
┌────────────────────────────────────────────────────────────────────────────┐
│                              Email Agent                                    │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                   │
│  │   Gmail API  │◄──►│   Ollama     │◄──►│   Config     │                   │
│  │   Client     │    │   Client     │    │   Manager    │                   │
│  └──────┬───────┘    └──────────────┘    └──────────────┘                   │
│         │                                                                  │
│         ▼                                                                  │
│  ┌──────────────────────────────────────────────────────────────┐          │
│  │                    Email Processor                            │          │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────────────────┐  │          │
│  │  │   Triage   │  │  Assess    │  │ Create Draft Reply     │  │          │
│  │  │   Stage    │  │ Importance │  │ (if important)         │  │          │
│  │  └─────┬──────┘  └──────┬─────┘  └────────────────────────┘  │          │
│  │        │               │                                     │          │
│  │        └───────────────┼─────────────────────────────────────┘          │
│  │                        ▼                                               │
│  │  ┌──────────────────────────────────────────────────────────────┐        │
│  │  │         Business Rules Override Layer                       │        │
│  │  │  (Post-LLM deterministic corrections)                       │        │
│  │  └──────────────────────────────────────────────────────────────┘        │
│  └──────────────────────────────────────────────────────────────┘          │
│         │                                                                  │
│         ▼                                                                  │
│  ┌──────────────────────────────────────────────────────────────┐          │
│  │                    Workflow Pipeline                          │          │
│  │              (Two-phase: Triage → Draft)                     │          │
│  └──────────────────────────────────────────────────────────────┘          │
│                                                                             │
│  ┌──────────────────────────────────────────────────────────────┐          │
│  │                    Trigger Module                            │          │
│  │              (Polling loop with interval)                   │          │
│  └──────────────────────────────────────────────────────────────┘          │
│                                                                             │
└────────────────────────────────────────────────────────────────────────────┘
```

## Modules

See [PLAN.md §4 Project Structure](PLAN.md#4-project-structure) for the complete module inventory and file tree.

## Two-Phase Pipeline

See [PLAN.md §5 Two-Phase Pipeline](PLAN.md#5-two-phase-pipeline) for the authoritative specification.

### Phase 1: Triage

```
1. FETCH → List unread emails from INBOX
2. STATE → Check if already processed (skip if yes)
3. STRIP → Strip HTML (BeautifulSoup, html.parser); skip if email has no textable content
4. TRIAGE → For each email: call Ollama with function calling, apply business rules, apply Gmail label
5. SUMMARY → Log triage results
```

### Phase 2: Draft

```
1. FILTER → Get emails with action=REPLY
2. DEDUP → Check for existing drafts in same thread (skip if exists)
3. IMPORTANCE → Check importance_threshold; skip if below threshold
4. DRAFT → For each REPLY email (not deduplicated): call Ollama with draft prompt, create Gmail draft
5. SUMMARY → Log draft creation results
```

## Error Handling

See [PLAN.md §7 Exception Hierarchy](PLAN.md#7-exception-hierarchy) and [PLAN.md §7 Retry Strategy](PLAN.md#retry-strategy-tenacity) for:
- Custom exception hierarchy (EmailAgentError base class)
- Retry strategy table (Ollama timeout, Gmail transient, Gmail quota)
- Circuit breaker parameters (5 failures, 60s recovery, 1 half-open call)

## Never Send Policy

Enforced by:
- Only `users.drafts.create()` used (never `.send()`)
- Pre-commit pygrep hook forbids `.send(` in src/
- CI ruff check catches any bypassed commits
