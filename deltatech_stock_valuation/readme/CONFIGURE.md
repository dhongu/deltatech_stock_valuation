Configuration requires the **System Administrator** group.

1. **Valuation area.** Go to **Inventory → Configuration → Settings**, section **Valuation**, and
   tick **Use Valuation Area** (it comes from `deltatech_valuation_area`). Choose the **Valuation
   Area** of the company, or leave it empty: it is created automatically when you save.
2. **Area level.** In the same block, under **Stock Valuation**, set **Valuation Area Level** to
   **Company**. This is the only level supported by the full recompute from the interface; with
   Warehouse or Location the recompute button is not shown.
3. **Keep the move value.** In the same section, leave **Keep move value on retroactive recompute**
   ticked (it is ticked by default; it comes from `deltatech_valuation_area` and matters only for
   categories with **Use Valuation Area Price**). With it, outgoing moves valued at the area price
   keep their unit price after a retroactive correction (changed date, edited quantity, revalued
   receipt), consistent with the posted journal entries. Unticked, the standard Odoo 20 recompute
   rewrites them at the global average cost and the posted journal entries are **not** corrected,
   so the stock value and the accounting can diverge. Untick it only if the customer asks for it.
4. **Save the settings.** On saving, the module:
   - creates the valuation area of the company, if missing;
   - ticks **Stock Valuation** on the stock account of every product category;
   - moves the existing journal lines of the marked accounts to the area of the company.

   On a database without any valuation account, saving ends without error.

   Settings are saved **per company**: repeat the configuration for each company, from that company.
   On a database with a lot of history, save the settings outside working hours.
5. **Valuation accounts.** In **Accounting → Configuration → Accounting → Chart of Accounts**, check that every
   relevant stock account has **Stock Valuation** ticked. An unmarked account is not valued.
6. **Product categories.** In **Inventory → Configuration → Products → Product Categories**, on the
   **Accounting** tab, check that the **Costing Method** is **Average Cost (AVCO)** and the
   **Inventory Valuation** is **Perpetual (at invoicing)**. With **Periodic (at closing)** the
   module receives no data from receipts, deliveries or invoices. Optionally tick **Use Valuation
   Area Price** (AVCO only; not compatible with FIFO). These values appear in English in every
   interface language.
7. **With `deltatech_obyc`** (recommended for Romanian companies), every storable product needs a
   **Valuation Class**.
8. **Without `deltatech_obyc`**, set **Loss Account** on the virtual inventory locations (inventory
   adjustments, scrap); otherwise adjustments and scrap post no entries.
9. **Initial recompute.** After the first installation or a data import, run the full recompute
   (see *Usage*, step 7), once for each company.
