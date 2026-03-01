"""Copy the project CHANGELOG.md into the docs virtual filesystem."""

from pathlib import Path

import mkdocs_gen_files

changelog_src = Path("CHANGELOG.md")

with mkdocs_gen_files.open("changelog.md", "w") as f:
    f.write(changelog_src.read_text())
