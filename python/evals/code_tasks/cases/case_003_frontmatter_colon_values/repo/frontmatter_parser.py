def parse_frontmatter(text):
    if not text.startswith("---\n"):
        return {}, text

    _, header, body = text.split("---", 2)
    meta = {}
    for line in header.strip().splitlines():
        key, value = line.split(":")
        meta[key.strip()] = value.strip()
    return meta, body.strip()

