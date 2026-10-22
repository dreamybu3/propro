# Cloud development environment

The current Linux instance has the installed virtual environment and all executed artifacts. The cloud configuration draft now saves complete `install_script` and `start_skill` fields: frozen dependency installation, tests, the isolated-checkout rule, CLI startup/readiness checks, reproduction commands and honest limitations. Existing repository/network/credential settings were preserved.

Saving the draft did not execute it, publish a snapshot, push source code, or activate settings for another task. The installation and startup commands were separately exercised in the current instance. If the owner later wants to activate this saved environment, review and save the draft in environment settings and then publish the environment through the product. The environment snapshot remains unpublished. The owner subsequently authorized source-code delivery to the separate GitHub branch `gaplens-delivery`; that authorization does not publish or activate the cloud environment snapshot.

The project itself remains portable: use README.md or QUICKSTART_RU.md in any extracted checkout. No cloud credential or paid service is required.
