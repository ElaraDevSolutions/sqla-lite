# Contributing to sqla-lite

Thanks for your interest in contributing to **sqla-lite**.

## Development Setup

1. Clone the repository.
2. Create and activate a virtual environment.
3. Install development dependencies:

```bash
pip install -r requirements.txt
```

## Run Tests

```bash
pytest -v
```

## Code Guidelines

- Keep changes focused and minimal.
- Preserve existing public APIs unless the change explicitly requires breaking behavior.
- Follow the current code style used in the project.

## Pull Request Checklist

All changes must be submitted via Pull Request. Direct changes to `main` are not part of the regular contribution flow.

- [ ] Tests pass locally.
- [ ] New behavior is covered by tests when applicable.
- [ ] Documentation is updated (`README.md` for usage, this file for contribution flow).
- [ ] PR description explains what changed and why.

## Versioning and PyPI Publish

Versioning and publishing are automated by GitHub Actions.

When a PR is merged into `main` (or when the version workflow is triggered manually), the action:

1. Determines the next version (or uses the provided manual version input).
2. Updates version files.
3. Creates and pushes the release tag.
4. Triggers the PyPI publish workflow automatically.

To allow one workflow to create tags and trigger another workflow, configure the repository secret `RELEASE_PUSH_TOKEN` with a Personal Access Token that has permission to write repository contents/workflows.

Do not create release tags manually for the normal release flow.
