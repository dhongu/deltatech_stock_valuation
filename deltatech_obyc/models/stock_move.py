import logging

from odoo import Command, fields, models
from odoo.exceptions import UserError
from odoo.tools import float_is_zero

_logger = logging.getLogger(__name__)


class StockMove(models.Model):
    _inherit = "stock.move"

    # def _get_accounting_data_for_valuation(self):
    #     if not self.product_id.valuation_class_id:
    #         return super()._get_accounting_data_for_valuation()
    #
    #     valuation_area = self._get_valuation_area()
    #
    #     journal_id = valuation_area.stock_journal_id.id
    #     if not journal_id:
    #         raise UserError(_("Stock journal is not defined for the valuation area"))
    #
    #     picking_type = self.picking_type_id
    #     transaction_key = self._compute_transaction_key()
    #     account_modifier = self.env["account.modifier"]
    #     if picking_type:
    #         account_modifier = picking_type.account_modifier_id
    #
    #     _get_rule_account = self.env["product.account.determination"]._get_rule_account
    #
    #     rule = _get_rule_account(
    #         valuation_area=valuation_area,
    #         valuation_class=self.product_id.valuation_class_id,
    #         transaction_key=transaction_key,
    #         account_modifier=account_modifier,
    #         company=self.company_id,
    #     )
    #     acc_src = rule.acc_src_id.id
    #     acc_dest = rule.acc_dest_id.id
    #     acc_valuation = rule.acc_valuation_id.id
    #
    #     return journal_id, acc_src, acc_dest, acc_valuation

    # def _prepare_account_move_vals(
    #     self, credit_account_id, debit_account_id, journal_id, qty, description, svl_id, cost
    # ):
    #     self.ensure_one()
    #     if credit_account_id == debit_account_id:
    #         return False
    #     vals = super()._prepare_account_move_vals(
    #         credit_account_id, debit_account_id, journal_id, qty, description, svl_id, cost
    #     )
    #     if self.company_id.account_storno and self.origin_returned_move_id:
    #         vals["is_storno"] = True
    #     return vals

    # def _account_entry_move(self, qty, description, svl_id, cost):
    #     if not qty:
    #         self = self.with_context(price_difference=True)
    #     am_vals_list = super()._account_entry_move(qty, description, svl_id, cost)
    #     for am_vals in am_vals_list:
    #         if not am_vals:
    #             am_vals_list.remove(am_vals)
    #
    #     return am_vals_list

    def _set_value(self, correction_quantity=None):
        """Completează valoarea mișcărilor dropship pentru produsele OBYC.

        Core (`stock_account._set_value`) include mișcările dropship în
        filtrul `is_in or is_dropship`, dar atribuie `move.value` doar când
        `is_in` e adevărat. Fără acest fix, `_get_account_move_line_vals()`
        de mai jos ar folosi `self.value == 0`, iar nota contabilă OBYC
        generată imediat după (tot în `_action_done()`) ar fi postată cu
        debit=0/credit=0 — o notă aparent înregistrată, dar fără valoare.
        """
        res = super()._set_value(correction_quantity=correction_quantity)
        obyc_dropship_moves = self.filtered(
            lambda m: m.product_id._get_valuation_class() and m.is_dropship and not m.value
        )
        for move in obyc_dropship_moves:
            move.value = move.sudo()._get_value()
        return res

    def _is_obyc_transit_transfer(self):
        """Mișcare dintr-o locație internă în tranzit sau din tranzit într-o locație internă,
        pentru un produs cu clasă de evaluare."""
        self.ensure_one()
        if not self.product_id._get_valuation_class():
            return False
        return self._compute_transaction_key(raise_if_not_found=False) in (
            "internal_transfer_out",
            "internal_transfer_in",
        )

    def _get_obyc_transit_value(self):
        """Valoarea unui transfer prin tranzit, indiferent de metoda de evaluare.

        La sosire: valoarea mișcărilor de plecare (ce a ieșit dintr-o arie intră întreagă în
        cealaltă); la plecare, sau fără mișcări de plecare: costul unităților mutate
        (`_get_obyc_transit_cost_value`)."""
        self.ensure_one()
        if self._compute_transaction_key(raise_if_not_found=False) == "internal_transfer_in":
            value = self._get_obyc_transit_value_from_origins()
            if value is not None:
                return value
        return self._get_obyc_transit_cost_value()

    def _get_obyc_transit_value_from_origins(self):
        """Valoarea mărfii care sosește din tranzit; None dacă nu poate fi stabilită.

        Întâi mișcările de plecare înlănțuite cu aceasta (`move_orig_ids`), proporțional cu
        cantitatea primită. Dacă transferurile nu sunt înlănțuite (două transferuri introduse
        separat), costul mediu al mărfii rămase în locația de tranzit: valoarea intrată minus
        valoarea ieșită, împărțită la cantitatea rămasă."""
        self.ensure_one()
        quantity = sum(self.move_line_ids.mapped("quantity_product_uom"))
        origins = self.move_orig_ids.filtered(lambda m: m.state == "done" and m.value and m.quantity)
        origin_quantity = sum(origins.move_line_ids.mapped("quantity_product_uom"))
        if origins and origin_quantity:
            return sum(origins.mapped("value")) / origin_quantity * quantity
        transit = self.location_id
        domain = [
            ("product_id", "=", self.product_id.id),
            ("company_id", "=", self.company_id.id),
            ("state", "=", "done"),
            ("id", "!=", self.id),
        ]
        incoming = self.search(domain + [("location_dest_id", "=", transit.id)])
        outgoing = self.search(domain + [("location_id", "=", transit.id)])
        transit_quantity = sum(incoming.move_line_ids.mapped("quantity_product_uom")) - sum(
            outgoing.move_line_ids.mapped("quantity_product_uom")
        )
        transit_value = sum(incoming.mapped("value")) - sum(outgoing.mapped("value"))
        if transit_quantity > 0 and transit_value:
            return transit_value / transit_quantity * quantity
        return None

    def _get_obyc_transit_quantities(self):
        """Cantitățile mutate, în UoM-ul produsului: (lot, cantitate) pe lot la produsele cu
        evaluare pe lot, altfel o singură pereche (fără lot, cantitate totală)."""
        self.ensure_one()
        lines = self.move_line_ids
        if not self.product_id.lot_valuated:
            return [(self.env["stock.lot"], sum(lines.mapped("quantity_product_uom")))]
        quantities = {}
        for line in lines:
            quantities[line.lot_id] = quantities.get(line.lot_id, 0.0) + line.quantity_product_uom
        return list(quantities.items())

    def _get_obyc_transit_area_price(self):
        """Prețul pe aria de evaluare a mișcării (`deltatech_stock_valuation`), când produsul
        îl folosește (categorie cu preț pe arie, cost mediu, fără evaluare pe lot); altfel None.
        Punct de extensie pentru alte surse de preț."""
        self.ensure_one()
        category = self.product_id.categ_id
        if "use_valuation_area_price" not in category._fields or not category.use_valuation_area_price:
            return None
        if self.product_id.lot_valuated or self.product_id.cost_method == "fifo":
            return None
        if self.location_id.usage != "internal":
            return None
        return self._get_valuation_area_price()

    def _get_obyc_transit_cost_value(self):
        """Costul unităților mutate, după metoda de evaluare a produsului:

        - FIFO: costul următoarelor straturi de intrare (`_run_fifo`), pe lot la evaluarea pe lot;
        - cost mediu cu evaluare pe lot: costul fiecărui lot;
        - cost mediu cu preț pe aria de evaluare: prețul ariei din care pleacă marfa;
        - altfel costul curent al produsului (cost standard sau mediu ponderat)."""
        self.ensure_one()
        product = self.product_id.with_company(self.company_id)
        quantities = self._get_obyc_transit_quantities()
        if product.cost_method == "fifo":
            return sum(
                product._run_fifo(quantity, lot=lot.with_company(self.company_id) or None)
                for lot, quantity in quantities
            )
        if product.lot_valuated:
            return sum(
                (lot.with_company(self.company_id).standard_price if lot else product.standard_price) * quantity
                for lot, quantity in quantities
            )
        quantity = sum(qty for _lot, qty in quantities)
        area_price = self._get_obyc_transit_area_price()
        if area_price is not None:
            return area_price * quantity
        return product.standard_price * quantity

    def _compute_transaction_key(self, raise_if_not_found=True):
        source_usage = self.location_id.usage
        dest_usage = self.location_dest_id.usage

        match source_usage, dest_usage:
            # Purchase transactions
            case "supplier", "internal":
                tr_key = "stock_receipt"  # Receipt from supplier
            case "supplier", "transit":
                tr_key = "stock_receipt"  # Receipt from supplier
            case "internal", "supplier":
                tr_key = "return_to_supplier"  # Return to supplier
            case "transit", "supplier":
                tr_key = "return_to_supplier"  # Return to supplier

            # Sale transactions
            case "internal", "customer":
                tr_key = "stock_delivery"  # Delivery to customer
            case "customer", "internal":
                tr_key = "return_from_customer"  # Return from customer
            case "supplier", "customer":
                tr_key = "dropship"  # Drop shipment from supplier to customer
            case "customer", "supplier":
                tr_key = "dropship_return"  # Return from customer to supplier (if applicable)

            # Internal transfers
            case "internal", "internal":
                tr_key = "internal_transfer"
            case "internal", "transit":
                tr_key = "internal_transfer_out"
            case "transit", "internal":
                tr_key = "internal_transfer_in"

            # Inventory adjustments
            case "inventory", "internal":
                tr_key = "inventory_adjustment_plus"  # Gain found at the count
            case "internal", "inventory":
                tr_key = "inventory_adjustment_minus"  # Loss found at the count

            # Production transactions
            case "internal", "production":
                tr_key = "production_issue"  # Issue to production
            case "production", "internal":
                tr_key = "production_receipt"  # Receipt from production
            case _:
                tr_key = False

        if not tr_key:
            if not raise_if_not_found:
                return False
            raise UserError(
                self.env._(
                    "Transaction key could not be determined for the move from %(source_usage)s to %(dest_usage)s.",
                    source_usage=source_usage,
                    dest_usage=dest_usage,
                )
            )
        if self.env.context.get("price_difference"):
            # If the context indicates a price difference, we use a specific transaction key
            tr_key = "price_difference"
        return tr_key

    def _get_rule_account(self):
        self.ensure_one()
        if not self.product_id._get_valuation_class():
            return self.env["product.account.determination"]
        transaction_key = self._compute_transaction_key()
        account_modifier = self.env["account.modifier"]
        valuation_area = self._get_valuation_area()
        if self.picking_type_id:
            account_modifier = self.picking_type_id.account_modifier_id

        _get_rule_account = self.env["product.account.determination"]._get_rule_account

        rule = _get_rule_account(
            valuation_area=valuation_area,
            valuation_class=self.product_id._get_valuation_class(),
            transaction_key=transaction_key,
            account_modifier=account_modifier,
            company=self.company_id,
        )

        return rule

    def _get_valuation_area_price_account(self):
        """Produsele OBYC nu au conturi pe categorie: evaluarea pe arie se ține pe contul de
        evaluare din regula OBYC a mișcării."""
        if not self.product_id._get_valuation_class():
            return super()._get_valuation_area_price_account()
        self.ensure_one()
        return self._get_rule_account().acc_valuation_id

    def _get_obyc_debit_credit_accounts(self, rule):
        """Conturile de debit și de credit ale notei, din regula OBYC."""
        if rule.acc_src_id:
            return rule.acc_valuation_id, rule.acc_src_id
        return rule.acc_dest_id, rule.acc_valuation_id

    def _is_obyc_reclassification(self):
        """Transfer intern a cărui regulă are conturi diferite pe cele două părți
        (ex. 3028 → 371): schimbă doar contul de stoc, nu și cantitatea. Transferul
        obișnuit are regula fără conturi sau cu același cont, deci rămâne fără notă."""
        self.ensure_one()
        if not self.product_id._get_valuation_class():
            return False
        if self._compute_transaction_key(raise_if_not_found=False) != "internal_transfer":
            return False
        debit_acc, credit_acc = self._get_obyc_debit_credit_accounts(self._get_rule_account())
        return bool(debit_acc and credit_acc and debit_acc != credit_acc)

    def _set_obyc_reclassification_value(self):
        """Nucleul evaluează doar intrările, ieșirile și dropship-ul; transferul intern
        de reclasificare se evaluează la costul curent al produsului."""
        for move in self:
            product = move.product_id.with_company(move.company_id)
            value = 0.0
            for move_line in move.move_line_ids:
                cost = product.standard_price
                if product.lot_valuated and move_line.lot_id:
                    cost = move_line.lot_id.with_company(move.company_id).standard_price
                value += cost * move_line.quantity_product_uom
            move.value = value

    def _should_create_account_move(self):
        if not self.product_id._get_valuation_class():
            return super()._should_create_account_move()
        self.ensure_one()

        # condițiile nucleului, fără contul de evaluare al locației (înlocuit de regula OBYC)
        # și fără `is_valued`: dropship-ul și transferurile dintre arii de evaluare nu sunt
        # intrări/ieșiri în nucleu, dar au chei OBYC proprii
        product = self.product_id.with_company(self.company_id)
        if not product.is_storable or product.valuation != "real_time":
            return False
        if float_is_zero(self.quantity, precision_rounding=self.product_uom.rounding):
            return False
        if self._is_obyc_owner_stock():
            return False
        if not (self.is_valued or self.is_dropship) and not self._compute_transaction_key(raise_if_not_found=False):
            # combinație de locații fără cheie, pe o mișcare pe care nici nucleul nu o evaluează
            return False

        rule = self._get_rule_account()
        if not (rule.acc_src_id or rule.acc_dest_id or rule.acc_valuation_id):
            return False
        debit_acc, credit_acc = self._get_obyc_debit_credit_accounts(rule)
        if self._compute_transaction_key(raise_if_not_found=False) == "internal_transfer":
            # transferul intern are notă doar dacă schimbă contul de stoc
            return bool(debit_acc and credit_acc and debit_acc != credit_acc)
        return not (debit_acc and debit_acc == credit_acc)

    def _is_obyc_owner_stock(self):
        """Marfă cu proprietar terț (custodie, consignație primită): nucleul nu o evaluează."""
        self.ensure_one()
        if self._should_exclude_for_valuation():
            return True
        move_lines = self.move_line_ids
        return bool(move_lines) and all(line._should_exclude_for_valuation() for line in move_lines)

    def _is_storno_return(self):
        """Retururile se înregistrează în roșu (storno) când compania are activată
        contabilitatea storno: aceleași conturi ca tranzacția originală, sume negative."""
        self.ensure_one()
        return bool(self.company_id.account_storno and self.origin_returned_move_id)

    def _get_account_move_line_vals(self):
        if not self.product_id._get_valuation_class():
            vals_list = super()._get_account_move_line_vals()
        else:
            rule = self._get_rule_account()

            debit_acc, credit_acc = self._get_obyc_debit_credit_accounts(rule)
            # cantitatea (SEMNATĂ: negativă pe credit, pozitivă pe debit) și UoM sunt
            # necesare evaluării (deltatech_stock_valuation); aria de evaluare se
            # completează prin compute-ul de pe account.move.line
            quantity = self._get_valued_qty()
            if not quantity and (self._is_obyc_reclassification() or self._is_obyc_transit_transfer()):
                quantity = sum(self.move_line_ids.mapped("quantity_product_uom"))
            vals_list = [
                {
                    "account_id": credit_acc.id,
                    "name": self.reference,
                    "debit": 0,
                    "credit": self.value,
                    "product_id": self.product_id.id,
                    "quantity": -quantity,
                    "product_uom_id": self.product_id.uom_id.id,
                },
                {
                    "account_id": debit_acc.id,
                    "name": self.reference,
                    "debit": self.value,
                    "credit": 0,
                    "product_id": self.product_id.id,
                    "quantity": quantity,
                    "product_uom_id": self.product_id.uom_id.id,
                },
            ]

        if self._is_storno_return():
            # transformare în storno (roșu): nota „neagră" de retur (Dr A / Cr B)
            # devine tranzacția originală cu sume negative (Dr B -V / Cr A -V);
            # mecanic: suma trece pe partea opusă, negată, iar cantitatea semnată
            # se inversează odată cu partea
            for vals in vals_list:
                debit = vals.get("debit", 0.0)
                credit = vals.get("credit", 0.0)
                vals["debit"], vals["credit"] = -credit, -debit
                if vals.get("quantity"):
                    vals["quantity"] = -vals["quantity"]
        return vals_list

    def _get_obyc_stock_journal(self):
        """Jurnalul de stoc al ariei de evaluare, pentru produsele cu clasă de
        evaluare OBYC; recordset gol dacă nu se aplică."""
        self.ensure_one()
        journal = self.env["account.journal"]
        if self.product_id._get_valuation_class():
            valuation_area = self._get_valuation_area(raise_if_not_found=False)
            if valuation_area and valuation_area.stock_journal_id:
                journal = valuation_area.stock_journal_id
        return journal

    def _create_account_move(self):
        """Grupează mișcările pe jurnalul ariei de evaluare: mișcările OBYC dintr-o
        arie cu jurnal propriu primesc nota pe acel jurnal; restul merg pe
        comportamentul standard (jurnalul de stoc al companiei)."""
        reclassification_moves = self.filtered(
            lambda m: m._should_create_account_move() and m._is_obyc_reclassification()
        )
        reclassification_moves._set_obyc_reclassification_value()
        # transferul prin locația de tranzit nu e nici intrare, nici ieșire în nucleu (`_set_value`
        # nu îl atinge), deci `value` rămâne gol, iar nota OBYC ar fi postată pe zero
        for move in self.filtered(
            lambda m: not m.value and m._should_create_account_move() and m._is_obyc_transit_transfer()
        ):
            move.value = move._get_obyc_transit_value()
        result = self.env["account.move"]
        default_moves = self.browse()
        by_journal = {}
        for move in self:
            journal = move._get_obyc_stock_journal()
            if journal:
                by_journal.setdefault(journal, self.browse())
                by_journal[journal] |= move
            else:
                default_moves |= move
        if default_moves:
            result |= super(StockMove, default_moves)._create_account_move()
        for journal, moves in by_journal.items():
            result |= moves._create_account_move_with_journal(journal)
        return result

    def _create_account_move_with_journal(self, journal):
        """Replica fluxului core `_create_account_move`, cu jurnalul forțat
        (core-ul folosește necondiționat jurnalul de stoc al companiei)."""
        aml_vals_list = []
        move_to_link = set()
        for move in self:
            if move._should_create_account_move():
                aml_vals_list += move._get_account_move_line_vals()
                move_to_link.add(move.id)
        if not aml_vals_list:
            return self.env["account.move"]

        move_refs = list(set(self.mapped("reference")))
        joined_refs = ", ".join(move_refs)
        if len(joined_refs) > 43:
            joined_refs = joined_refs[:40] + "..."

        account_move = (
            self.env["account.move"]
            .sudo()
            .create(
                {
                    "ref": joined_refs,
                    "partner_id": self._get_partner_id_for_valuation_lines(),
                    "journal_id": journal.id,
                    "line_ids": [Command.create(aml_vals) for aml_vals in aml_vals_list],
                    "date": self.env.context.get("force_period_date") or fields.Date.context_today(self),
                }
            )
        )
        self.env["stock.move"].browse(move_to_link).account_move_id = account_move.id
        account_move._post()
        return account_move
