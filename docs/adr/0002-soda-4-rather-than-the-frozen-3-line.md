# 2. Soda 4, and not the line that carries SodaCL

Accepted, 29 August 2026.

## Context

The vendor-facing contract is executed by Soda against the candidate file. Soda ships in two
lines that are not compatible with each other, and most of the writing about it describes the
older one.

## Decision

Use `soda-core` and `soda-duckdb` at 4.22.0, with contracts as the interface.

The alternative, and the reason it was rejected, verified against the package index rather than
against a changelog:

| package | version | requires-python | its DuckDB pin |
|---|---|---|---|
| `soda-core-duckdb` (the SodaCL line) | 3.5.6, frozen | **none declared** | **`duckdb<1.1.0`** |
| `soda-duckdb` (the contracts line) | 4.22.0 | `>=3.10` | `duckdb>=1.2.0` |

This repository reads DuckDB 1.5, so the 3.x line cannot be installed beside it. A package that
declares no `requires-python` at all will also install itself on an interpreter it has never been
tested against and fail later, which is worse than refusing.

## Consequences

SodaCL check syntax does not apply here and no example written for it will run. Two things the
day-zero smoke test found, which no changelog states:

- the DuckDB data source infers its connection class from the KEY it is handed, so `path:` fails
  with `Could not infer DuckDB connection type from input`, a message that reads as a complaint
  about the value. The key is `database:`.
- a dataset is addressed as `data source / database / schema / table`.

Both are recorded in the committed contract files with the reason beside them.

Soda Cloud is deliberately not used. The contract runs locally, against a file, with no account,
which is what makes it something a vendor can be handed rather than invited to.
