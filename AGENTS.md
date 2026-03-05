# Repository Guidelines

## Project Structure & Module Organization
This repository is currently a clean bootstrap (no source files committed yet). Keep the layout simple and predictable as you add code:
- `src/` application source code, organized by feature or domain.
- `tests/` automated tests mirroring `src/` paths.
- `assets/` static files (images, fixtures, sample data).
- `docs/` architecture notes, ADRs, and onboarding docs.

Example: `src/video/transcoder.ts` with matching `tests/video/transcoder.test.ts`.

## Build, Test, and Development Commands
No build tooling is configured yet. Once initialized, expose a minimal standard command set:
- `npm run dev` starts the local development workflow.
- `npm run build` creates production artifacts.
- `npm test` runs the full automated test suite.
- `npm run lint` checks formatting and static analysis.

If you choose a different stack (for example, `make` or `just`), document equivalent commands in `README.md` and keep this section updated.

## Coding Style & Naming Conventions
Use repository-wide defaults unless a formatter/linter defines otherwise:
- Indentation: 2 spaces for JS/TS/JSON/YAML; 4 spaces for Python.
- File names: `kebab-case` for files, `PascalCase` for classes/components, `camelCase` for variables/functions.
- Keep modules focused; prefer small, testable functions over large scripts.
- Adopt automated formatting early (Prettier + ESLint or language-native equivalents).

## Testing Guidelines
Place tests under `tests/` or next to code as `*.test.*` / `*.spec.*`. Minimum expectation for each PR:
- unit tests for new logic,
- regression tests for bug fixes,
- updated fixtures when behavior changes.

Target meaningful coverage for core logic (suggested baseline: 80%+ for new modules).

## Commit & Pull Request Guidelines
Git history is not established yet, so use Conventional Commits from the start:
- `feat: add clip timeline parser`
- `fix: handle empty frame batches`
- `docs: update setup instructions`

PRs should include:
- concise summary of what changed and why,
- linked issue/task (`Closes #123` when applicable),
- test evidence (command output or CI link),
- screenshots/video for UI changes.

## Security & Configuration Tips
Do not commit secrets. Keep local configuration in `.env` and commit only `.env.example`. Validate inputs at boundaries (API, file upload, external integrations) and prefer least-privilege credentials for all services.
