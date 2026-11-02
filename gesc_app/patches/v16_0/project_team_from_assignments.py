"""Projects' current assignees, active employees only, make up their new team tables."""

from gesc_app.gesc_app.project_team import add_assigned_employees


def execute():
	add_assigned_employees()
