# Business Intelligence Platform

Multi-tenant AI-powered BI platform.

## Stack
- Backend: FastAPI + PostgreSQL + MongoDB + Redis
- Frontend: Next.js 15
- AI: Vertex AI Gemini + Anthropic + OpenAI

## Quick Start
cd infrastructure
docker-compose up -d

## Production Workflow

The backend currently implements the following tenant-scoped flow:

1. Load and normalize customer reviews and social data.
2. Build deterministic cross-source trend intelligence.
3. Generate an evidence-grounded SWOT update proposal.
4. Validate every generated claim against stable evidence references.
5. Persist the draft proposal for explicit human review.
6. Apply human approval decisions.
7. Persist an approved, Strategy-ready SWOT report.
8. Generate Strategy only from the latest approved SWOT.
9. Persist the complete Strategy output.
10. Resolve creative themes and expose an image-generation handoff.

## SWOT Update API

- `POST /api/v1/businesses/{business_id}/swot/proposals`
- `GET /api/v1/businesses/{business_id}/swot/proposals/{proposal_id}`
- `POST /api/v1/businesses/{business_id}/swot/proposals/{proposal_id}/approve`

Draft SWOT proposals never feed Strategy directly.

## Strategy API

- `POST /api/v1/businesses/{business_id}/strategy/generate`
- `GET /api/v1/businesses/{business_id}/strategy/latest`

Strategy generation accepts only a SWOT report with:

- `status = approved`
- `approval_complete = true`
- `ready_for_strategy = true`
- no unresolved candidate IDs

The persisted Strategy includes:

- Positioning
- Audience
- Value proposition
- Tone of voice
- Content pillars
- Channels
- Goals
- TOWS matrix
- Priority action plan
- Resource assessment
- Campaign brief feed
- Strategy quality report

## Creative Context and Image Handoff

- `POST /api/v1/businesses/{business_id}/creative-themes/auto-resolve`
- `POST /api/v1/businesses/{business_id}/creative-themes/image-handoff`

The image handoff is a compact, versioned contract and excludes
internal diagnostics, rejected market moments, inactive candidates,
registry warnings, and social-account identifiers.

## Image Team Next Integration

The creative-context engine already accepts optional
`AutoCreativeSignals`.

The next integration task is to add an adapter from the latest
persisted `StrategyReportDocument` into `AutoCreativeSignals`, then
pass those signals to `resolve_automatic_creative_theme`.

Suggested mappings:

- Strategy channels -> preferred platform
- Strategy goals -> campaign objective
- Campaign brief feed -> objective and product context
- Strategy evidence/source lineage -> creative evidence references

The current image-handoff endpoint remains functional without this
optional Strategy adapter.

## Verification Status

Release verification completed with:

- 487 passing tests
- 3 external database health checks skipped
- 0 failing tests
- no duplicate FastAPI routes