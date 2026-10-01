# ©  2026 Deltatech
# See README.rst file on addons root folder for license details

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Cheile de ajustare de inventar erau inversate până la 20.0.1.0.5 (OBYC-005): plusul
    folosea regula `inventory_adjustment_minus`, minusul regula `inventory_adjustment_plus`.
    Regulile nu se modifică automat; se semnalează în log cele configurate după
    comportamentul vechi (un plus care ar credita stocul, un minus care l-ar debita), ca să
    fie verificate și, la nevoie, să li se schimbe cheia."""
    if not version:
        return
    cr.execute(
        """
        SELECT id, transaction_key, company_id
          FROM product_account_determination
         WHERE (transaction_key = 'inventory_adjustment_plus' AND acc_src_id IS NULL AND acc_dest_id IS NOT NULL)
            OR (transaction_key = 'inventory_adjustment_minus' AND acc_src_id IS NOT NULL)
        """
    )
    for rule_id, transaction_key, company_id in cr.fetchall():
        _logger.warning(
            "OBYC-005: account determination rule %s (%s, company %s) looks configured for the old, "
            "swapped inventory adjustment keys. Since 20.0.1.0.5 a gain uses inventory_adjustment_plus "
            "and a loss inventory_adjustment_minus; check the rule and swap its key if needed.",
            rule_id,
            transaction_key,
            company_id,
        )
