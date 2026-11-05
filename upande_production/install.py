"""Install hooks.

`frappe.installer.install_app` runs before_install, THEN sync_for (the JSON doctype import), and only
then marks every patches.txt entry as already done without running it (set_all_patches_as_completed).
So on a site that already carries these doctypes under another app (live Margin Par: upande_agriculture
and upande_summer_flowers, some as custom doctypes), the pre_model_sync take-over patches never run on a
fresh `install-app` and the JSON import would collide with the existing doctypes. before_install runs
the same patches first. All of them are idempotent and do nothing on a site that has none of the
old doctypes (Mutara, a clean site). Returning None, never False: False would abort the install.
"""

import frappe

# patches.txt [pre_model_sync] order
PRE_MODEL_SYNC_PATCHES = (
	"upande_production.patches.rename_production_operation_to_field_activity",
	"upande_production.patches.rename_field_activity_to_field_operation",
	"upande_production.patches.rename_forecast_and_plan_task_doctypes",
	"upande_production.patches.take_over_from_upande_agriculture",
	"upande_production.patches.take_over_from_upande_summer_flowers",
)

# Setup (not history) from patches.txt [post_model_sync]; set_all_patches_as_completed skips them on
# install, and nothing else creates what they create. The data backfills there (number_cycles,
# drop_cycles_for_bees_and_fish, backfill_*, convert_protocol_steps, ...) only repair rows written by
# older Mutara versions of this app, so they are correctly skipped on a site installing it fresh.
SETUP_PATCHES = (
	"upande_production.patches.ensure_crop_production_defaults",
	"upande_production.patches.ensure_production_desktop_icon",
	"upande_production.patches.seed_default_bands",
)


def _run(paths):
	for path in paths:
		frappe.get_attr(path + ".execute")()


def before_install():
	_run(PRE_MODEL_SYNC_PATCHES)


def after_install():
	_run(SETUP_PATCHES)
