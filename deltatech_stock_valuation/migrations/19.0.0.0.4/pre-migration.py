# ©  2026 Deltatech
# See README.rst file on addons root folder for license details

# Pregătire pentru constrângerile UNIQUE declarate cu models.Constraint (Odoo 19):
# - elimină dublurile existente (constrângerea pe product.valuation era dezactivată,
#   iar pe bazele instalate direct pe 19 lista _sql_constraints a fost ignorată)
# - elimină constrângerea cu numele vechi (din _sql_constraints) ca să nu coexiste
#   cu cea nouă creată de ORM


def migrate(cr, version):
    # dubluri în product_valuation: păstrăm înregistrarea cea mai recentă
    cr.execute(
        """
        DELETE FROM product_valuation pv
        USING product_valuation pv2
        WHERE pv.id < pv2.id
          AND pv.product_id = pv2.product_id
          AND pv.valuation_area_id IS NOT DISTINCT FROM pv2.valuation_area_id
          AND pv.account_id = pv2.account_id
          AND pv.company_id = pv2.company_id
        """
    )
    # dubluri în product_valuation_history (posibile doar pe baze instalate direct pe 19)
    cr.execute(
        """
        DELETE FROM product_valuation_history pv
        USING product_valuation_history pv2
        WHERE pv.id < pv2.id
          AND pv.product_id = pv2.product_id
          AND pv.valuation_area_id IS NOT DISTINCT FROM pv2.valuation_area_id
          AND pv.account_id = pv2.account_id
          AND pv.company_id = pv2.company_id
          AND pv.month = pv2.month
        """
    )
    cr.execute(
        """
        ALTER TABLE product_valuation_history
        DROP CONSTRAINT IF EXISTS product_valuation_history_product_valuation_history_uniq
        """
    )
