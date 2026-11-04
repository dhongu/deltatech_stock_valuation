1. Go to *Inventory > Configuration > Settings*, section *Valuation*. Tick *One Cost Method*
   and *Block Unvalued Moves*, check the *Cost Method* and *Valuation* of the company and save.

   ![Inventory settings, Valuation section: One Cost Method with the Cost Method, the Valuation and the Align the categories button, and Block Unvalued Moves, both ticked](static/description/en/01_setari_valuation_guard.png)

2. Click *Align the categories* to put every product category on the method of the company.
   Do it first on a test database: the cost of the products of the changed categories is
   recomputed. The previous costs are saved in a JSON attachment on the company.

   ![Confirmation of Align the categories, warning that the costs are recomputed and saved first](static/description/en/02_confirmare_aliniere.png)

3. Before switching the blocking on, open *Inventory > Reporting > Valuation Control*:
   *Categories with Another Cost Method* must be empty after the alignment, and in
   *Storable Products without Cost* set the cost of the products you still sell.

   ![Categories with Another Cost Method: the category Mărfuri FIFO, on another method than the company](static/description/en/03_categorii_alta_metoda.png)

   ![Storable Products without Cost: two storable products with a cost of zero](static/description/en/04_produse_fara_cost.png)

4. With *Block Unvalued Moves* on, validating a receipt, a delivery or an inventory
   adjustment of a product without value shows the list of the products to fix. Set the
   cost of the product, or the price on the purchase order, and validate again.

   ![A receipt refused at validation: the product enters the stock with no value](static/description/en/05_receptie_refuzata.png)

5. *Stock Valued at Zero* lists the stock that entered at zero value and is still on hand.
   Its revaluation is an accounting decision (which cost, which entry); the list shows
   what it concerns.

   ![Stock Valued at Zero: an incoming move done at zero value with its quantity still in stock](static/description/en/06_stoc_valorizat_zero.png)

6. *Moves Valued at Zero* shows the receipts and deliveries of the last 30 days that were
   valued at zero, to follow the effect of the checks.

   ![Moves Valued at Zero (last 30 days)](static/description/en/07_miscari_valorizate_zero.png)
