# Guidance for AI Agents

This document provides context for AI assistants (like Claude Code) working on this project.

## Project Structure

- **Source**: `src/pytest_adbc_replay/` - All package code
- **Tests**: `tests/` - Pytest test suite with fixtures in conftest.py
- **Build**: uv + pyproject.toml, uv_build backend
- **Python**: >=3.11, strict type checking enabled

## Quality Gates (Mandatory)

All code must pass these checks before committing. We use [prek](https://prek.j178.dev/) — a fast, Rust-based runner for `.pre-commit-config.yaml` hooks:

```bash
prek run --all-files  # Runs all hooks (typecheck, lint, format, test)
```

Or run individually:
```bash
uv run basedpyright  # Type checking (strict mode)
uv run ruff check    # Linting
uv run ruff format --check  # Format validation
uv run pytest        # Test suite
```

Apply formatting: `uv run ruff format`

## Code Conventions

- **Line length**: 100 characters maximum
- **Docstrings**: Multi-line docstrings use D213 format (summary on second line after opening quotes)
- **Type annotations**: Strict mode enabled, avoid `# type: ignore`, prefer pyproject.toml-level exemptions
- **Import sorting**: Automated via ruff isort (I rules)

## Development Workflow

1. Make changes to source code
2. Run quality gates (typecheck, lint, format, test)
3. Commit with conventional commit format: `<type>(<scope>): <message>`
   - Types: feat, fix, docs, chore, test, refactor, perf, style
4. CI runs automatically on push (if GitHub Actions enabled)

## Type Checking Notes

- `reportPrivateUsage = false` in basedpyright config - tests may access private members
- Use `from __future__ import annotations` only when necessary for forward references
- Use `TYPE_CHECKING` blocks to avoid circular imports

## Testing Patterns

- Fixtures in `tests/conftest.py` (centralized)
- Test classes group related behaviors
- Test naming: `test_<specific_behavior>`
- Coverage reported but not enforced (visibility only)

## Package Structure

- Public API defined in `src/pytest_adbc_replay/__init__.py` via `__all__`
- Version managed in pyproject.toml only (no __version__ in __init__.py)
- Type information available (py.typed marker present)

## Build and Release

- Build: `uv build` (creates wheel + sdist)
- Validate: Test installation in isolated venv before publishing
- Release: Push semver tag (v1.2.3) to trigger automated PyPI publish (if GitHub Actions enabled)

## Common Commands

```bash
# Development setup
uv sync --dev

# Run all quality checks
prek run --all-files

# Run quality checks individually
uv run basedpyright && uv run ruff check && uv run ruff format --check && uv run pytest

# Auto-fix formatting and linting
uv run ruff format && uv run ruff check --fix

# Run tests with coverage
uv run pytest --cov=src/pytest_adbc_replay --cov-report=term

# Build package
uv build
```

## Documentation

### Skills for documentation tasks

Subagents (gsd-executor, gsd-planner, etc.) do not have access to the `Skill` tool. When a plan includes documentation tasks, the planner must include skill files directly in the plan's `<execution_context>` block so the executor has the instructions inline.

For any PLAN.md that writes or substantially rewrites documentation, add to its `<execution_context>`:

```
@/Users/paul/.claude/skills/diataxis-documentation/SKILL.md
@/Users/paul/.claude/skills/diataxis-documentation/references/tutorials.md
@/Users/paul/.claude/skills/diataxis-documentation/references/how-to-guides.md
@/Users/paul/.claude/skills/diataxis-documentation/references/reference.md
@/Users/paul/.claude/skills/diataxis-documentation/references/explanation.md
@/Users/paul/.claude/skills/humanizer/SKILL.md
```

### When to apply

- **New pages:** full diataxis + humanizer workflow (mandatory)
- **Major rewrites (>50% of page changed):** full workflow (mandatory)
- **Minor fixes (typos, version numbers, small corrections):** not required

### Humanizer pass

Every task that produces or substantially modifies a `.md` file must include an explicit sub-step: apply humanizer review and edit in place before marking the task done. Check for: AI vocabulary, em-dash overuse, rule-of-three, promotional language, `-ing` phrase endings.

### Content types

- **Tutorial** (`docs/src/tutorial/`): Learning-oriented, guided from install to first working replay. Copy-pasteable code at every step.
- **How-to guides** (`docs/src/how-to/`): Goal-oriented, assumes reader knows the basics. Solve one specific task per guide.
- **Reference** (`docs/src/reference/`): Auto-generated via mkdocstrings + `gen_ref_pages.py` for module API. Hand-crafted pages for config keys, CLI flags, fixtures, markers, record modes, cassette format.
- **Explanation** (`docs/src/explanation/`): Understanding-oriented, "why" not "how". No step-by-step instructions — link to tutorials/how-tos for action items.

### Writing voice

- **Audience:** Python/pytest users who want to test against a real database without running one in CI
- **Tone:** Direct and practical (like pytest's own docs)
- **Perspective:** Second person ("you") for Tutorial and How-To; neutral for Reference and Explanation

## Notes for Agents

- Always run quality gates before committing
- Follow conventional commit format for commit messages
- Add new dev dependencies to `[dependency-groups]` dev section in pyproject.toml
- Update __all__ in __init__.py when adding public APIs
- Write tests for new features (prefer TDD when appropriate)
