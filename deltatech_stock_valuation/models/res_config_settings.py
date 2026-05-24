# ©  2024 Deltatech
#              Dorin Hongu <dhongu(@)gmail(.)com
# See README.rst file on addons root folder for license details


from odoo import api, fields, models
from odoo.exceptions import UserError

from .product_valuation import _PARAM_STEP, _PARAM_STEP5_LAST_PID

STEP_LABELS = {
    1: "Step 1/7: Delete history",
    2: "Step 2/7: Compute monthly movements",
    3: "Step 3/7: Fill missing months",
    4: "Step 4/7: Compute final balance for current month",
    5: "Step 5/7: Propagate balances to previous months",
    6: "Step 6/7: Delete empty rows",
    7: "Step 7/7: Recompute current product valuation",
}


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    module_deltatech_stock_valuation = fields.Boolean("Stock Valuation", readonly=True)
    valuation_area_level = fields.Selection(related="company_id.valuation_area_level", readonly=False)

    refresh_valuation_step_info = fields.Char(
        string="Next Refresh Step",
        compute="_compute_refresh_valuation_step_info",
    )

    @api.depends("valuation_area_level")
    def _compute_refresh_valuation_step_info(self):
        ICP = self.env["ir.config_parameter"].sudo()
        step = int(ICP.get_param(_PARAM_STEP, "1"))
        label = STEP_LABELS.get(step, STEP_LABELS[1])
        if step == 5:
            last_pid = int(ICP.get_param(_PARAM_STEP5_LAST_PID, "0"))
            if last_pid:
                label = f"{label} (from product {last_pid})"
        for rec in self:
            rec.refresh_valuation_step_info = label

    def set_values(self):
        res = super().set_values()
        self.company_id.set_stock_valuation_at_company_level()
        return res

    def _check_refresh_access(self):
        if not self.env.user.has_group("base.group_system"):
            raise UserError(self.env._("Only System Administrator can do this action!"))

    def refresh_stock_valuation(self):
        if self.valuation_area_level != "company":
            return
        self._check_refresh_access()

        ICP = self.env["ir.config_parameter"].sudo()
        step = int(ICP.get_param(_PARAM_STEP, "1"))

        if step in (1, 2, 3, 4, 6):
            self.env["product.valuation.history"]._recompute_all_amount(execute_step=[step])
            next_step = step + 1
            ICP.set_param(_PARAM_STEP, str(next_step))
        elif step == 5:
            last_pid = int(ICP.get_param(_PARAM_STEP5_LAST_PID, "0"))
            next_pid = self.env["product.valuation.history"]._recompute_step5_batch(product_id_start=last_pid)
            if next_pid is not None:
                ICP.set_param(_PARAM_STEP5_LAST_PID, str(next_pid))
                next_step = 5  # stay at step 5 until all products done
            else:
                ICP.set_param(_PARAM_STEP5_LAST_PID, "0")
                next_step = 6
                ICP.set_param(_PARAM_STEP, str(next_step))
        elif step == 7:
            self.env["product.valuation"]._recompute_all_amount()
            next_step = 1
            ICP.set_param(_PARAM_STEP, str(next_step))
        else:
            next_step = 1
            ICP.set_param(_PARAM_STEP, str(next_step))

        label_done = STEP_LABELS.get(step, "")
        label_next = STEP_LABELS.get(next_step, STEP_LABELS[1])

        if step == 5 and next_step == 5:
            last_pid = int(ICP.get_param(_PARAM_STEP5_LAST_PID, "0"))
            msg = self.env._(
                "%(done)s — processed up to product %(pid)s. Press again to continue.", done=label_done, pid=last_pid
            )
            msg_type = "info"
        elif next_step == 1:
            msg = self.env._("%(done)s completed. Refresh cycle finished. Ready to restart.", done=label_done)
            msg_type = "success"
        else:
            msg = self.env._("%(done)s completed. Next: %(next)s", done=label_done, next=label_next)
            msg_type = "info"

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": self.env._("Stock Valuation Refresh"),
                "message": msg,
                "type": msg_type,
                "sticky": False,
            },
        }

    def reset_refresh_valuation_step(self):
        self._check_refresh_access()
        ICP = self.env["ir.config_parameter"].sudo()
        ICP.set_param(_PARAM_STEP, "1")
        ICP.set_param(_PARAM_STEP5_LAST_PID, "0")
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": self.env._("Reset"),
                "message": self.env._("Refresh step reset to Step 1."),
                "type": "warning",
                "sticky": False,
            },
        }

    def recompute_product_valuation(self):
        if self.valuation_area_level != "company":
            return
        if not self.env.user.has_group("base.group_system"):
            raise UserError(self.env._("Only System Administrator can do this action!"))
        self.env["product.valuation"]._recompute_all_amount()

    def start_auto_refresh(self):
        self._check_refresh_access()
        cron = self.env.ref(
            "deltatech_stock_valuation.ir_cron_auto_refresh_valuation",
            raise_if_not_found=False,
        )
        if cron:
            cron.sudo().active = True
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": self.env._("Auto Refresh"),
                "message": self.env._("Auto refresh started. It will run every 2 minutes until complete."),
                "type": "success",
                "sticky": False,
            },
        }

    def stop_auto_refresh(self):
        self._check_refresh_access()
        cron = self.env.ref(
            "deltatech_stock_valuation.ir_cron_auto_refresh_valuation",
            raise_if_not_found=False,
        )
        if cron:
            cron.sudo().active = False
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": self.env._("Auto Refresh"),
                "message": self.env._("Auto refresh stopped."),
                "type": "warning",
                "sticky": False,
            },
        }
