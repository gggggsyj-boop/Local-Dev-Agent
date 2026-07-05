Expected fix:

- `slugify("Hello, World!")` returns `hello-world`.
- repeated spaces and punctuation do not produce repeated dashes.
- leading/trailing whitespace is removed from the final slug.
- Tests should not be modified.

