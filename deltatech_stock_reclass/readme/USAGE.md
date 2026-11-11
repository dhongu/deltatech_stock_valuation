## 1. Define the allowed pairs of accounts

Open **Inventory → Operations → Reclassification Rules** and create a rule for each reclassification you accept: the **Source Account**, the **Destination Account** and, optionally:

- **Management Decision Required**: the document cannot be validated without the text of the management decision (use it when the destination of the goods changes);
- **Reason Required**: the document cannot be validated without a reason.

The pair of accounts is unique per company and the two accounts must differ. No rule is delivered with the module: each company creates the pairs it needs (for example *3028 → 371*).

![Reclassification rule 302800 → 371000: Source Account 302800 Other consumables and Destination Account 371000 Merchandise are highlighted, Destination Type is Stock account change, Management Decision Required is ticked and Reason Required is not](static/description/en/01_regula_reclasificare.png)

## 2. Create the reclassification document

Open **Inventory → Operations → Reclassifications** and create a document:

- **Rule**: brings the source and destination accounts (read only);
- **Source Location** and **Destination Location**: they can be the same location, when only the account changes, or two locations; the destination can also be a location outside the stock, but only when the destination account is not a stock account (for example stock → fixed asset): with a stock-to-stock rule the goods would leave the stock while the destination account keeps the value;
- **Journal** and **Date**, and **Management Decision** / **Reason** when the rule asks for them;
- in the **Products** tab: the product, the **Lot/Serial Number** (required for tracked products; a serial number has quantity 1), the **Quantity** and, optionally, the **Vendor Bill Line** the goods were bought with. The quantity reclassified on a bill line cannot exceed the quantity of the line.

![Draft reclassification: rule 302800 → 371000 and the Validate button are highlighted; source and destination location DC/Stock, journal Inventory Valuation, management decision filled in and the Products tab with Marfă de reclasificat, quantity 4.00](static/description/en/02_document_ciorna.png)

## 3. Validate

Press **Validate**. The module checks the rule, the decision and the reason, the lots and serial numbers and the stock available in the source location, then:

1. does an internal transfer of the products (it does not post the automatic valuation entry);
2. sets the **Unit Cost** and the **Value** of each line: the cost of the goods in stock at the validation date;
3. posts the journal entry on the chosen journal.

The document moves to **Done** and links the **Transfer** and the **Journal Entry**.

![Validated reclassification: the status is Done, the Transfer (DC/INT/00001) and Journal Entry fields are highlighted, and the product line shows quantity 4.00, unit cost 25.00 lei and value 100.00 lei](static/description/en/03_document_validat.png)

## 4. The journal entry

Open the **Journal Entry** from the document: it is posted on the chosen journal, with the reference of the document. It debits the destination account and credits the source account at the cost of the goods.

![Journal entry of the reclassification: credit 302800 Other consumables 100.00 lei and debit 371000 Merchandise 100.00 lei, with the product in the label of both lines](static/description/en/04_nota_contabila.png)

## 5. Decision or reason required by the rule

When the rule asks for the **Management Decision** (or the **Reason**), the field is required on the document. If it is empty, **Validate** does not go through: the field turns red and the message *Missing required fields* appears. Fill in the field and validate again.

![Draft document without the management decision after pressing Validate: the Management Decision field is red and the message Missing required fields appears in the top right corner; the document stays in Draft](static/description/en/05_decizie_obligatorie.png)

## 6. Cancel

**Cancel** on a validated document does a reverse transfer (from the destination location back to the source one, with the same products and serial numbers) and posts a reversal of the journal entry. If the stock in the destination is no longer enough, the cancellation is refused. A draft document is cancelled without transfer or entry. A validated document cannot be deleted, only cancelled. Cancel it only from the document, not with *Reverse Entry* on the journal entry: that button does not cancel the transfer, so the document and the entry would no longer match.

![Cancelled document: the status is Cancelled and the Reverse Transfer and Reversal Entry fields are highlighted next to the Transfer and Journal Entry](static/description/en/06_document_anulat.png)

## Access

Two groups control the module: **Reclassifications** (create and validate documents) and **Reclassification Configuration** (manage the rules). The **Reclassification Rules** menu (under **Inventory → Operations**) is visible only to the second one.
