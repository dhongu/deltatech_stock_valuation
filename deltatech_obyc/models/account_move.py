# © 2026 Deltatech
# See README.rst file on addons root folder for license details

from odoo import models


class AccountMove(models.Model):
    _inherit = "account.move"

    def _stock_account_prepare_realtime_out_lines_vals(self):
        """Fără linii COGS pe factura de vânzare pentru produsele OBYC.

        La OBYC costul mărfii vândute se înregistrează la livrare, pe nota mișcării
        de stoc (cheia `stock_delivery`: Dr cheltuială / Cr stoc). Liniile COGS
        generate de core la postarea facturii ar dubla costul; cu cheia `skip`,
        `_get_product_accounts` întoarce conturi goale pentru produsele OBYC și
        core-ul le sare. Produsele fără clasă de evaluare nu sunt afectate."""
        moves = self.with_context(transaction_key="skip")
        return super(AccountMove, moves)._stock_account_prepare_realtime_out_lines_vals()

    # ------------------------------------------------------------------
    # OBYC-014: diferența de preț și de curs dintre factură și recepție
    # ------------------------------------------------------------------
    def _post(self, soft=True):
        """Corectează stocul cu diferența dintre factura furnizorului și recepție.

        Recepția a înregistrat stocul (Dr 371/30x) în contrapartidă cu 408 la prețul
        comenzii. Linia facturii stinge 408 la prețul facturii, deci fără corecție
        rămâne un sold pe 408, iar stocul din contabilitate diferă de fișa de magazie
        (core-ul reface valoarea mișcării din factură, dar nota recepției nu se schimbă).
        Liniile de corecție (display_type `cogs`, dispar la `button_draft`) mută:
        - diferența de preț pe stoc (Dr 371 / Cr 408; storno la diferență negativă) și,
          pentru cantitatea ieșită deja din stoc, pe cheltuială (Dr 607 / Cr 371);
        - diferența de curs pe contul de diferențe de curs al companiei (665/765): stocul
          este element nemonetar și rămâne la cursul de la recepție.
        """
        if self.env.context.get("move_reverse_cancel"):
            return super()._post(soft=soft)
        corrections = self._obyc_prepare_price_difference()
        res = super()._post(soft=soft)
        self._obyc_align_received_moves(corrections)
        return res

    def _obyc_prepare_price_difference(self):
        """Creează liniile de corecție; întoarce, per mișcare de recepție, valoarea de adăugat."""
        corrections = []
        lines_vals_list = []
        for move in self.filtered(lambda m: m.move_type == "in_invoice"):
            move = move.with_company(move.company_id)
            for line in move.invoice_line_ids.filtered(lambda aml: aml.display_type == "product"):
                data = line._obyc_get_price_difference_data()
                if not data:
                    continue
                lines_vals_list += line._obyc_price_difference_lines_vals(data)
                corrections.append((data["receipts"], data["price_diff"], {r.id: r.value for r in data["receipts"]}))
        if lines_vals_list:
            self.env["account.move.line"].create(lines_vals_list)
        return corrections

    def _obyc_align_received_moves(self, corrections):
        """Valoarea mișcărilor de recepție urmează contabilitatea (fără diferența de curs).

        După postare core-ul a pus valoarea din factură (la cursul facturii); o aducem la
        valoarea din nota recepției plus diferența de preț (costul mediu al produsului urmează
        prețul facturii; partea ieșită a diferenței merge pe cheltuială prin linia de corecție) și refacem costul."""
        products = self.env["product.product"]
        for receipts, price_diff, booked_values in corrections:
            total_qty = sum(receipts.mapped(lambda m: m._get_valued_qty()))
            if not total_qty:
                continue
            for receipt in receipts:
                share = receipt._get_valued_qty() / total_qty
                receipt.value = receipt.company_currency_id.round(booked_values[receipt.id] + price_diff * share)
            products |= receipts.product_id
        if products:
            products._update_standard_price()
