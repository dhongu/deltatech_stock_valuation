import {AlertDialog} from "@web/core/confirmation_dialog/confirmation_dialog";
import {PosStore} from "@point_of_sale/app/services/pos_store";
import {_t} from "@web/core/l10n/translation";
import {patch} from "@web/core/utils/patch";

patch(PosStore.prototype, {
    /**
     * The product to check: the variant given by the caller, or the only variant of the template.
     * A template with several variants and no variant given yet is let through: the variant is
     * chosen later, in the configurator, and such products show up in the control lists.
     */
    _valuationGuardProduct(vals) {
        if (vals.product_id) {
            return vals.product_id;
        }
        const template =
            typeof vals.product_tmpl_id === "number"
                ? this.data.models["product.template"].get(vals.product_tmpl_id)
                : vals.product_tmpl_id;
        const variants = template?.product_variant_ids || [];
        return variants.length === 1 ? variants[0] : null;
    },

    valuationGuardBlocks(vals, order) {
        if (!this.company.valuation_guard_zero_cost || order?.preset_id?.is_return) {
            return false;
        }
        if ((vals.qty ?? 1) <= 0) {
            return false;
        }
        const product = this._valuationGuardProduct(vals);
        return Boolean(product && product.product_tmpl_id?.is_storable && !(product.standard_price > 0));
    },

    async addLineToOrder(vals, order, opts = {}, configure = true) {
        if (this.valuationGuardBlocks(vals, order)) {
            const product = this._valuationGuardProduct(vals);
            this.dialog.add(AlertDialog, {
                title: _t("Product without cost"),
                body: _t(
                    "%s has no cost, so its sale would leave the stock with no value. " +
                        "Ask the manager to set the cost of the product.",
                    product.display_name
                ),
            });
            return;
        }
        return await super.addLineToOrder(vals, order, opts, configure);
    },
});
