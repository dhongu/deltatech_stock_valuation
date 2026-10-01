Configuration requires the **System Administrator** group.

1. **Valuation area.** Go to **Inventory → Configuration → Settings**, section **Valuation**, and
   tick **Use Valuation Area** (it comes from `deltatech_valuation_area`). Choose the **Valuation
   Area** of the company, or leave it empty: it is created automatically when you save.
2. **Area level.** In the same block, set **Valuation Area Level** to **Company**. This is the only
   level supported by the full recompute from the interface.
3. **Save the settings.** On saving, the module:
   - creates the valuation area of the company, if missing;
   - ticks **Stock Valuation** on the stock account of every product category;
   - moves the existing journal lines of the marked accounts to the area of the company.

   Settings are saved **per company**: repeat the configuration for each company, from that company.
   On a database with a lot of history, save the settings outside working hours.
4. **Valuation accounts.** In **Accounting → Configuration → Chart of Accounts**, check that every
   relevant stock account has **Stock Valuation** ticked. An unmarked account is not valued.
5. **Product categories.** In **Inventory → Configuration → Product Categories**, check that the
   **Costing Method** is **Average Cost (AVCO)** and the **Inventory Valuation** is **Automated**.
   Optionally tick **Use Valuation Area Price** (AVCO only; not compatible with FIFO).
6. **With `deltatech_obyc`** (recommended for Romanian companies), every storable product needs a
   **Valuation Class**.
7. **Without `deltatech_obyc`**, set **Loss Account** on the virtual inventory locations (inventory
   adjustments, scrap); otherwise adjustments and scrap post no entries. One loss account per
   location gives one counterpart for every stock account (for example 607 for 371, but 601 is
   expected for 301 and 608 for 381); with several stock accounts, use `deltatech_obyc`.
8. **Initial recompute.** After the first installation or a data import, run the full recompute
   (see *Usage*, step 7), once for each company. After the upgrade to 19.0.0.0.11 on a database
   with several companies, reset a background run that was in progress (it did not record its
   company) and run the full recompute from each company: the upgrade removes the valuation rows
   written by the old version on the area of another company.
