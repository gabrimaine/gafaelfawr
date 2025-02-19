#################
Development guide
#################

This page provides procedures and guidelines for developing and contributing to Gafaelfawr.

Scope of contributions
======================

Gafaelfawr is an open source package, meaning that you can contribute to Gafaelfawr itself, or fork Gafaelfawr for your own purposes.

Since Gafaelfawr is intended for internal use by Rubin Observatory, community contributions can only be accepted if they align with Rubin Observatory's aims.
For that reason, it's a good idea to propose changes with a new `GitHub issue`_ before investing time in making a pull request.

Gafaelfawr is developed by the LSST SQuaRE team.

.. _GitHub issue: https://github.com/lsst-sqre/gafaelfawr/issues/new

.. _dev-environment:

Setting up a local development environment
==========================================

To develop Gafaelfawr, create a virtual environment with your method of choice (like virtualenvwrapper) and then clone or fork, and install:

.. code-block:: sh

   git clone https://github.com/lsst-sqre/gafaelfawr.git
   cd gafaelfawr
   make init

This init step does three things:

1. Installs Gafaelfawr in an editable mode with its "dev" extra that includes test and documentation dependencies.
2. Installs pre-commit, tox, and tox-docker.
3. Installs the pre-commit hooks.

On macOS hosts, you may also need to run the following in the terminal window where you run ``make init`` and where you intend to run ``tox`` commands:

.. code-block:: sh

   export LDFLAGS="-L/usr/local/opt/openssl/lib"

Otherwise, OpenSSL isn't on the default linker path and some Python extensions may not build.

.. _pre-commit-hooks:

Pre-commit hooks
================

The pre-commit hooks, which are automatically installed by running the :command:`make init` command on :ref:`set up <dev-environment>`, ensure that files are valid and properly formatted.
Some pre-commit hooks automatically reformat code:

``isort``
    Automatically sorts imports in Python modules.

``black``
    Automatically formats Python code.

``blacken-docs``
    Automatically formats Python code in reStructuredText documentation and docstrings.

When these hooks fail, your Git commit will be aborted.
To proceed, stage the new modifications and proceed with your Git commit.

Building the UI
===============

Before running tests or starting a local development server, you must build the UI.
The Gafaelfawr UI is written in JavaScript and contained in the ``ui`` subdirectory.
To build it, run (from the top level):

.. code-block:: sh

   make ui

You will need to have `Node.js <https://nodejs.org/en/>`__ and npm installed.
The easiest way to do this is generally to use `nvm <https://github.com/nvm-sh/nvm>`__.
Gafaelfawr provides an ``.nvmrc`` file that sets the version of Node.js to what is currently used to build the UI in GitHub Actions for the official Docker image.

.. _dev-run-tests:

Running tests
=============

To test all components of Gafaelfawr other than the Kubernetes operator (see below), run tox_, which tests the library the same way that the CI workflow does:

.. code-block:: sh

   tox

This uses tox-docker to start PostgreSQL and Redis Docker containers for the tess to use, so Docker must be installed and the user running tox must have permission to create Docker containers.

To run the Selenium tests, you will need to have ``chromedriver`` installed.
On Debian and Ubuntu systems, you can install this with ``apt install chromium-driver``.

To run the tests with coverage analysis and generate a report, run:

.. code-block:: sh

   tox -e py-coverage,coverage-report

To see a listing of test environments, run:

.. code-block:: sh

   tox -av

To run a specific test or list of tests, you can add test file names (and any other pytest_ options) after ``--`` when executing the ``py`` or ``py-full`` tox environment.
For example:

.. code-block:: sh

   tox -e py -- tests/handlers/api_tokens_test.py

Testing the Kubernetes operator
-------------------------------

To test the Kubernetes operator, you must have a Kubernetes cluster available that is not already running Gafaelfawr.
This is only tested with Minikube_, which is the approach used by CI.

.. _Minikube: https://minikube.sigs.k8s.io/docs/

.. warning::

   The default Kubernetes credentials in your local Kubernetes configuration will be used to run the tests, whatever cluster that points to.
   In theory, you can use a regular Kubernetes cluster and only test namespaces starting with ``test-`` will be affected.

   In practice, this is not tested, and it is possible the tests will damage or destroy other applications or data running on the same Kubernetes cluster.

   If you want to run these tests manually rather than via CI, using Minikube for tests and carefully verifying that the default Kubernetes credentials are for the Minikube environment is strongly encouraged.

To set up Minikube:

#. `Install Minikube <https://minikube.sigs.k8s.io/docs/start/>`__ for your platform.

#. Start a cluster using the Docker driver with the minimum recommended resources:

   .. code-block:: sh

      minikube start --driver=docker --cpus=4 --memory=8g --disk-size=100g  --kubernetes-version=1.21.5

   The ``--kubernetes-version`` option can be used to specify the Kubernetes version to use.

#. Enable the NGINX Ingress Controller using the  `Minikube ingress addon <https://kubernetes.io/docs/tasks/access-application-cluster/ingress-minikube/>`__:

   .. code-block:: sh

   minikube addons enable ingress

To run all of the tests including Kubernetes tests, first check that your default Kubernetes environment is the one in which you want to run tests:

.. code-block:: sh

   kubectl config current-context

Then, run:

.. code-block:: sh

   tox -e py-full

Add the ``coverage-report`` environment to also get a test coverage report.

.. _dev-server:

Starting a development server
=============================

There are two methods to run Gafaelfawr interactively on your local machine for development and testing the UI: outside Docker or inside Docker.
In both cases, you will need Docker to be installed on your local machine.

For either approach, you will first need to create a `GitHub OAuth app <https://github.com/settings/developers>`__ for Gafaelfawr to use.
On GitHub, go to your personal settings page, select developer settings, and then select OAuth Apps.
Create a new OAuth App with the following settings:

* Homepage: ``http://localhost:8080/``
* Authorization callback URL: ``http://localhost:8080/login``

The rest can be set to whatever you want.
Replace ``<github-client-id>`` in ``examples/docker/gafaelfawr.yaml`` and ``examples/gafaelfawr-dev.yaml`` with the resulting client ID.
Put the resulting secret in ``examples/secrets/github-client-secret``.

Now, use one of the two methods below for running Gafaelfawr.

Outside Docker
--------------

Run:

.. code-block:: sh

   tox -e run

This will use ``docker-compose`` to start Redis and PostgreSQL servers, and then will start Gafaelfawr in the foreground outside of Docker.
You can now go to ``http://localhost:8080/auth/tokens`` and will be redirected to GitHub for authentication.

To stop the running server, use Ctrl-C.
You will then need to run:

.. code-block:: sh

   docker-compose down

to stop the Redis and PostgreSQL containers.

The advantage of this method is that the running code and UI will be taken from your current working directory, so you can update it on the fly and immediately see the effects.

Inside Docker
-------------

Build a Docker image and start the development instance of Gafaelfawr with:

.. code-block:: sh

   docker-compose -f examples/docker/docker-compose.yaml --project-directory . build
   docker-compose -f examples/docker/docker-compose.yaml --project-directory . up

You can then go to ``http://localhost:8080/auth/tokens`` and will be redirected to GitHub for authentication.

To stop the running server, use Ctrl -C.
To fully clean up the services, then run:

.. code-block:: sh

   docker-compose -f examples/docker/docker-compose.yaml --project-directory . down

This way of running Gafaelfawr doesn't require you to have its dependencies installed locally and more closely simulates a production deployment.
However, you will need to stop Gafaelfawr, rebuild the Docker container, and then start it again after each change to see your changes reflected.

Building documentation
======================

Documentation is built with Sphinx_:

.. _Sphinx: https://www.sphinx-doc.org/en/master/

.. code-block:: sh

   tox -e docs

The build documentation is located in the :file:`docs/_build/html` directory.

.. _dev-change-log:

Updating the change log
=======================

Each pull request should update the change log (:file:`CHANGELOG.md`).
Add a description of new features and fixes as list items under a section at the top of the change log, using ``unreleased`` for the date portion.
The version number for that heading should be chosen or updated based on the semver_ rules.

.. _semver: https://semver.org/

.. code-block:: markdown

   ## X.Y.Z (unreleased)

   ### Subheading (see below)

   - Description of the feature or fix.

All changelog entries should be divided into sections (each starting with ``###``) chosen from the following:

- **Backward-incompatible changes** (which should also come with a bump in the major version except in unusual cases)
- **New features**
- **Bug fixes**
- **Other changes** (which are mostly new features that are not significant enough to call attention to, such as logging formatting changes or updates to the documentation)

If the exact version and release date is known (:doc:`because a release is being prepared <release>`), the section header is formatted as:

.. code-block:: markdown

   ## X.Y.Z (YYYY-MM-DD)

.. _style-guide:

Style guide
===========

Code
----

- The code style follows :pep:`8`, though in practice lean on Black and isort to format the code for you.

- Use :pep:`484` type annotations.
  The ``tox -e typing`` test environment, which runs mypy_, ensures that the project's types are consistent.

- Write tests for Pytest_.

Documentation
-------------

- Follow the `LSST DM User Documentation Style Guide`_, which is primarily based on the `Google Developer Style Guide`_.

- Document the Python API with numpydoc-formatted docstrings.
  See the `LSST DM Docstring Style Guide`_.

- Follow the `LSST DM ReStructuredTextStyle Guide`_.
  In particular, ensure that prose is written **one-sentence-per-line** for better Git diffs.

.. _`LSST DM User Documentation Style Guide`: https://developer.lsst.io/user-docs/index.html
.. _`Google Developer Style Guide`: https://developers.google.com/style/
.. _`LSST DM Docstring Style Guide`: https://developer.lsst.io/python/style.html
.. _`LSST DM ReStructuredTextStyle Guide`: https://developer.lsst.io/restructuredtext/style.html
