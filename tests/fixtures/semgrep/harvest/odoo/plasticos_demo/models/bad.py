"""Known-bad cases for the path-scoped PlasticOS Python rules.

The same file is stored under other_addon/. These rules are scoped to
``plasticos_*`` paths, so they must flag this copy and stay silent on that one.

Scan input only. Never imported or executed.
"""

from odoo import fields, models


# bad: plasticos-namespace-drift
class PlastosDemo(models.Model):
    _name = "plasticos.demo"
    _description = "Demo"

    # bad: plasticos-x-prefixed-field
    x_trucker_id = fields.Many2one("res.partner")
    # bad: plasticos-custom-partner-boolean
    is_customer = fields.Boolean()

    def action_demo(self):
        # bad: plasticos-production-todo-implement
        return None  # TODO implement the demo action
