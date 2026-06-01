# ©  2024 Deltatech
#              Dorin Hongu <dhongu(@)gmail(.)com
# See README.rst file on addons root folder for license details


from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .product_valuation import (
    _PARAM_LAST_DURATION,
    _PARAM_LAST_RUN,
    _PARAM_LAST_STEP,
    _PARAM_NOTIFY_UID,
    _PARAM_STEP,
    _PARAM_STEP5_LAST_PID,
    STEP_LABELS,
)

_CRON_XMLID = "deltatech_stock_valuation.ir_cron_auto_refresh_valuation"


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    module_deltatech_stock_valuation = fields.Boolean("Stock Valuation", readonly=True)
    valuation_area_level = fields.Selection(related="company_id.valuation_area_level", readonly=False)

    refresh_valuation_step_info = fields.Char(
        string="Next Refresh Step",
        compute="_compute_refresh_valuation_step_info",
    )
    is_refresh_running = fields.Boolean(
        string="Background Refresh Running",
        compute="_compute_refresh_valuation_step_info",
    )
    refresh_valuation_progress_info = fields.Char(
        string="Last Refresh Progress",
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

        cron = self.env.ref(_CRON_XMLID, raise_if_not_found=False)
        running = bool(cron and cron.sudo().active)

        last_step = ICP.get_param(_PARAM_LAST_STEP)
        last_run = ICP.get_param(_PARAM_LAST_RUN)
        last_duration = ICP.get_param(_PARAM_LAST_DURATION)
        if last_step and last_run:
            progress = _(
                "Last: %(label)s at %(when)s (%(s)ss)",
                label=STEP_LABELS.get(int(last_step), ""),
                when=last_run,
                s=last_duration or "?",
            )
        else:
            progress = _("No background refresh has run yet.")

        for rec in self:
            rec.refresh_valuation_step_info = label
            rec.is_refresh_running = running
            rec.refresh_valuation_progress_info = progress

    def set_values(self):
        res = super().set_values()
        self.company_id.set_stock_valuation_at_company_level()
        return res

    def _check_refresh_access(self):
        if not self.env.user.has_group("base.group_system"):
            raise UserError(_("Only System Administrator can do this action!"))

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
            msg = _(
                "%(done)s — processed up to product %(pid)s. Press again to continue.", done=label_done, pid=last_pid
            )
            msg_type = "info"
        elif next_step == 1:
            msg = _("%(done)s completed. Refresh cycle finished. Ready to restart.", done=label_done)
            msg_type = "success"
        else:
            msg = _("%(done)s completed. Next: %(next)s", done=label_done, next=label_next)
            msg_type = "info"

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Stock Valuation Refresh"),
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
                "title": _("Reset"),
                "message": _("Refresh step reset to Step 1."),
                "type": "warning",
                "sticky": False,
            },
        }

    def recompute_product_valuation(self):
        if self.valuation_area_level != "company":
            return
        if not self.env.user.has_group("base.group_system"):
            raise UserError(_("Only System Administrator can do this action!"))
        self.env["product.valuation"]._recompute_all_amount()

    def action_recompute_in_background(self):
        """Single-click background recompute: restart the cycle at step 1 and let the
        cron run all 7 steps automatically. The cron keeps track of the current step
        and notifies the initiating user after each step."""
        if self.valuation_area_level != "company":
            return
        self._check_refresh_access()

        cron = self.env.ref(_CRON_XMLID, raise_if_not_found=False)
        # Guard against a double start: if a run is already in progress, do nothing
        # so the user cannot restart the cycle mid-way by clicking again.
        if cron and cron.sudo().active:
            return self._notification(
                _("Background Recompute"),
                _("A background recompute is already running."),
                "warning",
            )

        ICP = self.env["ir.config_parameter"].sudo()
        # Restart a clean cycle and remember who should be notified.
        ICP.set_param(_PARAM_STEP, "1")
        ICP.set_param(_PARAM_STEP5_LAST_PID, "0")
        ICP.set_param(_PARAM_NOTIFY_UID, str(self.env.uid))

        if cron:
            # Activate and trigger promptly instead of waiting for the next schedule.
            cron.sudo().write({"active": True, "nextcall": fields.Datetime.now()})
            cron.sudo()._trigger()
        # Reload the settings so the button immediately flips to "Stop" (the run is now
        # active) and the user cannot press the start button again.
        return {"type": "ir.actions.client", "tag": "reload"}

    def start_auto_refresh(self):
        self._check_refresh_access()
        ICP = self.env["ir.config_parameter"].sudo()
        ICP.set_param(_PARAM_NOTIFY_UID, str(self.env.uid))
        cron = self.env.ref(_CRON_XMLID, raise_if_not_found=False)
        if cron:
            cron.sudo().active = True
            cron.sudo()._trigger()
        return self._notification(
            _("Auto Refresh"),
            _("Auto refresh started. It will run every 2 minutes until complete."),
            "success",
        )

    def stop_auto_refresh(self):
        self._check_refresh_access()
        cron = self.env.ref(_CRON_XMLID, raise_if_not_found=False)
        if cron:
            cron.sudo().active = False
        # Reload so the "Stop" button flips back to "Recompute All (Background)".
        return {"type": "ir.actions.client", "tag": "reload"}

    def _notification(self, title, message, msg_type):
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": title,
                "message": message,
                "type": msg_type,
                "sticky": False,
            },
        }
