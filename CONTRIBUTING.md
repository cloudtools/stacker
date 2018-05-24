# Contributing

Contributions are welcome, and they are greatly appreciated!

You can contribute in many ways:

## Types of Contributions

### Report Bugs

Report bugs at https://github.com/cloudtools/stacker/issues.

If you are reporting a bug, please include:

* Your operating system name and version.
* Any details about your local setup that might be helpful in troubleshooting.
* Detailed steps to reproduce the bug.

### Fix Bugs

Look through the GitHub issues for bugs. Anything tagged with "bug"
is open to whoever wants to implement it.

### Implement Features

Look through the GitHub issues for features. Anything tagged with "feature"
is open to whoever wants to implement it.

### Write Documentation

stacker could always use more documentation, whether as part of the
official stacker docs, in docstrings, or even on the web in blog posts,
articles, and such.

Note: We use Google style docstrings (http://sphinxcontrib-napoleon.readthedocs.io/en/latest/example\_google.html)

### Submit Feedback

The best way to send feedback is to file an issue at https://github.com/cloudtools/stacker/issues.

If you are proposing a feature:

* Explain in detail how it would work.
* Keep the scope as narrow as possible, to make it easier to implement.
* Remember that this is a volunteer-driven project, and that contributions
  are welcome :)


## Get Started!

Ready to contribute? Here's how to set up `stacker` for local development.

1. Fork the `stacker` repo on GitHub.
2. Clone your fork locally:

    ```console
    $ git clone git@github.com:your_name_here/stacker.git
    ```

3. Install your local copy into a virtualenv. Assuming you have virtualenvwrapper installed, this is how you set up your fork for local development:

    ```console
    $ mkvirtualenv stacker
    $ cd stacker/
    $ python setup.py develop
    ```

4. Create a branch for local development:

    ```console
    $ git checkout -b name-of-your-bugfix-or-feature
    ```

   Now you can make your changes locally.

5. When you're done making changes, check that your changes pass flake8 and the tests, including testing other Python versions with tox:

    ```console
    $ make test
    ```

   To get flake8 just pip install it into your virtualenv.

6. Commit your changes and push your branch to GitHub:

    ```console
    $ git add .
    $ git commit -m "Your detailed description of your changes."
    $ git push origin name-of-your-bugfix-or-feature
    ```

7. Submit a pull request through the GitHub website.

For information about the functional testing suite, see [tests/README.md](./tests).

## Pull Request Guidelines

Before you submit a pull request, check that it meets these guidelines:

1. The pull request should include tests.
2. If the pull request adds functionality, the docs should be updated. (See `Write Documentation` above for guidelines)
3. The pull request should work for Python 2.7 and for PyPy. Check
   https://circleci.com/gh/cloudtools/stacker and make sure that the tests pass for all supported Python versions.
4. Please update the `Upcoming/Master` section of the [CHANGELOG](./CHANGELOG.md) with a small bullet point about the change.
