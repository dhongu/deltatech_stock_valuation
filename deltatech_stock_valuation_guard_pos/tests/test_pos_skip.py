from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestValuationGuardPosSkip(TransactionCase):
    def test_company_flag_is_loaded_in_the_register(self):
        config = self.env["pos.config"].create({"name": "Guard Register"})
        self.assertIn("valuation_guard_zero_cost", self.env["res.company"]._load_pos_data_fields(config))

    def test_pos_picking_moves_are_skipped(self):
        product = self.env["product.product"].create({"name": "POS Guard", "is_storable": True})
        stock = self.env["stock.warehouse"].search([("company_id", "=", self.env.company.id)], limit=1).lot_stock_id
        move = self.env["stock.move"].create(
            {
                "product_id": product.id,
                "product_uom_qty": 1.0,
                "product_uom": product.uom_id.id,
                "location_id": stock.id,
                "location_dest_id": self.env.ref("stock.stock_location_customers").id,
            }
        )
        self.assertFalse(move._valuation_guard_skip())
        config = self.env["pos.config"].create({"name": "Guard Register"})
        session = self.env["pos.session"].create({"config_id": config.id, "user_id": self.env.uid})
        picking = self.env["stock.picking"].create(
            {
                "picking_type_id": stock.warehouse_id.out_type_id.id,
                "location_id": stock.id,
                "location_dest_id": self.env.ref("stock.stock_location_customers").id,
                "pos_session_id": session.id,
            }
        )
        move.picking_id = picking
        self.assertTrue(move._valuation_guard_skip())
