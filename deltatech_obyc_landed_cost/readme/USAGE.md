## Configuration

1. Go to *Inventory → Configuration → Settings*, block **Valuation**.
2. Set **Landed Cost Class 6 Method** to *Through intermediary account* and choose the **Intermediary
   Account** (a technical account defined by the company accounting policy).
3. Make sure the OBYC rule **Landed Costs** (`landed_cost`) has the **Valuation Account** filled.

![Landed cost method setting](static/description/en/01_settings_landed_cost.png)

## Usage

1. Open *Inventory → Operations → Adjustments → Landed Costs*, create a document on a receipt, add a
   cost line (for example transport, 50 lei, account 624) and click **Compute**, then **Validate**.
   The same document can be created from a vendor bill: the receipts of the bill's purchase orders
   not yet covered by another landed cost and the account of each bill line are filled in.

![Vendor bill with the Create Landed Costs button](static/description/en/05_vendor_bill_button.png)

![Validated landed cost](static/description/en/02_landed_cost_form.png)

2. Open the journal entry. With the standard method it is Dr stock / Cr 624:

![Standard entry](static/description/en/03_note_standard.png)

   With the intermediary method it is Dr stock / Cr intermediary and Dr intermediary / Cr 624:

![Entry through the intermediary account](static/description/en/04_note_intermediary.png)

Class 609, accounts outside class 6 and the debit of a negative cost are never rerouted.
