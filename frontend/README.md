# Mycelium frontend

See the [project README](../README.md) for the portfolio overview and full-stack setup.

```bash
npm ci
npm run demo
```

This starts a no-account preview at http://localhost:3000 with clearly labeled fictional data. Changes are in memory and reset on refresh.

For a configured FastAPI backend, use `npm run dev` instead. Set `NEXT_PUBLIC_API_URL` before starting/building if it differs from http://localhost:8000. `NEXT_PUBLIC_DEV_MOCK` is a build-time selection; rebuild when switching modes.

Checks: `npm run typecheck`, `npm run build:demo`, and `npm run build`.
