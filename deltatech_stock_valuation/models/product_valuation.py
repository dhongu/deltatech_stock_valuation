# ©  2023 Deltatech
#              Dorin Hongu <dhongu(@)gmail(.)com
# See README.rst file on addons root folder for license details


import logging
import time
from datetime import datetime

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.tools import SQL, float_is_zero

_logger = logging.getLogger(__name__)

_PARAM_STEP = "deltatech_stock_valuation.refresh_step"
_PARAM_STEP5_LAST_PID = "deltatech_stock_valuation.step5_last_product_id"
_PARAM_NOTIFY_UID = "deltatech_stock_valuation.refresh_notify_uid"
_PARAM_LAST_RUN = "deltatech_stock_valuation.refresh_last_run"
_PARAM_LAST_DURATION = "deltatech_stock_valuation.refresh_last_duration"
_PARAM_LAST_STEP = "deltatech_stock_valuation.refresh_last_step"
_STEP5_CLICK_BATCH = 2000  # products per button click / cron run
_STEP5_SQL_BATCH = 500  # products per SQL window function query
# Safety bound: a single accounting move with a wrong date (e.g. year 1561) must not
# make the monthly calendar span centuries and explode the history table.
_MAX_HISTORY_YEARS = 20

# Labels shown in the configuration while the background refresh advances.
STEP_LABELS = {
    1: "Step 1/7: Delete history",
    2: "Step 2/7: Compute monthly movements",
    3: "Step 3/7: Fill missing months",
    4: "Step 4/7: Compute final balance for current month",
    5: "Step 5/7: Propagate balances to previous months",
    6: "Step 6/7: Delete empty rows",
    7: "Step 7/7: Recompute current product valuation",
}


# ca in SAP Material Valuation - MBEW & MBEWH
class ProductValuation(models.Model):
    _name = "product.valuation"
    _description = "Product Valuation"
    _rec_name = "product_id"

    product_id = fields.Many2one("product.product", string="Product", required=True, index=True)
    product_tmpl_id = fields.Many2one(
        "product.template", string="Product Template", index=True, related="product_id.product_tmpl_id"
    )
    valuation_area_id = fields.Many2one("valuation.area", string="Valuation Area", index=True)

    price = fields.Float(string="Price", digits="Product Price")

    quantity = fields.Float(string="Quantity", digits="Product Unit of Measure", default=0.0)

    amount = fields.Monetary(string="Amount", default=0.0)
    account_id = fields.Many2one("account.account", string="Account", required=True, index=True)

    currency_id = fields.Many2one("res.currency", string="Currency", default=lambda self: self.env.company.currency_id)
    company_id = fields.Many2one(
        "res.company", string="Company", required=True, index=True, default=lambda self: self.env.company
    )

    # în Odoo 19 lista _sql_constraints e ignorată silențios — se folosește models.Constraint;
    # atributul e suprascris în product.valuation.history (moștenire prototype) cu varianta pe lună
    _combination_uniq = models.Constraint(
        "UNIQUE (product_id, valuation_area_id, account_id, company_id)",
        "Product valuation must be unique",
    )

    def get_valuation(self, product_id, valuation_area_id, account_id, company_id=False):
        """
        Returnează înregistrarea curentă de evaluare (product.valuation) pentru combinația
        (product_id, valuation_area_id, account_id, company_id).

        Dacă nu există, creează o înregistrare nouă cu valorile implicite (quantity=0, amount=0).

        :param product_id: ID-ul produsului
        :param valuation_area_id: ID-ul zonei de evaluare
        :param account_id: ID-ul contului contabil de stoc
        :param company_id: ID-ul companiei (implicit: compania curentă)
        :return: recordset product.valuation
        """
        if not company_id:
            company_id = self.env.company.id
        domain = [
            ("product_id", "=", product_id),
            ("valuation_area_id", "=", valuation_area_id),
            ("account_id", "=", account_id),
            ("company_id", "=", company_id),
        ]
        valuation = self.with_context(active_test=False).search(domain, limit=1)
        if not valuation:
            valuation = self.create(
                {
                    "product_id": product_id,
                    "valuation_area_id": valuation_area_id,
                    "account_id": account_id,
                    "company_id": company_id,
                }
            )
        return valuation

    @api.model
    def _get_qty_epsilon(self):
        """
        Pragul sub care o cantitate e considerată reziduală (zero) la calculul prețului,
        derivat din precizia zecimală globală „Product Unit of Measure".
        În Odoo 19 `uom.uom.rounding` e câmp calculat (nestocat), deci nu poate fi
        folosit direct în SQL.

        :return: float, jumătate din pasul de rotunjire al cantităților
        """
        digits = self.env["decimal.precision"].precision_get("Product Unit of Measure")
        return (10**-digits) / 2

    @api.model
    def _get_quantity_in_out_sql(self):
        """
        Returnează expresiile SQL (multiplicatori CASE) pentru clasificarea cantităților
        în intrări/ieșiri, folosite de toate agregările (product.valuation,
        product.valuation.history și soldul din pasul 4 al recalculării complete).

        Convenția canonică pe note de tip `entry` (validată pe baze de client 16/18):
        cantitatea de pe linie e SEMNATĂ — pozitivă la intrare (linia de debit),
        negativă la ieșire (linia de credit). Multiplicatorii de mai jos convertesc
        cantitatea semnată în intrări/ieșiri pozitive:
        - intrare: debit > 0 → +1 (qty pozitiv = intrare); storno (debit < 0) → -1;
          liniile valoric-zero cu cantitate (mișcări la cost 0) sunt intrări semnate
        - ieșire: credit > 0 → -1 (qty negativ devine ieșire pozitivă);
          storno pe credit (credit < 0) → +1
        - facturile (in_/out_invoice/refund/receipt) au cantitate pozitivă,
          multiplicatorii rămân pe move_type
        - cantitatea netă = intrări - ieșiri (== cantitatea semnată, pe note entry)

        :return: tuple (in_case, out_case) de obiecte SQL cu multiplicatorii per linie
        """
        in_case = SQL(
            """(CASE
                    WHEN move_type IN ('in_invoice','in_receipt') THEN 1
                    WHEN move_type = 'in_refund' THEN -1
                    WHEN move_type IN ('out_invoice','out_refund','out_receipt') THEN 0
                    ELSE CASE WHEN debit > 0 THEN 1
                              WHEN debit < 0 THEN -1
                              WHEN credit = 0 THEN 1
                              ELSE 0 END
                END)"""
        )
        out_case = SQL(
            """(CASE
                    WHEN move_type IN ('out_invoice','out_receipt') THEN 1
                    WHEN move_type = 'out_refund' THEN -1
                    WHEN move_type IN ('in_invoice','in_refund','in_receipt') THEN 0
                    ELSE CASE WHEN credit > 0 THEN -1
                              WHEN credit < 0 THEN 1
                              ELSE 0 END
                END)"""
        )
        return in_case, out_case

    def _recompute_amount(self):
        """
        Recalculează valorile curente (quantity, amount, price) din `product.valuation`
        pentru fiecare înregistrare din recordset, preluând datele din ultima lună disponibilă
        din `product.valuation.history`.

        Logica de calcul a prețului:
        - dacă `quantity_final != 0`: price = amount_final / quantity_final
        - altfel dacă `quantity_in != 0`: price = debit / quantity_in
        - altfel: se păstrează prețul existent

        :return: None
        """
        for item in self:
            domain = [
                ("product_id", "=", item.product_id.id),
                ("valuation_area_id", "=", item.valuation_area_id.id),
                ("account_id", "=", item.account_id.id),
                ("company_id", "=", item.company_id.id),
            ]
            valuation = self.env["product.valuation.history"].search(domain, order="month desc", limit=1)
            if valuation:
                price = item.price
                # cantitățile reziduale (sub rotunjirea UoM) nu trebuie să producă prețuri aberante
                rounding = item.product_id.uom_id.rounding or 0.01
                if not float_is_zero(valuation.quantity_final, precision_rounding=rounding):
                    price = valuation.amount_final / valuation.quantity_final
                elif not float_is_zero(valuation.quantity_in, precision_rounding=rounding):
                    price = valuation.debit / valuation.quantity_in

                item.write(
                    {
                        "quantity": valuation.quantity_final,
                        "amount": valuation.amount_final,
                        "price": price,
                    }
                )

    def _recompute_amount_sql(self):
        """
        Recalculează valorile curente (quantity, amount, price) din `product.valuation`
        folosind un UPDATE SQL direct, bazat pe mișcările din notele contabile postate.

        Spre deosebire de `_recompute_amount` (care iterează Python), această metodă
        execută un singur UPDATE în baza de date, mai eficient pentru volume mari.

        Câmpurile actualizate:
        - `quantity` = cantitatea netă (intrări - ieșiri)
        - `amount` = debit - credit
        - `price` = amount / quantity (prețul anterior se păstrează dacă quantity e rezidual/zero)

        :return: None
        """
        if not self:
            return
        valuation_areas = self.mapped("valuation_area_id")
        products = self.mapped("product_id")
        accounts = self.mapped("account_id")

        # zerorizare înainte de UPDATE (vezi comentariul din varianta de pe istoric);
        # prețul se păstrează intenționat
        self.env.cr.execute(
            SQL(
                "UPDATE product_valuation SET quantity = 0, amount = 0 WHERE id in %(ids)s",
                ids=tuple(self.ids),
            )
        )

        inner = self._get_sql_select(
            account_ids=tuple(accounts.ids),
            product_ids=tuple(products.ids),
            valuation_area_ids=tuple(valuation_areas.ids) or (None,),
        )
        sql = SQL(
            """
          UPDATE product_valuation AS pv
          SET quantity = sub.quantity,
                amount = sub.debit - sub.credit,
                price = CASE WHEN abs(sub.quantity) >= %(qty_epsilon)s
                             THEN (sub.debit - sub.credit) / sub.quantity
                             ELSE pv.price END
            FROM (%(inner)s) as sub
            WHERE
                pv.product_id = sub.product_id AND
                pv.account_id = sub.account_id AND
                pv.valuation_area_id = sub.valuation_area_id AND
                pv.company_id = sub.company_id
        """,
            inner=inner,
            qty_epsilon=self._get_qty_epsilon(),
        )
        self.env.cr.execute(sql)
        self._invalidate_cache()

    def _get_sql_select(self, account_ids, product_ids=None, valuation_area_ids=None):
        """
        Returnează un obiect SQL care agregă mișcările contabile pe combinația
        (product_id, valuation_area_id, account_id, company_id), calculând:
        - `debit`, `credit` = totaluri monetare
        - `quantity_in` = cantitate intrată (in_invoice pozitiv, in_refund negativ)
        - `quantity_out` = cantitate ieșită (out_invoice pozitiv, out_refund negativ)
        - `quantity` = cantitate netă (ieșirile au semn negativ)

        Folosit în `_recompute_amount_sql` pentru UPDATE pe `product.valuation`.

        :param account_ids: tuple de ID-uri conturi de stoc (filtru obligatoriu)
        :param product_ids: tuple de ID-uri produse (None = toate)
        :param valuation_area_ids: tuple de ID-uri arii (None = toate)
        :return: obiect SQL compus
        """
        sub = self._get_sql_sub_select(account_ids, product_ids, valuation_area_ids)
        in_case, out_case = self._get_quantity_in_out_sql()
        return SQL(
            """
        SELECT product_id, valuation_area_id, account_id, company_id,
                sum(debit) as debit, sum(credit) as credit,
                sum(quantity * %(in_case)s) as quantity_in,
                sum(quantity * %(out_case)s) as quantity_out,
                sum(quantity * (%(in_case)s - %(out_case)s)) as quantity

            FROM (%(sub)s) as sub
             GROUP BY  product_id, valuation_area_id, account_id, company_id
        """,
            sub=sub,
            in_case=in_case,
            out_case=out_case,
        )

    def _get_sql_sub_select(self, account_ids, product_ids=None, valuation_area_ids=None):
        """
        Returnează un obiect SQL cu liniile individuale din `account_move_line`,
        filtrate după conturile de stoc și notele contabile postate.

        Calculează cantitatea convertită în UoM-ul produsului (template), folosind
        raportul factorilor UoM dintre linia de factură și UoM-ul produsului.

        Folosit ca subquery în `_get_sql_select` (clasa ProductValuation).

        :param account_ids: tuple de ID-uri conturi (filtru obligatoriu)
        :param product_ids: tuple de ID-uri produse; None = fără filtru pe produs
        :param valuation_area_ids: tuple de ID-uri arii; None = fără filtru pe arie
        :return: obiect SQL compus
        """
        if product_ids is None:
            return SQL(
                """
                    SELECT product_id, valuation_area_id, account_id, m.company_id,
                        debit, credit, move_type,
                        l.quantity * uom_line.factor / NULLIF(uom_template.factor, 0) as quantity
                    FROM account_move_line as l
                        LEFT JOIN account_move as m ON l.move_id=m.id
                        LEFT JOIN product_product product ON product.id = l.product_id
                        LEFT JOIN product_template template ON template.id = product.product_tmpl_id
                        LEFT JOIN uom_uom uom_line ON uom_line.id = COALESCE(l.product_uom_id, template.uom_id)
                        LEFT JOIN uom_uom uom_template ON uom_template.id = template.uom_id
                    WHERE
                        account_id in %(account_ids)s
                        AND m.state = 'posted'
                        AND l.product_id IS NOT NULL
            """,
                account_ids=account_ids,
            )
        return SQL(
            """
                SELECT product_id, valuation_area_id, account_id, m.company_id,
                    debit, credit, move_type,
                    l.quantity * uom_line.factor / NULLIF(uom_template.factor, 0) as quantity
                FROM account_move_line as l
                    LEFT JOIN account_move as m ON l.move_id=m.id
                    LEFT JOIN product_product product ON product.id = l.product_id
                    LEFT JOIN product_template template ON template.id = product.product_tmpl_id
                    INNER JOIN uom_uom uom_line ON uom_line.id = l.product_uom_id
                    INNER JOIN uom_uom uom_template ON uom_template.id = template.uom_id
                WHERE
                    account_id in %(account_ids)s
                    AND m.state = 'posted'
                    AND l.product_id IS NOT NULL
                    AND product_id in %(product_ids)s
                    AND valuation_area_id in %(valuation_area_ids)s
        """,
            account_ids=account_ids,
            product_ids=product_ids,
            valuation_area_ids=valuation_area_ids,
        )

    def _set_months_and_dates(self, params):
        self.env.cr.execute(
            """
            SELECT min(month) as min_month, max(month) as max_month
            FROM product_valuation_history
            WHERE valuation_area_id = %(valuation_area_id)s
              AND company_id = %(company_id)s
            """,
            params,
        )
        res = self.env.cr.dictfetchone()

        if res and res.get("min_month") and res.get("max_month"):
            params["max_month"] = res.get("max_month")
            params["min_month"] = res.get("min_month")
            params["min_date"] = datetime.strptime(params["min_month"], "%Y%m")
            params["max_date"] = datetime.strptime(params["max_month"], "%Y%m")
        else:
            params["max_month"] = fields.Date.today().strftime("%Y%m")
            params["min_month"] = fields.Date.today().strftime("%Y%m")
            params["min_date"] = datetime.today().replace(day=1)
            params["max_date"] = datetime.today().replace(day=1)

    def _recompute_all_amount(self):
        """
        Recalculează valorile curente din `product.valuation` pornind de la istoricul lunar.

        Pași:
        1. Șterge toate înregistrările existente din `product_valuation` pentru conturile de stoc.
        2. Determină luna maximă disponibilă din `product_valuation_history`.
        3. Inserează în `product_valuation` soldurile finale (quantity_final, amount_final, price)
           din luna maximă a istoricului, pentru fiecare combinație
           (product_id, valuation_area_id, account_id, company_id).

        Această metodă este complementară `_recompute_all_amount` din `ProductValuationHistory`
        care calculează istoricul lunar; aceasta preia doar soldul curent (ultima lună).

        :return: None
        """
        self.env.company.set_stock_valuation_at_company_level()
        valuation_area = self.env.company.valuation_area_id
        account_ids = tuple(self.env["account.account"].search([("is_for_stock_valuation", "=", True)]).ids)
        if not account_ids:
            return
        params = {
            "account_ids": account_ids,
            "valuation_area_id": valuation_area.id,
            "company_id": self.env.company.id,
        }
        # filtrul pe companie e esențial: conturile pot fi partajate între companii,
        # iar refresh-ul unei companii nu trebuie să șteargă evaluările celorlalte
        self.env.cr.execute(
            "DELETE FROM product_valuation WHERE account_id in %(account_ids)s AND company_id = %(company_id)s",
            params,
        )

        # Flush pending ORM writes so the raw SQL below reads up-to-date final balances
        # (quantity_final / amount_final are stored computed fields).
        self.env["product.valuation.history"].flush_model()

        # The current valuation is the running balance of the latest recorded history
        # month (which carries the cumulative quantity_final / amount_final forward).
        # Use the max available month instead of the calendar current month: otherwise,
        # on the first day of a new month with no movements yet, no row would match.
        self.env.cr.execute(
            """
            SELECT max(month) FROM product_valuation_history
            WHERE valuation_area_id = %(valuation_area_id)s
              AND company_id = %(company_id)s
            """,
            params,
        )
        row = self.env.cr.fetchone()
        params["max_month"] = (row and row[0]) or fields.Date.today().strftime("%Y%m")
        params["qty_epsilon"] = self._get_qty_epsilon()

        sql = """
        INSERT INTO product_valuation
                (product_id, valuation_area_id, account_id, company_id, currency_id,
                quantity,  amount, price)
           SELECT product_id, valuation_area_id, account_id, company_id, currency_id,
                         quantity_final as quantity, amount_final as amount,
                         CASE WHEN abs(quantity_final) >= %(qty_epsilon)s
                              THEN amount_final / quantity_final ELSE 0 END as price
            FROM product_valuation_history as pv

            WHERE month = %(max_month)s
              AND valuation_area_id = %(valuation_area_id)s
              AND company_id = %(company_id)s
        """
        self.env.cr.execute(sql, params)


class ProductValuationHistory(models.Model):
    _name = "product.valuation.history"
    _description = "Product Valuation History"
    _inherit = ["product.valuation"]
    _order = "product_id, month desc"

    month = fields.Char(string="Month", required=True, index=True)

    amount_initial = fields.Monetary("Initial Amount", default=0.0)
    quantity_initial = fields.Float("Initial Quantity", digits="Product Unit of Measure", default=0.0)

    quantity_in = fields.Float(string="Quantity In", digits="Product Unit of Measure", default=0.0)
    quantity_out = fields.Float(string="Quantity Out", digits="Product Unit of Measure", default=0.0)
    debit = fields.Monetary(string="Debit", default=0.0)
    credit = fields.Monetary(string="Credit", default=0.0)

    amount_final = fields.Monetary("Final Amount", compute="_compute_final", store=True, default=0.0)
    quantity_final = fields.Float(
        "Final Quantity", digits="Product Unit of Measure", compute="_compute_final", store=True, default=0.0
    )

    # suprascrie constrângerea moștenită din product.valuation cu varianta pe lună;
    # ON CONFLICT din _recompute_all_amount (pasul 3) depinde de acest index unic
    _combination_uniq = models.Constraint(
        "UNIQUE (product_id, valuation_area_id, account_id, company_id, month)",
        "Product valuation history must be unique",
    )

    def get_valuation(self, product_id, valuation_area_id, account_id, date, company_id=False):
        """
        Returnează înregistrarea istorică (product.valuation.history) pentru combinația
        (product_id, valuation_area_id, account_id, company_id) în luna corespunzătoare datei.

        Dacă nu există înregistrare pentru luna respectivă, creează una nouă preluând
        soldurile inițiale din ultima lună anterioară disponibilă (quantity_final, amount_final).
        Dacă nu există nicio lună anterioară, soldurile inițiale sunt 0.

        :param product_id: ID-ul produsului
        :param valuation_area_id: ID-ul zonei de evaluare
        :param account_id: ID-ul contului contabil de stoc
        :param date: data pentru care se caută istoricul (se extrage luna YYYYMM)
        :param company_id: ID-ul companiei (implicit: compania curentă)
        :return: recordset product.valuation.history
        """
        if not company_id:
            company_id = self.env.company.id

        month = date.strftime("%Y%m")

        domain = [
            ("product_id", "=", product_id),
            ("valuation_area_id", "=", valuation_area_id),
            ("account_id", "=", account_id),
            ("company_id", "=", company_id),
            ("month", "=", month),
        ]
        valuation = self.search(domain, limit=1)
        if not valuation:
            last_valuation = self.search(
                [
                    ("product_id", "=", product_id),
                    ("valuation_area_id", "=", valuation_area_id),
                    ("account_id", "=", account_id),
                    ("company_id", "=", company_id),
                    ("month", "<", month),
                ],
                order="month desc",
                limit=1,
            )
            if last_valuation:
                quantity_initial = last_valuation.quantity_final
                amount_initial = last_valuation.amount_final
            else:
                quantity_initial = 0
                amount_initial = 0

            valuation = self.create(
                {
                    "product_id": product_id,
                    "valuation_area_id": valuation_area_id,
                    "account_id": account_id,
                    "month": month,
                    "company_id": company_id,
                    "quantity_initial": quantity_initial,
                    "amount_initial": amount_initial,
                }
            )
        return valuation

    @api.depends("quantity", "amount", "quantity_initial", "amount_initial")
    def _compute_final(self):
        """
        Calculează soldurile finale ale lunii curente și propagă soldurile inițiale
        către luna imediat următoare.

        Logica:
        - `quantity_final = quantity_initial + quantity`
        - `amount_final = amount_initial + amount`
        - Dacă există o înregistrare pentru luna imediat următoare, actualizează
          `quantity_initial` și `amount_initial` ale acesteia cu valorile finale curente.

        :return: None
        """
        if self.env.context.get("skip_compute_final"):
            return
        for s in self:
            s.quantity_final = s.quantity_initial + s.quantity
            s.amount_final = s.amount_initial + s.amount
            domain = [
                ("product_id", "=", s.product_id.id),
                ("valuation_area_id", "=", s.valuation_area_id.id),
                ("account_id", "=", s.account_id.id),
                ("company_id", "=", s.company_id.id),
                ("month", ">", s.month),
            ]
            next_valuation = self.search(domain, order="month asc", limit=1)
            if next_valuation:
                next_valuation.update(
                    {
                        "quantity_initial": s.quantity_final,
                        "amount_initial": s.amount_final,
                    }
                )

    def _propagate_balances(self):
        """
        Recalculează soldurile inițiale/finale pentru TOATE lunile combinațiilor
        (product, valuation_area, account, company) din recordset, printr-un singur
        UPDATE SQL cu window function (sumă cumulată ordonată pe lună).

        Înlocuiește cascada Python din `_compute_final` (un search + write per lună)
        pe calea incrementală — esențial la corecții retroactive cu istoric lung.

        Ancora: soldul inițial al primei luni din serie (0 după un refresh complet);
        de la el, final(luna) = ancora + cumsum(mișcări) până la luna respectivă.

        :return: None
        """
        combos = {
            (item.product_id.id, item.valuation_area_id.id, item.account_id.id, item.company_id.id)
            for item in self
            if item.valuation_area_id
        }
        if not combos:
            return
        self.env.cr.execute(
            SQL(
                """
                WITH base AS (
                    SELECT DISTINCT ON (product_id, valuation_area_id, account_id, company_id)
                           product_id, valuation_area_id, account_id, company_id,
                           quantity_initial AS qty_base, amount_initial AS amt_base
                    FROM product_valuation_history
                    WHERE (product_id, valuation_area_id, account_id, company_id) IN %(combos)s
                    ORDER BY product_id, valuation_area_id, account_id, company_id, month ASC
                ),
                cumsum AS (
                    SELECT pvh.id,
                           b.qty_base + SUM(pvh.quantity) OVER w AS quantity_final,
                           b.amt_base + SUM(pvh.amount) OVER w AS amount_final
                    FROM product_valuation_history pvh
                    JOIN base b ON b.product_id = pvh.product_id
                              AND b.valuation_area_id = pvh.valuation_area_id
                              AND b.account_id = pvh.account_id
                              AND b.company_id = pvh.company_id
                    WINDOW w AS (
                        PARTITION BY pvh.product_id, pvh.valuation_area_id, pvh.account_id, pvh.company_id
                        ORDER BY pvh.month ASC
                        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
                    )
                )
                UPDATE product_valuation_history pv
                SET quantity_final   = cs.quantity_final,
                    amount_final     = cs.amount_final,
                    quantity_initial = cs.quantity_final - pv.quantity,
                    amount_initial   = cs.amount_final - pv.amount
                FROM cumsum cs
                WHERE pv.id = cs.id
                """,
                combos=tuple(combos),
            )
        )
        self._invalidate_cache()

    def _compute_initial(self):
        """
        Calculează soldurile inițiale ale lunii curente pornind de la soldurile finale,
        și propagă recursiv soldurile finale corecte către luna imediat anterioară.

        Logica:
        - `quantity_initial = quantity_final - quantity`
        - `amount_initial = amount_final - amount`
        - Dacă există o înregistrare pentru luna imediat anterioară, actualizează
          `quantity_final` și `amount_final` ale acesteia cu valorile inițiale curente,
          apoi apelează recursiv `_compute_initial` pe aceasta.

        Notă: Metoda nu este apelată activ în fluxul curent; este utilă pentru
        recalculări manuale sau corecții punctuale ale istoricului.

        :return: None
        """
        for item in self:
            item.quantity_initial = item.quantity_final - item.quantity
            item.amount_initial = item.amount_final - item.amount
            domain = [
                ("product_id", "=", item.product_id.id),
                ("valuation_area_id", "=", item.valuation_area_id.id),
                ("account_id", "=", item.account_id.id),
                ("company_id", "=", item.company_id.id),
                ("month", "<", item.month),
            ]
            prev_valuation = self.search(domain, order="month desc", limit=1)
            if prev_valuation:
                prev_valuation.write(
                    {
                        "quantity_final": item.quantity_initial,
                        "amount_final": item.amount_initial,
                    }
                )
                prev_valuation._compute_initial()

    def _get_sql_select(self, account_ids, product_ids=None, valuation_area_ids=None, months=None):
        """
        Returnează un obiect SQL care agregă mișcările contabile pe combinația
        (product_id, valuation_area_id, account_id, company_id, currency_id, month), calculând:
        - `debit`, `credit` = totaluri monetare lunare
        - `quantity_in` = cantitate intrată în luna respectivă
        - `quantity_out` = cantitate ieșită în luna respectivă
        - `quantity` = cantitate netă lunară (ieșirile au semn negativ)

        Folosit în `_recompute_amount` pentru UPDATE pe `product.valuation.history`.

        :param account_ids: tuple de ID-uri conturi (filtru obligatoriu)
        :param product_ids: tuple de ID-uri produse; None = fără filtru
        :param valuation_area_ids: tuple de ID-uri arii; None = fără filtru
        :param months: tuple de luni (format YYYYMM); None = fără filtru
        :return: obiect SQL compus
        """
        sub = self._get_sql_sub_select(account_ids, product_ids, valuation_area_ids, months)
        in_case, out_case = self._get_quantity_in_out_sql()
        return SQL(
            """
                    SELECT product_id, valuation_area_id, account_id, company_id, currency_id,   month,
                sum(debit) as debit, sum(credit) as credit,
                sum(quantity * %(in_case)s) as quantity_in,
                sum(quantity * %(out_case)s) as quantity_out,
                sum(quantity * (%(in_case)s - %(out_case)s)) as quantity

            FROM (%(sub)s) as sub
             GROUP BY  product_id, valuation_area_id, account_id, company_id, currency_id,  month
        """,
            sub=sub,
            in_case=in_case,
            out_case=out_case,
        )

    def _get_sql_sub_select(self, account_ids, product_ids=None, valuation_area_ids=None, months=None):
        """
        Returnează un obiect SQL cu liniile individuale din `account_move_line`,
        filtrate după conturile de stoc și notele contabile postate, incluzând luna (YYYYMM).

        Calculează cantitatea convertită în UoM-ul produsului (template), folosind
        raportul factorilor UoM dintre linia de factură și UoM-ul produsului.

        Folosit ca subquery în `_get_sql_select` (clasa ProductValuationHistory).

        :param account_ids: tuple de ID-uri conturi (filtru obligatoriu)
        :param product_ids: tuple de ID-uri produse; None = fără filtru
        :param valuation_area_ids: tuple de ID-uri arii; None = fără filtru
        :param months: tuple de luni YYYYMM; None = fără filtru
        :return: obiect SQL compus
        """
        if product_ids is None:
            return SQL(
                """
                SELECT product_id, valuation_area_id, account_id, m.company_id, l.company_currency_id as currency_id,
                        debit, credit, move_type,
                        to_char(m.date, 'YYYYMM')  as month,
                        l.quantity * uom_line.factor / NULLIF(uom_template.factor, 0) as quantity
                    FROM account_move_line as l
                        LEFT JOIN account_move as m ON l.move_id=m.id
                        LEFT JOIN product_product product ON product.id = l.product_id
                        LEFT JOIN product_template template ON template.id = product.product_tmpl_id
                        LEFT JOIN uom_uom uom_line ON uom_line.id = COALESCE(l.product_uom_id, template.uom_id)
                        LEFT JOIN uom_uom uom_template ON uom_template.id = template.uom_id
                    WHERE
                        account_id in %(account_ids)s
                        AND m.state = 'posted'
                        AND l.product_id IS NOT NULL
            """,
                account_ids=account_ids,
            )
        return SQL(
            """
            SELECT product_id, valuation_area_id, account_id, m.company_id, l.company_currency_id as currency_id,
                    debit, credit, move_type,
                    to_char(m.date, 'YYYYMM')  as month,
                    l.quantity * uom_line.factor / NULLIF(uom_template.factor, 0) as quantity
                FROM account_move_line as l
                    LEFT JOIN account_move as m ON l.move_id=m.id
                    LEFT JOIN product_product product ON product.id = l.product_id
                    LEFT JOIN product_template template ON template.id = product.product_tmpl_id
                    INNER JOIN uom_uom uom_line ON uom_line.id = l.product_uom_id
                    INNER JOIN uom_uom uom_template ON uom_template.id = template.uom_id
                WHERE
                    account_id in %(account_ids)s
                    AND m.state = 'posted'
                    AND l.product_id IS NOT NULL
                    AND product_id in %(product_ids)s
                    AND valuation_area_id in %(valuation_area_ids)s
                    AND to_char(m.date, 'YYYYMM') in %(months)s
        """,
            account_ids=account_ids,
            product_ids=product_ids,
            valuation_area_ids=valuation_area_ids,
            months=months,
        )

    def _recompute_amount(self):
        """
        Recalculează mișcările lunare (quantity, amount, debit, credit, quantity_in, quantity_out)
        din `product.valuation.history` pentru înregistrările din recordset curent,
        folosind un UPDATE SQL direct bazat pe notele contabile postate.

        După UPDATE, invalidează cache-ul câmpurilor computed și apelează `_compute_final`
        pentru a recalcula soldurile finale și a le propaga în lunile următoare.

        :return: None
        """
        if not self:
            return
        valuation_areas = self.mapped("valuation_area_id")
        products = self.mapped("product_id")
        accounts = self.mapped("account_id")

        # zerorizare înainte de UPDATE: dacă pentru o combinație nu mai există mișcări
        # postate (ex. notă de-postată), sub-query-ul nu întoarce rânduri și valorile
        # vechi ar rămâne altfel neschimbate
        self.env.cr.execute(
            SQL(
                """
                UPDATE product_valuation_history
                SET quantity = 0, quantity_in = 0, quantity_out = 0,
                    debit = 0, credit = 0, amount = 0
                WHERE id in %(ids)s
                """,
                ids=tuple(self.ids),
            )
        )

        inner = self._get_sql_select(
            account_ids=tuple(accounts.ids),
            product_ids=tuple(products.ids),
            months=tuple(self.mapped("month")),
            valuation_area_ids=tuple(valuation_areas.ids) or (None,),
        )
        sql = SQL(
            """
           UPDATE product_valuation_history AS pv
            SET quantity = sub.quantity,
                quantity_in = sub.quantity_in,
                quantity_out = sub.quantity_out,
                debit = sub.debit,
                credit = sub.credit,
                amount = sub.debit - sub.credit
            FROM (%(inner)s) as sub
            WHERE
                pv.product_id = sub.product_id AND
                pv.account_id = sub.account_id AND
                pv.valuation_area_id = sub.valuation_area_id AND
                pv.company_id = sub.company_id AND
                pv.month = sub.month
        """,
            inner=inner,
        )
        self.env.cr.execute(sql)
        # invalidate cached fields
        self._invalidate_cache()
        # propagarea soldurilor pe toate lunile combinațiilor afectate, într-un singur
        # UPDATE cu window function (cascada Python din _compute_final făcea un
        # search + write per lună)
        self._propagate_balances()

    def _recompute_all_amount(self, execute_step=None):
        """
        Recalculare completă a istoricului valorilor de stoc pe luni, bazată exclusiv pe notele contabile.

        Algoritmul parcurge următorii pași:

        1. **Ștergere date existente**: Se șterg toate înregistrările din `product_valuation_history`
           pentru zona de evaluare curentă (company level).

        2. **Calcul mișcări lunare** (INSERT din `_get_sql_select`):
           Se inserează în `product_valuation_history` câte o linie per combinație
           (product_id, valuation_area_id, account_id, company_id, month), cu:
           - `quantity` = cantitatea netă mișcată în luna respectivă (intrări pozitive, ieșiri negative)
           - `amount` = debit - credit (valoarea netă din notele contabile postate)
           - `debit`, `credit`, `quantity_in`, `quantity_out` = detalii mișcare

        3. **Completare luni lipsă**: Se generează o serie temporală completă (lună cu lună) între
           prima și ultima lună cu mișcări. Pentru combinațiile produs/cont care nu au mișcări
           într-o lună, se inserează linii cu valori 0 (ON CONFLICT DO NOTHING).

        4. **Calcul sold final pentru ultima lună** (din note contabile):
           Se calculează soldul cumulat total direct din `account_move_line`.

        5. **Propagare solduri pentru lunile anterioare** folosind fereastră SQL.

        6. **Ștergere linii goale**: Se elimină înregistrările fără nicio mișcare și fără sold.

        :return: None
        """
        if execute_step is None:
            execute_step = [1, 2, 3, 4, 5, 6]
        if not self.env.registry.ready:
            return
        self.env.company.set_stock_valuation_at_company_level()
        valuation_area = self.env.company.valuation_area_id

        params = {
            "account_ids": tuple(self.env["account.account"].search([("is_for_stock_valuation", "=", True)]).ids),
            "valuation_area_id": valuation_area.id,
            "company_id": self.env.company.id,
            "currency_id": self.env.company.currency_id.id,
        }

        # Verificare linii fără UoM care vor fi excluse
        self.env.cr.execute(
            """
            SELECT COUNT(*) as cnt, SUM(ABS(l.debit - l.credit)) as valoare
            FROM account_move_line l
            INNER JOIN account_move m ON l.move_id = m.id
            LEFT JOIN product_product p ON p.id = l.product_id
            LEFT JOIN product_template t ON t.id = p.product_tmpl_id
            WHERE l.account_id IN %(account_ids)s
              AND m.state = 'posted'
              AND m.company_id = %(company_id)s
              AND l.product_id IS NOT NULL
              AND t.uom_id IS NULL
        """,
            params,
        )
        row = self.env.cr.dictfetchone()
        if row and row["cnt"]:
            _logger.warning(
                "deltatech_stock_valuation: %d linii contabile excluse din evaluare (UoM produs lipsă), valoare totală: %s",
                row["cnt"],
                row["valoare"] or 0,
            )

        if 1 in execute_step:
            _logger.info("Stergere linii istoric")
            self.env.cr.execute(
                """
                DELETE FROM product_valuation_history
                WHERE company_id = %(company_id)s
                  AND (valuation_area_id = %(valuation_area_id)s OR valuation_area_id IS NULL);
            """,
                params,
            )

        if 2 in execute_step:
            _logger.info("Calculare linii istoric miscari lunare")

            inner = self._get_sql_select(account_ids=params["account_ids"])
            sql = SQL(
                """
                INSERT INTO product_valuation_history
                    (product_id, valuation_area_id, account_id, company_id, currency_id,  month,
                    quantity, quantity_in, quantity_out, debit, credit, amount)
                SELECT product_id, valuation_area_id, account_id, company_id, currency_id,  month,
                            quantity, quantity_in, quantity_out, debit, credit, debit-credit as amount
                FROM (%(inner)s) as a
            """,
                inner=inner,
            )
            self.env.cr.execute(sql)
            # move lines without explicit valuation_area_id are assigned to company area
            self.env.cr.execute(
                """
                UPDATE product_valuation_history
                SET valuation_area_id = %(valuation_area_id)s
                WHERE valuation_area_id IS NULL
                  AND company_id = %(company_id)s
                """,
                params,
            )

        # optinere data minima si maxima
        self._set_months_and_dates(params)

        # Asigurăm că max_date este cel puțin luna curentă pentru a avea istoric la zi
        today_month_date = datetime.today().replace(day=1)
        if params["max_date"] < today_month_date:
            params["max_date"] = today_month_date
            params["max_month"] = today_month_date.strftime("%Y%m")

        # Guard against a wrong move date producing a calendar of centuries: clamp the
        # lower bound so generate_series cannot blow up the history table.
        floor = params["max_date"] - relativedelta(years=_MAX_HISTORY_YEARS)
        if params["min_date"] < floor:
            _logger.warning(
                "deltatech_stock_valuation: history start %s is more than %d years before %s "
                "(likely a wrong move date); clamping to %s.",
                params["min_month"],
                _MAX_HISTORY_YEARS,
                params["max_month"],
                floor.strftime("%Y%m"),
            )
            params["min_date"] = floor
            params["min_month"] = floor.strftime("%Y%m")

        if 3 in execute_step:
            _logger.info("Adaugare linii lipsa")
            self.env.cr.execute("DROP TABLE IF EXISTS calendar_temporal")
            self.env.cr.execute(
                """
                CREATE TEMP TABLE calendar_temporal AS
                SELECT
                     to_char(generate_series, 'YYYYMM') AS month
                FROM
                    generate_series(%(min_date)s::date, %(max_date)s::date, '1 month'::interval)
                """,
                params,
            )
            self.env.cr.execute(
                """
                INSERT INTO product_valuation_history
                (
                    product_id, valuation_area_id, account_id, company_id, currency_id,  month,
                    quantity, amount, quantity_initial, amount_initial, quantity_final, amount_final,
                    quantity_in, quantity_out, debit, credit
                )
                SELECT
                    pa.product_id,
                    %(valuation_area_id)s as valuation_area_id,
                    pa.account_id,
                    %(company_id)s as company_id,
                    %(currency_id)s as currency_id,

                    c.month AS month,
                    0 as quantity,
                    0 as amount,
                    0 as quantity_initial,
                    0 as amount_initial,
                    0 as quantity_final,
                    0 as amount_final,
                    0 as quantity_in,
                    0 as quantity_out,
                    0 as debit,
                    0 as credit

                FROM
                    calendar_temporal c
                CROSS JOIN (SELECT DISTINCT product_id, account_id FROM product_valuation_history) pa
                ON CONFLICT (product_id, valuation_area_id, account_id, company_id, month) DO NOTHING
                """,
                params,
            )
            _logger.info("Liniile lipsa au fost adaugate")

        if 4 in execute_step:
            _logger.info("Calculare sold initial si final pentru ultima luna din note contabile")
            in_case, out_case = self._get_quantity_in_out_sql()
            sql_step4 = SQL(
                """
                    UPDATE product_valuation_history pv
                    SET
                        amount_initial = aml.total_amount - pv.amount,
                        quantity_initial = aml.total_quantity - pv.quantity,
                        amount_final = aml.total_amount,
                        quantity_final = aml.total_quantity
                    FROM (
                        SELECT l.product_id,
                               COALESCE(l.valuation_area_id, %(valuation_area_id)s) AS valuation_area_id,
                               l.account_id,
                               m.company_id,
                               SUM(l.debit - l.credit) AS total_amount,
                               SUM(
                                   l.quantity * uom_line.factor / NULLIF(uom_template.factor, 0)
                                   * (%(in_case)s - %(out_case)s)
                               ) AS total_quantity
                        FROM account_move_line l
                            LEFT JOIN account_move m ON l.move_id = m.id
                            LEFT JOIN product_product product ON product.id = l.product_id
                            LEFT JOIN product_template template ON template.id = product.product_tmpl_id
                            LEFT JOIN uom_uom uom_line ON uom_line.id = COALESCE(l.product_uom_id, template.uom_id)
                            LEFT JOIN uom_uom uom_template ON uom_template.id = template.uom_id
                        WHERE l.account_id IN %(account_ids)s
                            AND m.state = 'posted'
                            AND l.product_id IS NOT NULL
                        GROUP BY l.product_id, COALESCE(l.valuation_area_id, %(valuation_area_id)s), l.account_id, m.company_id
                    ) AS aml
                    WHERE pv.product_id = aml.product_id
                        AND pv.valuation_area_id = aml.valuation_area_id
                        AND pv.account_id = aml.account_id
                        AND pv.company_id = aml.company_id
                        AND pv.month = %(max_month)s;
                """,
                in_case=in_case,
                out_case=out_case,
                valuation_area_id=params["valuation_area_id"],
                account_ids=params["account_ids"],
                max_month=params["max_month"],
            )
            self.env.cr.execute(sql_step4)

        if 5 in execute_step:
            _logger.info("Calculare sold initial si final")
            self.env.cr.execute(
                """
                SELECT DISTINCT product_id
                FROM product_valuation_history
                WHERE valuation_area_id = %(valuation_area_id)s
                  AND company_id = %(company_id)s
                ORDER BY product_id
                """,
                params,
            )
            all_product_ids = [row[0] for row in self.env.cr.fetchall()]
            total = len(all_product_ids)
            for batch_start in range(0, total, _STEP5_SQL_BATCH):
                batch = tuple(all_product_ids[batch_start : batch_start + _STEP5_SQL_BATCH])
                self._execute_step5_sql(params, batch)
                if (batch_start // _STEP5_SQL_BATCH + 1) % 10 == 0:
                    _logger.info("Step 5: %d/%d produse procesate", batch_start + _STEP5_SQL_BATCH, total)

        _logger.info("FINALIZARE CALCULARE ISTORIC VALORI")

        if 6 in execute_step:
            _logger.info("Sterge linii goale ")
            self.env.cr.execute(
                """
                DELETE FROM product_valuation_history
                WHERE  valuation_area_id = %(valuation_area_id)s
                    and (quantity_initial is null or quantity_initial = 0)
                    and (quantity_final is null or quantity_final = 0)
                    and (quantity is null or quantity = 0)
                    and (amount_initial is null or amount_initial = 0)
                    and (amount is null or amount = 0)
                    and (amount_final is null or amount_final = 0) ;
                """,
                params,
            )

        _logger.info("Calculare sold initial si final varianta Python")

    def _execute_step5_sql(self, params, batch):
        self.env.cr.execute(
            """
            WITH cumsum AS (
                SELECT
                    id,
                    SUM(amount) OVER (
                        PARTITION BY product_id, valuation_area_id, account_id, company_id
                        ORDER BY month ASC
                        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
                    ) AS amount_final,
                    SUM(quantity) OVER (
                        PARTITION BY product_id, valuation_area_id, account_id, company_id
                        ORDER BY month ASC
                        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
                    ) AS quantity_final
                FROM product_valuation_history
                WHERE valuation_area_id = %(valuation_area_id)s
                  AND company_id = %(company_id)s
                  AND product_id IN %(batch)s
                  AND month <= %(max_month)s
            )
            UPDATE product_valuation_history pv
            SET amount_initial   = cs.amount_final - pv.amount,
                quantity_initial = cs.quantity_final - pv.quantity,
                amount_final     = CASE WHEN pv.month < %(max_month)s
                                       THEN cs.amount_final
                                       ELSE pv.amount_final END,
                quantity_final   = CASE WHEN pv.month < %(max_month)s
                                       THEN cs.quantity_final
                                       ELSE pv.quantity_final END
            FROM cumsum cs
            WHERE pv.id = cs.id
            """,
            {**params, "batch": batch},
        )

    def _recompute_step5_batch(self, product_id_start=0, click_batch_size=_STEP5_CLICK_BATCH):
        """Process step 5 for next click_batch_size products starting after product_id_start.
        Returns last processed product_id if more remain, None if all done."""
        self.env.company.set_stock_valuation_at_company_level()
        valuation_area = self.env.company.valuation_area_id
        params = {
            "valuation_area_id": valuation_area.id,
            "company_id": self.env.company.id,
        }
        self._set_months_and_dates(params)
        today_month_date = datetime.today().replace(day=1)
        if params["max_date"] < today_month_date:
            params["max_date"] = today_month_date
            params["max_month"] = today_month_date.strftime("%Y%m")

        self.env.cr.execute(
            """
            SELECT DISTINCT product_id
            FROM product_valuation_history
            WHERE valuation_area_id = %(valuation_area_id)s
              AND company_id = %(company_id)s
              AND product_id > %(product_id_start)s
            ORDER BY product_id
            LIMIT %(click_batch_size)s
            """,
            {**params, "product_id_start": product_id_start, "click_batch_size": click_batch_size},
        )
        product_ids = [row[0] for row in self.env.cr.fetchall()]
        if not product_ids:
            return None

        for i in range(0, len(product_ids), _STEP5_SQL_BATCH):
            batch = tuple(product_ids[i : i + _STEP5_SQL_BATCH])
            self._execute_step5_sql(params, batch)

        last_pid = product_ids[-1]
        self.env.cr.execute(
            """
            SELECT EXISTS(
                SELECT 1 FROM product_valuation_history
                WHERE valuation_area_id = %(valuation_area_id)s
                  AND company_id = %(company_id)s
                  AND product_id > %(last_pid)s
                LIMIT 1
            )
            """,
            {**params, "last_pid": last_pid},
        )
        has_more = self.env.cr.fetchone()[0]
        return last_pid if has_more else None

    def _auto_refresh_step(self):
        """Called by the scheduled action to auto-advance the refresh steps one sub-step
        at a time. The cron keeps the current step in `ir.config_parameter`, so it always
        knows what is left to execute. Records timing and notifies the initiating user."""
        ICP = self.env["ir.config_parameter"].sudo()
        step = int(ICP.get_param(_PARAM_STEP, "1"))

        start = fields.Datetime.now()
        t0 = time.monotonic()
        finished = False

        if step in (1, 2, 3, 4, 6):
            self._recompute_all_amount(execute_step=[step])
            ICP.set_param(_PARAM_STEP, str(step + 1))
        elif step == 5:
            last_pid = int(ICP.get_param(_PARAM_STEP5_LAST_PID, "0"))
            next_pid = self._recompute_step5_batch(product_id_start=last_pid)
            if next_pid is not None:
                ICP.set_param(_PARAM_STEP5_LAST_PID, str(next_pid))
            else:
                ICP.set_param(_PARAM_STEP5_LAST_PID, "0")
                ICP.set_param(_PARAM_STEP, "6")
        elif step == 7:
            self.env["product.valuation"]._recompute_all_amount()
            ICP.set_param(_PARAM_STEP, "1")
            cron = self.env.ref(
                "deltatech_stock_valuation.ir_cron_auto_refresh_valuation",
                raise_if_not_found=False,
            )
            if cron:
                cron.sudo().active = False
            finished = True
            _logger.info("Auto refresh valuation cycle complete. Cron deactivated.")

        duration = round(time.monotonic() - t0, 2)
        ICP.set_param(_PARAM_LAST_RUN, fields.Datetime.to_string(start))
        ICP.set_param(_PARAM_LAST_DURATION, str(duration))
        ICP.set_param(_PARAM_LAST_STEP, str(step))

        label = STEP_LABELS.get(step, "")
        if finished:
            self._notify_refresh(self.env._("Stock valuation refresh complete (%(s)ss).", s=duration), "success")
            ICP.set_param(_PARAM_NOTIFY_UID, "")
        else:
            self._notify_refresh(self.env._("%(label)s done in %(s)ss.", label=label, s=duration), "info")

    def _notify_refresh(self, message, msg_type="info"):
        """Best-effort toast notification to the user who started the background refresh."""
        ICP = self.env["ir.config_parameter"].sudo()
        uid = ICP.get_param(_PARAM_NOTIFY_UID)
        if not uid:
            return
        user = self.env["res.users"].browse(int(uid)).exists()
        if not user:
            return
        try:
            self.env["bus.bus"]._sendone(
                user.partner_id,
                "simple_notification",
                {
                    "type": msg_type,
                    "title": self.env._("Stock Valuation Refresh"),
                    "message": message,
                    "sticky": False,
                },
            )
        except Exception:  # pragma: no cover - notification must never break the cron
            _logger.exception("Could not send stock valuation refresh notification")
