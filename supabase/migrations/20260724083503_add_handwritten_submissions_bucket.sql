INSERT INTO storage.buckets (
  id,
  name,
  owner,
  created_at,
  updated_at,
  public,
  avif_autodetection,
  file_size_limit,
  allowed_mime_types,
  owner_id,
  type
)
VALUES (
  'handwritten-submissions',
  'handwritten-submissions',
  NULL,
  now(),
  now(),
  true,
  false,
  NULL,
  NULL,
  NULL,
  'STANDARD'
)
ON CONFLICT (id) DO UPDATE
SET
  name = EXCLUDED.name,
  public = EXCLUDED.public,
  avif_autodetection = EXCLUDED.avif_autodetection,
  file_size_limit = EXCLUDED.file_size_limit,
  allowed_mime_types = EXCLUDED.allowed_mime_types,
  type = EXCLUDED.type,
  updated_at = now();