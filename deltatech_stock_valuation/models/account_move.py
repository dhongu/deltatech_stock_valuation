# ©  2023 Deltatech
#              Dorin Hongu <dhongu(@)gmail(.)com
# See README.rst file on addons root folder for license details


from odoo import api, models


class AccountMove(models.Model):
    _inherit = "account.move"

    def _get_valuation_keys(self):
        """
        Returnează combinațiile (product_id, valuation_area_id, account_id, company_id, date)
        afectate de liniile de stoc ale notelor din recordset.

        :return: set de tuple (product_id, valuation_area_id, account_id, company_id, date)
        """
        keys = set()
        for move in self:
            for line in move.line_ids:
                if not (line.product_id and line.account_id.is_for_stock_valuation):
                    continue
                valuation_area = line.valuation_area_id
                if not valuation_area:
                    valuation_area = line._get_valuation_area(raise_if_not_found=False)
                if not valuation_area:
                    continue
                keys.add((line.product_id.id, valuation_area.id, line.account_id.id, line.company_id.id, move.date))
        return keys

    @api.model
    def _recompute_valuation_keys(self, keys):
        """
        Recalculează istoricul lunar și evaluarea curentă pentru combinațiile date.
        Combinațiile sunt deduplicate și procesate grupat (un singur UPDATE SQL
        pentru istoric, respectiv pentru evaluarea curentă).

        :param keys: iterabil de tuple (product_id, valuation_area_id, account_id, company_id, date)
        :return: None
        """
        # recalculul folosește SQL direct pe note: orice modificare ORM nescrisă
        # (stare, dată, arii pe linii) trebuie flushată înainte
        self.env.flush_all()
        histories = self.env["product.valuation.history"]
        valuations = self.env["product.valuation"]
        for product_id, valuation_area_id, account_id, company_id, date in keys:
            histories |= histories.get_valuation(product_id, valuation_area_id, account_id, date, company_id)
            valuations |= valuations.get_valuation(product_id, valuation_area_id, account_id, company_id)
        if histories:
            histories._recompute_amount()
        if valuations:
            valuations._recompute_amount()

    def _recompute_valuation(self, extra_keys=None):
        """
        Recompute stock valuation and history for the move lines.

        :param extra_keys: combinații suplimentare de recalculat (ex. capturate înainte
                           de de-postare sau de schimbarea datei)
        """
        for move in self:
            for line in move.line_ids:
                if line.product_id and line.account_id.is_for_stock_valuation:
                    line.valuation_area_id = line._get_valuation_area(raise_if_not_found=False)

        self.flush_model()
        self._invalidate_cache()

        keys = set(extra_keys or ()) | self._get_valuation_keys()
        self._recompute_valuation_keys(keys)

    def write(self, vals):
        """
        Trigger valuation recomputation when the move is posted, un-posted (back to
        draft / cancelled) or when the accounting date of a posted move changes.
        """
        keys_before = set()
        if "state" in vals or "date" in vals:
            keys_before = self.filtered(lambda m: m.state == "posted")._get_valuation_keys()
        res = super().write(vals)
        if vals.get("state") == "posted":
            self._recompute_valuation(extra_keys=keys_before)
        elif keys_before:
            # de-postare sau schimbare de dată: se recalculează combinațiile vechi
            # plus cele noi (dacă nota a rămas postată cu altă dată)
            keys_after = self.filtered(lambda m: m.state == "posted")._get_valuation_keys()
            self._recompute_valuation_keys(keys_before | keys_after)
        return res

    def unlink(self):
        """
        Trigger valuation recomputation when posted moves are deleted.
        """
        keys = self.filtered(lambda m: m.state == "posted")._get_valuation_keys()
        res = super().unlink()
        if keys:
            self._recompute_valuation_keys(keys)
        return res
