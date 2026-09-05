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

Starter exclusion aligns the supplied tokens with a student answer once and
removes aligned passages of at least eight tokens. Insertions split passages
instead of preventing all exclusion. It chooses the more complete alignment
using original or normalized identifier spellings, so added local declarations
and consistent renaming can both be handled. Shorter common fragments stay in
the answer, and a repeated passage is not excluded more times than it occurs in
the starter. This conservative threshold can retain small scaffold fragments;
it does not infer authorship of code beyond the supplied starter.

Identifier normalization follows declaration order, nested blocks, and loop
initializer scopes. Function names, type names, and prototype parameter names
are preserved; ordinary local variables and function parameters are normalized,
including pointer declarators. This is syntactic binding over Tree-sitter's C
tree, without macro expansion or full compiler name resolution.
