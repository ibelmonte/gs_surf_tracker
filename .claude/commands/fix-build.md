# Fix Build (pnpm)

## Goal
Build with `pnpm build` by fixing root causes while preserving intended behavior.

## Never Do
- Don’t delete/comment out code to bypass errors.
- Don’t weaken checks (`eslint-disable`, `@ts-ignore`, broad `any`) unless minimally justified with a one-line reason and safer attempt first.
- Don’t hide warnings that indicate real issues.

## Flow
1) **Repro**
   - Run: `pnpm build`; also `pnpm typecheck`, `pnpm lint --max-warnings=0` (and `pnpm test` if present).
   - Group errors by root cause; for each: Symptom → Likely cause → Intent → Fix plan (1 line each).

2) **Fix (intent-preserving, minimal)**
   - Types: tighten signatures/guards/generics; avoid casts.
   - Imports/exports: correct paths, resolve circulars.
   - Logic: null/undefined, async/await, branches.
   - Config: align `tsconfig`, bundler/Next/Vite; env vars safe (no secrets).
   - React/Next: server/client boundaries, hooks rules, SSR/CSR.
   - If intent unclear: infer conservatively; add `// FIX: why`.

3) **Supabase (only if DB involved)**
   - **MCP**: inspect schema, relations, and small data samples to verify shapes vs code types.
   - **CLI** (only if schema drift is root cause):
     - `supabase db diff` (confirm drift)
     - `supabase migration new <name>`
     - `supabase db push`
   - Keep migrations atomic, reversible; update generated/types/zod as needed.

4) **Proactive Sweep**
   - Search & fix same-pattern issues in touched files (don’t churn unrelated files).

5) **Validate**
   - Re-run: `pnpm typecheck`, `pnpm lint --max-warnings=0`, `pnpm build`, `pnpm test` (if exists).
   - Iterate until clean.

## Output (short)
- **Fixes:** root-cause → change (bulleted).
- **Supabase:** schema/data checks; migrations (if any).
- **Follow-ups:** non-blocking TODOs.

## Preferences
- Local refactors > global rewrites.
- Keep deps as-is unless version bug proven.
- Don’t change public API unless all callsites updated; note it.

## Commands
`pnpm build` · `pnpm typecheck` · `pnpm lint --max-warnings=0` · `pnpm test`  
`supabase db diff` · `supabase migration new <name>` · `supabase db push`

## Acceptance
- Build/typecheck/lint pass with no silenced rules.
- Behavior preserved; unclear intent documented.
- DB types/schema verified via MCP; migrations only if required.
- Similar issues in touched scope addressed.
