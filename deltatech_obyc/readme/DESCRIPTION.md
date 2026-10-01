# 📦 Deltatech OBYC - Product Account Determination

## Description
This module implements an account determination mechanism inspired by SAP OBYC (OBject-based valuation and account determination for inventorY and Cost management). It allows automatic selection of accounts based on:

- **Transaction Key** (e.g. stock_receipt, stock_delivery)
- **Valuation Class** (from the product)
- **Valuation Area** (e.g. by company, plant, warehouse)
- **Account Modifier** (from operation context)
- **Company**

## 🧩 Key Features

- Defines a flexible mapping table (`product.account.determination`) for automatic GL account assignment
- Introduces configurable master data:
  - `product.valuation.class` – assigned to product templates
  - `account.modifier` – optionally used in operations (e.g., picking types)
- Automatically selects source, destination, and valuation accounts during stock moves
- Transaction key determination logic for common inventory operations

## ⚠️ Cost of Goods Sold Is Booked at Delivery

For products with an OBYC valuation class, this module intentionally changes the standard
Odoo 20 behavior:

- **Standard Odoo 20 (real-time valuation):** the cost of goods sold is booked when the
  customer invoice is posted (COGS lines on the invoice).
- **With OBYC:** the cost of goods sold is booked at delivery, on the journal entry of the
  stock move (`stock_delivery` key, e.g. Dr 607 / Cr 371 for goods, Dr 711 / Cr 345 for
  finished products). The customer invoice only records the revenue and the VAT
  (Dr 4111 / Cr 707 + 4427) and has no COGS lines, so the cost is not booked twice.

This follows the Romanian accounting rules (OMFP 1802/2014, items 95, 283, 290 and
440–441): goods are removed from stock when control is transferred, which is usually the
delivery, not the invoice. See `readme/bugs.md` for the cases not covered yet (delivered but
not invoiced at month end, consignment, invoices issued before delivery).

## 🔄 Transaction Key Mapping (Default Logic)

| Source Location | Destination Location | Transaction Key |
|-----------------|----------------------|-----------------|
| Supplier        | Internal            | stock_receipt    |
| Internal        | Customer            | stock_delivery   |
| Internal        | Internal            | internal_transfer |
| Customer        | Internal            | return_from_customer |
| Internal        | Supplier            | return_to_supplier |
| Supplier        | Customer            | dropship         |

You can customize the transaction key determination logic in `stock.move` to support more complex cases.

## 📋 Comprehensive Transaction Keys List

The module implements the following transaction keys:

| Key                           | Description                   | Typical Accounting Impact                            | SAP Equivalent  |
|-------------------------------|-------------------------------|------------------------------------------------------|-----------------|
| **Stock Valuation**           |
| stock_valuation               | Stock Valuation               | Debit/Credit for valuation updates                   | BSX             |
| **Purchase Transactions**     |
| stock_receipt                 | Stock Receipt from Supplier   | Debit Inventory, Credit GR/IR clearing               | WRX             |
| return_to_supplier            | Return to Supplier            | Debit GR/IR clearing, Credit Inventory               | -               |
| **Sale Transactions**         |
| stock_delivery                | Delivery to Customer          | Debit COGS, Credit Inventory                         | VAX             |
| return_from_customer          | Return from Customer          | Debit Inventory, Credit COGS                         | -               |
| stock_income                  | Income Recognition            | Debit Receivables, Credit Revenue                    | SAL             |
| **Dropshipping Transactions** |
| dropship                      | Dropshipping                  | Debit COGS, Credit Payables                          | -               |
| dropship_return               | Dropshipping Return           | Debit Payables, Credit COGS                          | -               |
| **Internal Transfers**        |
| internal_transfer             | Internal Transfer             | Debit Destination Inventory, Credit Source Inventory | ZTR             |
| internal_transfer_out         | Internal Transfer Out         | Credit Source Inventory                              | -               |
| internal_transfer_in          | Internal Transfer In          | Debit Destination Inventory                          | -               |
| **Inventory Adjustments**     |
| inventory_adjustment_plus     | Positive Inventory Adjustment | Debit Inventory, Credit Inventory Adjustment         | BSX             |
| inventory_adjustment_minus    | Negative Inventory Adjustment | Debit Inventory Adjustment, Credit Inventory         | -               |
| **Production Transactions**   |
| production_issue              | Production Consumption        | Debit WIP, Credit Raw Materials                      | -               |
| production_receipt            | Production Receipt            | Debit Finished Goods, Credit WIP                     | -               |
| **Landed Costs**              |
| landed_cost                   | Landed Cost                   | Debit Inventory, Credit the cost line account        | -               |

A gain found at the count (inventory location → internal) uses `inventory_adjustment_plus`, a
loss (internal → inventory location) `inventory_adjustment_minus`; before 20.0.1.0.5 the two keys
were swapped (`readme/bugs.md` OBYC-005). The Romanian examples below book
production directly between the stock accounts and 601 / 711, without a WIP account.

## ⚙️ Models Introduced

- **product.account.determination**: Core mapping rule
- **product.valuation.class**: Master data used to group products by accounting behavior
- **account.modifier**: Optional field used to refine selection (similar to SAP account modifier)

## 📁 How it Works

When a stock move is processed:

1. **Transaction Key Determination**: The system computes a transaction key based on the source/destination locations and operation type
   ```
   Example: stock_receipt for supplier receipts, stock_delivery for customer deliveries
   ```

2. **Parameters Collection**:
  - Valuation class from product (e.g., "RM" for raw materials, "FG" for finished goods)
  - Valuation area from company (e.g., "MAIN" for main company)
  - Account modifier from picking type (e.g., "STD" for standard)

3. **Rule Matching**: It searches for a matching rule in `product.account.determination`
   ```
   Search criteria: Transaction Key + Valuation Class + Valuation Area + Account Modifier + Company
   ```

4. **Account Application**: If a rule is found, its accounts are used as follows:
  - **Stock move entry, Source Account set:** Dr **Valuation Account** / Cr **Source Account**
    (the Destination Account is ignored)
  - **Stock move entry, Source Account empty:** Dr **Destination Account** / Cr **Valuation Account**
  - **All three accounts empty:** no journal entry
  - **No entry, no rule needed:** products that are not storable, in a category without real-time
    valuation, zero quantities, stock owned by a third party, and moves between locations the
    standard valuation ignores (e.g. supplier → inventory location)
  - **Invoice product line:** sale documents (customer invoice, credit note) use the
    **Destination Account** of the `stock_income` rule; purchase documents (vendor bill, credit
    note) use the **Source Account** of the `stock_receipt` rule; the Valuation Account only
    when that account is empty. Credit notes use the same account as the invoice (booked in red
    on the same side with storno accounting, on the opposite side without it).
  - **Landed cost:** Dr **Valuation Account** of the `landed_cost` rule / Cr the account of the
    cost line


## 🧩 Account Determination Model

Each account determination rule (`product.account.determination`) contains:

1. **Transaction Key** (transaction_key): Defines the type of operation (stock_receipt, stock_delivery, etc.)
2. **Account Modifier** (account_modifier_id): Allows refinement of account selection
3. **Valuation Class** (valuation_class_id): Groups products by accounting behavior
4. **Valuation Area** (valuation_area_id): Allows different accounting per company/division
5. **Company** (company_id): The company for which the rule applies
6. **Source Account** (acc_src_id): When set, the credit side of the stock entry (the valuation
   account is debited); on vendor bills, the account of the product line (`stock_receipt` rule)
7. **Destination Account** (acc_dest_id): Used only when the Source Account is empty, as the
   debit side of the stock entry (the valuation account is credited); on customer invoices, the
   account of the product line (`stock_income` rule)
8. **Valuation Account** (acc_valuation_id): The stock account of the valuation class (e.g. 371,
   301, 345), on the other side of the entry

This flexible structure allows defining complex accounting rules for various types of inventory operations.

## 🛠️ Extensibility

- You can override the logic for transaction key computation per business scenario
- Add additional dimensions (e.g., storage location, product category) if needed
- Compatible with Odoo 20 Enterprise & Community
- Extensible for adaptation to industry specifics or special accounting requirements

## 📌 Usage Examples

### Basic Configuration

To configure the module:

1. Define valuation classes for products (e.g., Raw Materials, Semi-Finished, Finished Goods)
2. Define valuation areas for companies
3. Define account modifiers (optional)
4. Configure account determination rules in `product.account.determination`

### Typical Account Mappings

Romanian chart of accounts. Classes: MF = goods, RM = raw materials, FG = finished products.

| Key | Valuation Class | Source Account | Destination Account | Valuation Account | Resulting entry |
|-----|----------------|---------------|-------------------|-----------------|-------------|
| stock_receipt | MF | 408 | – | 371 | Dr 371 / Cr 408; vendor bill line on 408 |
| stock_receipt | RM | 408 | – | 301 | Dr 301 / Cr 408 |
| return_to_supplier | MF | – | 408 | 371 | Dr 408 / Cr 371 (storno: Dr 371 −V / Cr 408 −V) |
| stock_delivery | MF | – | 607 | 371 | Dr 607 / Cr 371 |
| stock_delivery | FG | – | 711 | 345 | Dr 711 / Cr 345 |
| return_from_customer | MF | 607 | – | 371 | Dr 371 / Cr 607 (storno: Dr 607 −V / Cr 371 −V) |
| stock_income | MF | – | 707 | – | customer invoice line on 707 |
| stock_income | FG | – | 701 | – | customer invoice line on 701 |
| dropship | MF | 408 | – | 607 | Dr 607 / Cr 408 |
| dropship_return | MF | 607 | – | 408 | Dr 408 / Cr 607 (storno: Dr 607 −V / Cr 408 −V) |
| production_issue | RM | – | 601 | 301 | Dr 601 / Cr 301 |
| production_receipt | FG | 711 | – | 345 | Dr 345 / Cr 711 |
| inventory_adjustment_plus (gains) | MF | 607 | – | 371 | Dr 371 / Cr 607 |
| inventory_adjustment_minus (losses) | MF | – | 607 | 371 | Dr 607 / Cr 371 |
| internal_transfer (same valuation area) | MF | – | – | – | no entry |
| landed_cost | MF | – | – | 371 | Dr 371 / Cr the cost line account |

The `dropship`, `dropship_return` and `stock_receipt` rules must use the same 408 account: the
vendor bill of a drop shipment takes its account from the `stock_receipt` rule.

Each of these mappings can vary by product class or warehouse (valuation area).

## 🔍 Comparison with SAP OBYC

This module is inspired by the SAP OBYC concept but adapted for the Odoo ecosystem. The main differences include:

- Simplification: Transaction keys are named descriptively rather than using SAP codes
- Integration: Works natively with the Odoo inventory system
- Flexibility: Allows simpler customizations than the original SAP system
- Structure: Uses concepts familiar to Odoo users (products, locations, stock moves)

## 📚 Additional Resources

- [Odoo Accounting Documentation](https://www.odoo.com/documentation/20.0/applications/finance/accounting.html)
- [Odoo Inventory Management Documentation](https://www.odoo.com/documentation/20.0/applications/inventory_and_mrp/inventory.html)
- [SAP OBYC Reference](https://community.sap.com/t5/enterprise-resource-planning-blog-posts-by-members/automatic-account-determination-overview/ba-p/13262637)

## 📣 Important Notes

- Ensure you understand the accounting implications before configuring this module
- Test the configuration in a test environment before using it in production
- Consult with an accounting expert to ensure compliance with local accounting regulations
- The module targets Odoo 20
- Retail-price stock (371 with the markup on 378 and the VAT on 4428) is not supported: stock is valued at cost

## 🧮 Three-Account System

Each rule has three accounts, but a stock entry always uses two of them:

1. **Valuation Account** (acc_valuation_id): the stock account of the valuation class (371 goods,
   301 raw materials, 345 finished products). It is always one side of the stock entry.
2. **Source Account** (acc_src_id): when set, the entry is Dr Valuation / Cr Source (stock in:
   receipt, return from customer, production receipt, inventory gain).
3. **Destination Account** (acc_dest_id): used only when the Source Account is empty; the entry is
   Dr Destination / Cr Valuation (stock out: delivery, return to supplier, production issue,
   inventory loss).

On invoices the account of the product line depends on the document type: Destination Account
of `stock_income` for sale documents, Source Account of `stock_receipt` for purchase documents.
Price and exchange rate differences between the receipt and the vendor bill are not handled by
the module; they stay on the GR/IR account (408) and are regularized manually.

## 📊 Transaction Key Use Cases

### Purchase Flow

- **stock_receipt**: goods received from a supplier
  - Source Account: GR/IR clearing (408), Valuation Account: inventory (371)
  - Entry: Dr 371 / Cr 408; the vendor bill line is booked on the Source Account (Dr 408)

- **return_to_supplier**: goods returned to a supplier
  - Destination Account: GR/IR clearing (408), Valuation Account: inventory (371)
  - Entry: Dr 408 / Cr 371; with storno accounting: Dr 371 −V / Cr 408 −V

### Sales Flow

- **stock_delivery**: goods delivered to a customer (cost of goods sold at delivery)
  - Destination Account: COGS (607, or 711 for finished products), Valuation Account: inventory
  - Entry: Dr 607 / Cr 371

- **return_from_customer**: goods returned by a customer
  - Source Account: COGS (607), Valuation Account: inventory (371)
  - Entry: Dr 371 / Cr 607; with storno accounting: Dr 607 −V / Cr 371 −V

- **stock_income**: revenue on the customer invoice
  - Destination Account: revenue (707, or 701 for finished products)
  - The customer invoice and credit note product lines use this account; no stock entry

### Inventory Management

- **inventory_adjustment_plus**: gain found at the count (inventory location → internal)
  - Source Account: 607, Valuation Account: inventory (371)
  - Entry: Dr 371 / Cr 607

- **inventory_adjustment_minus**: loss found at the count (internal → inventory location)
  - Destination Account: expense (607), Valuation Account: inventory (371)
  - Entry: Dr 607 / Cr 371

### Manufacturing

- **production_issue**: materials consumed in production
  - Destination Account: 601, Valuation Account: raw materials (301)
  - Entry: Dr 601 / Cr 301

- **production_receipt**: finished goods received from production
  - Source Account: 711, Valuation Account: finished products (345)
  - Entry: Dr 345 / Cr 711

### Special Cases

- **dropship**: direct delivery from supplier to customer
  - Source Account: GR/IR clearing (408), Valuation Account: COGS (607)
  - Entry: Dr 607 / Cr 408

- **internal_transfer**: transfer between locations of the same valuation area
  - No accounts: no entry (the stock value does not change)

- **internal_transfer_out / internal_transfer_in**: transfer between valuation areas through a
  transit location
  - Out (area of the sending location): Destination Account 371.09 (goods in transit),
    Valuation Account 371.01; entry Dr 371.09 / Cr 371.01
  - In (area of the receiving location): Source Account 371.09, Valuation Account 371.02;
    entry Dr 371.02 / Cr 371.09
  - Not a validated route: in Odoo 20 the stock → transit move gets no value, so these entries
    are expected to be posted at 0 (`readme/bugs.md`, OBYC-009). Do not use it for transfers
    between valuation areas until OBYC-009 is fixed.
