import {describe, expect, test} from "@odoo/hoot";
import {definePosModels} from "@point_of_sale/../tests/unit/data/generate_model_definitions";
import {setupPosEnv} from "@point_of_sale/../tests/unit/utils";

definePosModels();

async function setupStore(guard) {
    const store = await setupPosEnv();
    store.company.valuation_guard_zero_cost = guard;
    const template = store.models["product.template"].get(5);
    template.is_storable = true;
    const product = template.product_variant_ids[0];
    return {store, template, product};
}

describe("@deltatech_stock_valuation_guard_pos cart", () => {
    test("a storable product without cost is not added to the cart", async () => {
        const {store, template, product} = await setupStore(true);
        product.standard_price = 0;
        const order = store.addNewOrder();
        await store.addLineToOrder({product_tmpl_id: template}, order);
        expect(order.getOrderlines().length).toBe(0);
    });

    test("a storable product with cost is added", async () => {
        const {store, template, product} = await setupStore(true);
        product.standard_price = 12.5;
        const order = store.addNewOrder();
        await store.addLineToOrder({product_tmpl_id: template}, order);
        expect(order.getOrderlines().length).toBe(1);
    });

    test("without the company setting the product without cost is added", async () => {
        const {store, template, product} = await setupStore(false);
        product.standard_price = 0;
        const order = store.addNewOrder();
        await store.addLineToOrder({product_tmpl_id: template}, order);
        expect(order.getOrderlines().length).toBe(1);
    });

    test("a refund line of a product without cost is not blocked", async () => {
        const {store, product} = await setupStore(true);
        product.standard_price = 0;
        expect(store.valuationGuardBlocks({product_id: product, qty: -1}, store.addNewOrder())).toBe(false);
    });
});
