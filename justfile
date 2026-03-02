default:
    @just --list

setup-claude:
    npx get-shit-done-cc --claude --local
    npx skills add abatilo/vimrc/plugins/abatilo-core/skills/diataxis-documentation -a claude-code -y
    npx skills add blader/humanizer -a claude-code -y

# Build the docs site (strict mode)
docs-build:
    uv run --group docs mkdocs build --strict

# Serve the docs dev server (default port 8000)
docs-serve port="8000":
    uv run --group docs mkdocs serve --dev-addr 127.0.0.1:{{port}} --livereload
