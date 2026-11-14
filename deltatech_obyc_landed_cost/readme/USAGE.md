## Configuration

1. Go to *Inventory → Configuration → Settings*, block **Valuation**.
2. Set **Landed Cost Class 6 Method** to *Through intermediary account* and choose the **Intermediary
   Account** (a technical account defined by the company accounting policy, not a class 6 account).
3. Make sure the OBYC rule **Landed Costs** (`landed_cost`) has the **Valuation Account** filled.

![Landed cost method setting](static/description/en/01_settings_landed_cost.png)

## Usage

1. Confirm a purchase order for the goods.

![Confirmed purchase order](static/description/en/02_purchase_order.png)

2. Validate the receipt of the purchase order. OBYC posts Dr stock / Cr goods received not invoiced.

![Validated receipt](static/description/en/03_receipt.png)

![Receipt entry](static/description/en/04_receipt_note.png)

3. Create and post the vendor bill of the goods.

![Vendor bill of the goods](static/description/en/05_goods_bill.png)

4. Post the transport vendor bill, with a line of a product flagged as landed cost, then click
   **Create Landed Costs**. The receipts of the purchase orders on the bill not yet covered by another
   landed cost are filled in (otherwise add the receipt in the **Transfers** field), and the account of
   each cost line is taken from the bill line.

![Transport bill with the Create Landed Costs button](static/description/en/06_transport_bill_button.png)

5. **Compute** and **Validate** the landed cost.

![Validated landed cost](static/description/en/07_landed_cost_form.png)

6. With the standard method the entry is Dr stock / Cr 624:

![Standard entry](static/description/en/08_note_standard.png)

   With the intermediary method it is Dr stock / Cr intermediary and Dr intermediary / Cr 624:

![Entry through the intermediary account](static/description/en/09_note_intermediary.png)

Class 609, accounts outside class 6 and the debit of a negative cost are never rerouted.
