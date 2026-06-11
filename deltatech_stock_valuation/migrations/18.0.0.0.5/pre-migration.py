# ©  2026 Deltatech
# See README.rst file on addons root folder for license details

# Backport 19.0: pregătire pentru reactivarea constrângerii UNIQUE pe
# product_valuation — elimină dublurile existente (constrângerea era dezactivată).


def migrate(cr, version):
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
    cr.execute(
        """
        ALTER TABLE product_valuation_history
        DROP CONSTRAINT IF EXISTS product_valuation_history_product_valuation_uniq
        """
    )
