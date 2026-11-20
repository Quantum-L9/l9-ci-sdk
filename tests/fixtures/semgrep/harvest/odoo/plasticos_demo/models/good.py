"""Known-good counterparts of plasticos_demo/models/bad.py.

Scan input only. Never imported or executed.
"""

from odoo import fields, models


# good: plasticos-namespace-drift
class PlasticosDemo(models.Model):
    _name = "plasticos.demo"
    _description = "Demo"

    # good: plasticos-x-prefixed-field
    trucker_id = fields.Many2one("res.partner")
    # good: plasticos-custom-partner-boolean
    tracked_flag = fields.Boolean()

    def action_demo(self):
        # good: plasticos-production-todo-implement
        return self.trucker_id
