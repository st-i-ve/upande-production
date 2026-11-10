"""Create the Avocado Production Manager role and its document rights. Idempotent."""

from upande_production.production.logic.avocado_role import setup


def execute():
	setup()
