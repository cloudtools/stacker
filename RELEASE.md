# Steps to release a new version

## Preparing for the release

- Check out a branch named for the version: `git checkout -b release-1.1.1`
- Change version in setup.py and stacker/\_\_init\_\_.py
- Update CHANGELOG.md with changes made since last release (see below for helpful
  command)
- add changed files: `git add setup.py stacker/\_\_init\_\_.py CHANGELOG.md`
- Commit changes: `git commit -m "Release 1.1.1"`
- Create a signed tag: `git tag --sign -m "Release 1.1.1" 1.1.1`
- Push branch up to git: `git push -u origin release-1.1.1`
- Open a PR for the release, ensure that tests pass

## Releasing

- Push tag: `git push --tags`
- Merge PR into master, checkout master locally: `git checkout master; git pull`
- Create PyPI release: `python setup.py sdist upload --sign`
- Update github release page: https://github.com/cloudtools/stacker/releases 
  - use the contents of the latest CHANGELOG entry for the body.

# Helper to create CHANGELOG entries
git log --reverse --pretty=format:"%s" | tail -100 | sed 's/^/- /'
