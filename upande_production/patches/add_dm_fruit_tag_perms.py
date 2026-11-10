"""Give the Avocado Production Manager role its rights on the new Dry Matter Fruit Tag. Idempotent."""

from upande_production.production.logic.avocado_role import setup


def execute():
	setup()
