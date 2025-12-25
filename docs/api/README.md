# OpenAPI Contract Skeleton (YAML)

This folder is generated from `tech_updated.md` as a contract-first starter kit.

## Files
- `openapi.yaml`: entry OpenAPI document
- `paths/*.yaml`: PathItem objects (one anchor per path). Each path is referenced from `openapi.yaml` via `$ref`.
- `components/schemas.yaml`: shared schemas + per-operation placeholder Req_/Res_/Envelope_ schemas
- `components/parameters.yaml`: shared parameters (X-Tenant-Id, page, page_size, keyword)
- `components/responses.yaml`: shared error responses (all use ApiEnvelopeError)
- `components/security.yaml`: bearerAuth scheme

## Next steps
1. Replace placeholder request/response schemas in `components/schemas.yaml`.
2. Adjust which endpoints require `X-Tenant-Id` if needed.
3. (Optional) run a mock server using Prism:
   - `prism mock docs/api/openapi.yaml`
4. (Optional) Validate your DRF implementation against the contract:
   - Generate schema from code (drf-spectacular) and compare/diff.
