# open-banking-gateway# Open Banking API Gateway (PSD2 / BaaS)

Minimal foundation repo. Folders:

- `services/` — application services (e.g., auth-consent, AIS, PIS)
- `infra/` — IaC, Docker, K8s manifests, Terraform, Helm
- `docs/` — architecture notes, ADRs, API docs

## Getting Started

1. Clone the repo
2. Commit this base
3. CI will run lint/tests **only if** code exists

## Roadmap (High-level)

- Step 1: Repo & CI skeleton ✅
- Step 2: Dev containers / compose for local DX
- Step 3: Auth & Consent service (FastAPI) scaffolding
- Step 4: API Gateway (Kong) baseline + OIDC
