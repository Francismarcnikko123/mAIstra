export const environment = {
  production: false,
  supabaseUrl: 'https://cvtshfshqccuncamvnkl.supabase.co',
  // Publishable key. Exposing it is unavoidable -- the build inlines it into
  // the browser bundle -- so it is never the access control. What the key can
  // reach is decided server-side by grants and RLS in supabase/migrations/.
  // Replaced the legacy JWT key, which Supabase disabled on 2026-09-21.
  supabaseKey: 'sb_publishable_JVg6v4EDytH23pzt3kYqjA_erNxp_dr'
};
