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

- [ ] Tests pass locally.
- [ ] New behavior is covered by tests when applicable.
- [ ] Documentation is updated (`README.md` for usage, this file for contribution flow).
- [ ] PR description explains what changed and why.

## Versioning and PyPI Publish

This project publishes to PyPI through GitHub Actions when a tag like `v1.0.0` is pushed.

Basic release flow:

```bash
git checkout main
git pull
git tag -a vX.Y.Z -m "Release vX.Y.Z"
git push origin vX.Y.Z
```

Make sure the version in `pyproject.toml` matches the tag (`X.Y.Z`).
