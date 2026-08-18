# Switching Between Local and Cloud Supabase in Angular

This guide shows how to switch an Angular application between a local Supabase instance and a hosted Supabase project.

## 1. Create Two Environment Files

### Local Supabase

Create:

```text
src/environments/environment.development.ts
```

Add:

```ts
export const environment = {
  production: false,
  supabaseUrl: 'http://127.0.0.1:54321',
  supabaseKey: 'YOUR_LOCAL_ANON_OR_PUBLISHABLE_KEY',
};
```

Start local Supabase and view the local credentials:

```bash
npx supabase start
npx supabase status
```

Copy the local API URL and anon or publishable key into the environment file.

---

### Cloud Supabase

Use:

```text
src/environments/environment.ts
```

Add:

```ts
export const environment = {
  production: true,
  supabaseUrl: 'https://YOUR_PROJECT_REF.supabase.co',
  supabaseKey: 'YOUR_CLOUD_ANON_OR_PUBLISHABLE_KEY',
};
```

You can get the cloud project URL and publishable or anon key from the Supabase dashboard.

Do not put a service-role key or secret key in Angular frontend code.

---

## 2. Use One Supabase Client

Create or update your Supabase client:

```ts
import { createClient } from '@supabase/supabase-js';
import { environment } from '../environments/environment';

export const supabase = createClient(
  environment.supabaseUrl,
  environment.supabaseKey
);
```

Your queries and services do not need to change when switching environments.

---

## 3. Configure Angular File Replacement

Open:

```text
angular.json
```

Under the development build configuration, make sure this exists:

```json
{
  "development": {
    "fileReplacements": [
      {
        "replace": "src/environments/environment.ts",
        "with": "src/environments/environment.development.ts"
      }
    ]
  }
}
```

Angular will replace the cloud environment file with the local environment file when using the development configuration.

---

## 4. Connect to Local Supabase

Start Supabase:

```bash
npx supabase start
```

Run Angular using the development configuration:

```bash
ng serve --configuration development
```

Your application will use:

```text
http://127.0.0.1:54321
```

To stop local Supabase:

```bash
npx supabase stop
```

---

## 5. Connect to Cloud Supabase

Build the production version:

```bash
ng build --configuration production
```

To serve the application locally while using the cloud environment, you can run:

```bash
ng serve --configuration production
```

Be careful because this connects your local frontend directly to the hosted database.

---

## 6. Quick Reference

### Local

```bash
npx supabase start
ng serve --configuration development
```

Uses:

```text
src/environments/environment.development.ts
```

### Cloud

```bash
ng serve --configuration production
```

or:

```bash
ng build --configuration production
```

Uses:

```text
src/environments/environment.ts
```

---

## Important Notes

Switching the environment changes only the Supabase URL and browser-safe key.

Local and cloud Supabase have separate:

- Database records
- Authentication users and sessions
- Storage files and buckets
- Edge Function secrets
- Redirect URLs
- Database schema, unless migrations have been applied to both

Keep your database schema synchronized using Supabase migrations.

Example:

```bash
npx supabase migration new add_profiles_table
npx supabase db reset
npx supabase db push
```
