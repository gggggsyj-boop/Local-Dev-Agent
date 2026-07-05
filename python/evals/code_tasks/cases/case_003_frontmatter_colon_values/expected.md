Expected fix:

- metadata values can contain colons.
- malformed frontmatter without a closing delimiter is returned as normal body text.
- lines without `:` inside frontmatter are ignored.
- Tests should not be modified.

