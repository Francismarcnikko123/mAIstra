# Supabase Local Development Setup and CLI Commands

This guide explains how to run Supabase locally, connect it to a hosted Supabase project, and manage database migrations using the Supabase CLI.

> **Important:** Supabase local development requires a Docker-compatible container runtime. Docker Desktop is the preferred option. Do not expose the local Supabase stack directly to a public network.

---

## 1. Prerequisites

Install the following:

- [Node.js](https://nodejs.org/) and npm, pnpm, or Yarn
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) or another Docker-compatible container runtime
- A Supabase account and hosted project, if you need remote synchronization

Confirm that Docker is running before starting Supabase.

---

## 2. Install the Supabase CLI

### Recommended: Install in the project

Using npm:

```bash
npm install supabase --save-dev
```

Run commands through `npx`:

```bash
npx supabase --version
```

Using pnpm:

```bash
pnpm add -D supabase
pnpm supabase --version
```

Using Yarn:

```bash
yarn add --dev supabase
yarn supabase --version
```

### macOS with Homebrew

```bash
brew install supabase/tap/supabase
supabase --version
```

> The examples below use `npx supabase`. Replace it with `supabase`, `pnpm supabase`, or `yarn supabase` depending on how you installed the CLI.

---

## 3. Initialize Supabase in Your Project

Go to your application directory:

```bash
cd your-project
```

Initialize Supabase:

```bash
npx supabase init
```

This creates a structure similar to:

```text
supabase/
├── config.toml
├── migrations/
└── seed.sql
```

The exact generated files can vary depending on the CLI version and project configuration.

---

## 4. Start the Local Supabase Stack

Make sure Docker is running, then execute:

```bash
npx supabase start
```

The command starts the local services, including PostgreSQL, Auth, Storage, the API, and Supabase Studio.

After startup, the terminal displays local values such as:

- API URL
- GraphQL URL
- Database URL
- Studio URL
- Anonymous key
- Service-role key

The local Studio normally opens at:

```text
http://localhost:54323
```

Check the current local status and credentials:

```bash
npx supabase status
```

Stop the local stack while preserving its Docker volumes:

```bash
npx supabase stop
```

Stop it and delete its local data volumes:

```bash
npx supabase stop --no-backup
```

> Save schema and seed changes before using `--no-backup`, because the local database data will be removed.

---

## 5. Local Environment Variables

Copy the values printed by `supabase start` or `supabase status` into your application's local environment file.

Example:

```env
SUPABASE_URL=http://127.0.0.1:54321
SUPABASE_ANON_KEY=your-local-anon-key
```

The Judge0 API also hosts the similarity routes. Give that server a direct
local PostgreSQL connection in `judge0_api/.env`:

```env
DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:54322/postgres
```

The Angular client calls the service through
`http://127.0.0.1:8001/api/similarity`. Start the Python API on port 8001 and
apply the local migrations before using Check similarity. The API derives the
assessment/question group from the requested submission ID; it does not accept
browser-supplied assessment IDs or source code.

To run the real repository checks against local Postgres in PowerShell:

```powershell
$env:SIMILARITY_TEST_DATABASE_URL = 'postgresql://postgres:postgres@127.0.0.1:54322/postgres'
python -m pytest judge0_api/tests_similarity_repository.py -q
```

These tests refuse non-loopback hosts and delete only their randomly named
fixture cohorts. Production access still requires authenticated API routes and
assessment-level authorization; the similarity tables have RLS enabled and no
permissive browser policy.

For an Angular application, you may store the values in an environment configuration file:

```typescript
export const environment = {
  production: false,
  supabaseUrl: 'http://127.0.0.1:54321',
  supabaseAnonKey: 'your-local-anon-key',
};
```

Never expose the service-role key in browser or client-side code.

---

## 6. Log In and Link a Hosted Supabase Project

Log in to the Supabase CLI:

```bash
npx supabase login
```

You can find the project reference in the hosted project's dashboard URL or project settings.

Link the local repository to the hosted project:

```bash
npx supabase link --project-ref YOUR_PROJECT_REF
```

The CLI may request the hosted database password.

Verify migration synchronization:

```bash
npx supabase migration list
```

---

# Database Migration Workflow

## 7. Create a Migration Manually

Create an empty migration file:

```bash
npx supabase migration new create_profiles_table
```

A timestamped SQL file will be created:

```text
supabase/migrations/<timestamp>_create_profiles_table.sql
```

Add SQL to the migration file:

```sql
create table public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  full_name text,
  created_at timestamptz not null default now()
);

alter table public.profiles enable row level security;
```

Apply and test all migrations locally:

```bash
npx supabase db reset
```

`db reset` recreates the local database, applies every migration in timestamp order, and then runs the configured seed files.

---

## 8. Generate a Migration from Local Dashboard Changes

You can modify the schema through the **local** Supabase Studio, then generate the SQL difference:

```bash
npx supabase db diff -f add_profiles_table
```

This creates a new migration under:

```text
supabase/migrations/
```

Review the generated SQL before committing it.

Test the generated migration from a clean state:

```bash
npx supabase db reset
```

You can restrict the diff to selected schemas:

```bash
npx supabase db diff --schema public -f update_public_schema
```

> Once your project uses migrations, prefer making schema changes locally and deploying them through migration files. Direct remote Dashboard changes can make migration history inconsistent.

---

## 9. Apply Pending Migrations Without a Full Reset

Apply migrations that have not yet run on the local database:

```bash
npx supabase migration up
```

A full reset is usually better for verifying that the entire migration history can recreate the database correctly:

```bash
npx supabase db reset
```

---

## 10. Pull the Remote Schema

Before pulling, link the project:

```bash
npx supabase link --project-ref YOUR_PROJECT_REF
```

Pull hosted schema changes into a new local migration:

```bash
npx supabase db pull
```

Optionally provide a migration name:

```bash
npx supabase db pull remote_schema
```

After pulling, rebuild the local database:

```bash
npx supabase db reset
```

Use `db pull` when adopting an existing hosted database or when legitimate remote schema changes need to be captured locally.

> `db pull` requires Docker because the CLI uses a local database container to calculate the schema difference.

---

## 11. Push Local Migrations to the Hosted Project

Preview which migrations will be applied:

```bash
npx supabase db push --dry-run
```

Apply pending local migrations to the linked hosted project:

```bash
npx supabase db push
```

Include configured seed data when intentionally needed:

```bash
npx supabase db push --include-seed
```

Only one team member or deployment process should push migrations at a time to avoid migration-history conflicts.

---

## 12. View Migration History

Compare local migrations with the linked hosted project's migration history:

```bash
npx supabase migration list
```

Migration files are tracked locally in:

```text
supabase/migrations/
```

The hosted project tracks applied versions in Supabase's migration history table.

---

## 13. Repair Migration History

Use migration repair only when the SQL schema and migration-history records are out of sync and you understand which migration version needs correction.

Mark a migration as applied:

```bash
npx supabase migration repair MIGRATION_TIMESTAMP --status applied
```

Mark a migration as reverted:

```bash
npx supabase migration repair MIGRATION_TIMESTAMP --status reverted
```

Example:

```bash
npx supabase migration repair 20260724090000 --status applied
```

Then verify the result:

```bash
npx supabase migration list
```

> Repair changes migration-history records; it does not automatically execute the SQL contained in the migration.

---

## 14. Seed Local Test Data

Place repeatable development data in:

```text
supabase/seed.sql
```

Example:

```sql
insert into public.categories (name)
values
  ('Technology'),
  ('Education'),
  ('Agriculture')
on conflict do nothing;
```

Run all migrations and seed data:

```bash
npx supabase db reset
```

Reset without running seed data:

```bash
npx supabase db reset --no-seed
```

Export local data into a seed file when appropriate:

```bash
npx supabase db dump --local --data-only > supabase/seed.sql
```

Review exported data before committing it. Do not commit passwords, private user information, production records, or other secrets.

---

## 15. Dump a Database

Dump the linked hosted database schema:

```bash
npx supabase db dump -f supabase/schema.sql
```

Dump hosted data only:

```bash
npx supabase db dump --data-only -f supabase/data.sql
```

Dump local data only:

```bash
npx supabase db dump --local --data-only -f supabase/local-data.sql
```

Database dumps and migration files serve different purposes. Migrations represent incremental changes; dumps capture a database state or selected content.

---

## 16. Generate TypeScript Types

Generate types from the local database:

```bash
npx supabase gen types --lang typescript --local > src/app/types/database.types.ts
```

Generate types from the linked hosted project:

```bash
npx supabase gen types --lang typescript --linked > src/app/types/database.types.ts
```

Generate types from a specific hosted project reference:

```bash
npx supabase gen types --lang typescript --project-id YOUR_PROJECT_REF > src/app/types/database.types.ts
```

Regenerate types whenever the database schema changes.

---

## 17. Database Linting

Check the local database for schema or PL/pgSQL issues:

```bash
npx supabase db lint
```

Treat warnings as errors when needed:

```bash
npx supabase db lint --level error
```

---

# Common Workflows

## 18. New Project Without an Existing Remote Schema

```bash
npm install supabase --save-dev
npx supabase init
npx supabase start
npx supabase migration new initial_schema
# Add SQL to the generated migration file
npx supabase db reset
npx supabase link --project-ref YOUR_PROJECT_REF
npx supabase db push --dry-run
npx supabase db push
```

---

## 19. Existing Hosted Project to Local Development

```bash
npm install supabase --save-dev
npx supabase init
npx supabase login
npx supabase link --project-ref YOUR_PROJECT_REF
npx supabase db pull initial_remote_schema
npx supabase start
npx supabase db reset
```

Review the pulled migration before making further changes.

---

## 20. Daily Local Development

```bash
npx supabase start

# Make schema changes locally, then capture them:
npx supabase db diff -f describe_your_change

# Verify all migrations from scratch:
npx supabase db reset

# Regenerate application types:
npx supabase gen types --lang typescript --local > src/app/types/database.types.ts

# Review and commit:
git add supabase/migrations src/app/types/database.types.ts
git commit -m "Add database migration"
```

---

## 21. Pull a Teammate's Migrations

```bash
git pull
npx supabase db reset
```

This reapplies the repository's complete migration history locally.

---

## 22. Deploy Database Changes

```bash
npx supabase migration list
npx supabase db push --dry-run
npx supabase db push
```

After deployment, you can verify migration history again:

```bash
npx supabase migration list
```

---

# Command Cheat Sheet

| Command | Purpose |
|---|---|
| `npx supabase init` | Create local Supabase configuration |
| `npx supabase start` | Start the local Supabase stack |
| `npx supabase status` | Display local service URLs and credentials |
| `npx supabase stop` | Stop local services and preserve data |
| `npx supabase stop --no-backup` | Stop services and delete local data volumes |
| `npx supabase login` | Authenticate the CLI |
| `npx supabase link --project-ref <ref>` | Link the repository to a hosted project |
| `npx supabase migration new <name>` | Create an empty migration file |
| `npx supabase db diff -f <name>` | Generate a migration from schema differences |
| `npx supabase migration up` | Apply pending migrations locally |
| `npx supabase db reset` | Recreate the local DB, run migrations, and seed it |
| `npx supabase db pull [name]` | Pull hosted schema changes into a migration |
| `npx supabase db push --dry-run` | Preview hosted migration deployment |
| `npx supabase db push` | Apply pending migrations to the hosted project |
| `npx supabase migration list` | Compare local and hosted migration histories |
| `npx supabase migration repair <version> --status <status>` | Correct migration-history records |
| `npx supabase db dump` | Export schema or data |
| `npx supabase db lint` | Check database schema and functions for issues |
| `npx supabase gen types --local` | Generate types from the local database |
| `npx supabase gen types --linked` | Generate types from the linked hosted database |

---

# Recommended Git Files

Commit these files when applicable:

```text
supabase/config.toml
supabase/migrations/*.sql
supabase/seed.sql
```

Do not commit local secrets, database passwords, access tokens, or production data.

A project-specific `.gitignore` may include:

```gitignore
.env
.env.*
!.env.example
supabase/.temp/
```

Review the CLI-generated ignore rules and your team's deployment setup before changing them.

---

# Troubleshooting

## Docker is not running

Start Docker Desktop, then retry:

```bash
npx supabase start
```

## Port conflict

Another service may already be using a configured port. Stop the conflicting service or edit `supabase/config.toml`, then restart:

```bash
npx supabase stop
npx supabase start
```

## Local schema does not match migration files

Recreate the local database:

```bash
npx supabase db reset
```

Any unrecorded local schema or data changes will be discarded.

## Local and hosted migration histories differ

Inspect both histories:

```bash
npx supabase migration list
```

Pull legitimate remote changes when appropriate:

```bash
npx supabase db pull
npx supabase db reset
```

Use `migration repair` only after identifying the exact history mismatch.

## CLI version problems

Check the installed version:

```bash
npx supabase --version
```

Update the project dependency:

```bash
npm install supabase@latest --save-dev
```

Before deleting local containers during a CLI upgrade, capture any uncommitted schema and seed changes.

---

# Official References

- [Supabase Local Development](https://supabase.com/docs/guides/local-development)
- [Supabase CLI Getting Started](https://supabase.com/docs/guides/local-development/cli/getting-started)
- [Local Development Workflow](https://supabase.com/docs/guides/local-development/cli-workflows)
- [Database Migrations](https://supabase.com/docs/guides/deployment/database-migrations)
- [Supabase CLI Reference](https://supabase.com/docs/reference/cli/getting-started)

---

_Last verified against the official Supabase documentation on July 24, 2026. CLI behavior and flags can change, so check `npx supabase <command> --help` when using a newer version._
