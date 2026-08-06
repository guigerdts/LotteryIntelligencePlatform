# Code Review Rules

## Python

- Use `src-layout` packaging; import path `backend.app`.
- Modules and functions are documented with docstrings (responsibility first).
- Package seams (`__init__.py`) contain docstrings only — no logic, tables, or routes in scaffolds.
- Lint with ruff (`E`,`F`,`I`,`UP`,`B`), line-length 100; format with `ruff format`.
- Conventional commits only (`feat`, `fix`, `chore`, `build`, `refactor`, etc.); no AI attribution.
- Code is English; log format `%(asctime)s|%(levelname)s|%(name)s|%(message)s`.
- Config single-source via pydantic-settings `Settings`; secrets from env only.
- No business/engine logic, schema, or migrations in the Fase 0 scaffold.