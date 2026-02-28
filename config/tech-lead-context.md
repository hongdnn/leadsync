# Tech Lead Context — LeadSync Team

## Architectural Preferences

- **Async everywhere**: All I/O-bound operations must use `async`/`await`. Synchronous
  calls in endpoint handlers are a blocking bug, not a style choice.
- **Thin controllers, fat services**: Endpoint handlers validate input and delegate immediately.
  No business logic in `main.py`. If a handler is over 20 lines, it belongs in a service.
- **Explicit over implicit**: No magic imports, no auto-wired globals. Every dependency is
  passed explicitly or resolved via a factory function.
- **Fail fast, fail loud**: Validate at the boundary. Return 400, log the reason, stop.

## Non-Negotiables

- **No new global state**: Module-level mutable objects are a design smell — flag before implementing.
- **No raw SQL strings**: All queries go through the ORM or a parameterized builder. No exceptions.
- **Tests before merge**: A PR without tests does not get reviewed. Coverage must not drop.

## Team Notes

- **Alice** owns the database layer. Tickets touching the schema: check with Alice first.
- **Bob** owns the auth layer. Tokens, sessions, permissions: Bob reviews and signs off.
- **Default storage assumption**: PostgreSQL relational patterns, not document-oriented.

## Per-Label Rules

- **backend**: Every new endpoint needs a rate limit annotation. Third-party API calls need
  retry logic with exponential backoff.
- **frontend**: Components are pure where possible. Side effects belong in hooks, not render.
  Every interactive element needs an accessibility label.
- **database**: Fewer than 3 tightly-coupled columns → extend existing table. More than 3
  columns or new entity → new table. Junction data → always a join table, never a JSON column.

## Schema Decision Rule

When asked "extend table X or create a new table?":
- < 3 new columns tightly coupled to existing entity → extend.
- New entity with its own lifecycle, or > 3 columns → new table.
- Relationship/junction data → new join table always.

## Common Patterns

- HTTP clients: `httpx` with a shared client instance, not `requests`.
- Background tasks: FastAPI `BackgroundTasks` for lightweight work; Celery only if already in stack.
- Error responses: always `{"detail": "..."}` shape.
- Logging: Python's standard `logging` module. No `print()` in production code.
