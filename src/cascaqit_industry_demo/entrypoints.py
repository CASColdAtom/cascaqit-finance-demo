"""Public launch commands for the cross-domain industry workbench."""


def run() -> None:
    """Start the unified API and packaged frontend."""

    from cascaqit_finance_demo.api.app import run as run_application

    run_application()


def launch() -> None:
    """Start the unified application and open it in the default browser."""

    from cascaqit_finance_demo.api.app import launch as launch_application

    launch_application()
