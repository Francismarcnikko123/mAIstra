# Similarity detector fixtures

These small C programs cover the detector's intended boundaries:

- `exact_a.c` and `exact_b.c` are byte-for-byte duplicate answers.
- `renamed_a.c` and `renamed_b.c` use the same solution with consistent local
  and parameter renaming.
- `independent_a.c` and `independent_b.c` are different correct ways to sum a
  range and must remain below the 60% review threshold.
- `starter.c` is shared instructor code. Its tokens must not count toward a
  student pair's evidence.

The detector uses five-token k-grams, four-hash Winnowing windows, a minimum
matching passage of 12 tokens, and a 60% coverage review threshold.
