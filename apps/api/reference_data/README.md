# Reference data (`apps/api/reference_data/`)

## What this folder is for

It holds **CSV templates** and, later, **your own verified datasets**.

It deliberately does **not** contain a list of Indian states, districts, mandis or
commodities. Shipping a hand-made list and calling it "official" would be a
fabricated government dataset, which this project will never do.

## Where the data must come from

You need a source you can name. Acceptable options:

- a state or central government open-data portal,
- a state agricultural marketing authority (APMC / agri-market) publication,
- an official census or LGD (Local Government Directory) dataset,
- a published handbook you have checked.

For each source record: who published it, the URL, whether it is an official
government body, and any licence conditions.

## Templates

| File | Contents |
|---|---|
| `templates/states.csv` | header only |
| `templates/districts.csv` | header only |
| `templates/mandis.csv` | header only |
| `templates/localities.csv` | header only |
| `templates/commodities.csv` | header only |
| `templates/varieties.csv` | header only |
| `templates/grades.csv` | header only |
| `templates/units.csv` | header only |

Each template contains only the header row, so it can never be mistaken for real
data.

### Column rules

| Entity | Required | Optional |
|---|---|---|
| states | `code`, `name` | `name_hi`, `name_te` |
| districts | `state_code`, `code`, `name` | `name_hi`, `name_te` |
| mandis | `district_code`, `code`, `name` | `name_hi`, `name_te`, `has_storage` |
| localities | `district_code`, `kind`, `name` | `name_hi`, `name_te`, `latitude`, `longitude` |
| commodities | `code`, `name` | `name_hi`, `name_te`, `category` |
| varieties | `commodity_code`, `code`, `name` | `name_hi`, `name_te` |
| grades | `code`, `name` | `commodity_code`, `name_hi`, `name_te` |
| units | `code`, `name`, `dimension` | `name_hi`, `name_te`, `to_base_kg` |

Notes:

- `kind` must be `city`, `town` or `village`.
- `dimension` must be `mass`, `volume`, `count` or `bag`. A `mass` unit **must**
  have a positive `to_base_kg` (kilograms per unit), e.g. `100` for a quintal.
- `name_hi` / `name_te` may be left empty. The platform will then show the
  official name. **Never invent a translation of an official place name.**
- `latitude` / `longitude` are optional. They are copied from the source and are
  **never** used to state a road distance.

## Import order

Parents must exist before children:

```
states → districts → mandis
                 → localities
commodities → varieties → grades
units
```

## How to import (PowerShell)

Always dry run first:

```powershell
cd apps\api
..\..\.venv\Scripts\python.exe -m scripts.import_reference `
  --entity states --file .\reference_data\my_states.csv
```

It prints what *would* change and writes nothing. Then, to actually write:

```powershell
..\..\.venv\Scripts\python.exe -m scripts.import_reference `
  --entity states --file .\reference_data\my_states.csv `
  --source-key my-state-directory --source-name "State statistical handbooks" `
  --url "https://example.org/dataset" --official `
  --apply
```

`--source-key` and `--source-name` are **required** to write. Reference data is
never imported anonymously.

## Duplicate handling

| Situation | Result |
|---|---|
| New row | `inserted` |
| Existing row with changed values | `updated` (re-import is idempotent) |
| Existing row identical to the file | `skipped` |
| Missing required column, or unknown parent | `rejected`, with a reason |

Every run — including dry runs — writes a `reference_import_logs` row.

## Verifying what landed

```powershell
curl.exe http://127.0.0.1:8000/api/v1/reference/status
```

This returns the row counts, the sources, and when each was last imported. Until
something is imported it correctly reports `is_populated: false`.