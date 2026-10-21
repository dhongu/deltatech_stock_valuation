Two checks that keep the stock valuation trustworthy, each switched on per company.

**One cost method for every product category**

In Odoo the cost method (Standard, FIFO, Average) and the valuation (periodic or perpetual)
are set on each product category. Nothing stops two categories of the same company from
using different methods, and over the years a database ends up with a mix — some
categories on FIFO, others on Standard — which the accounting has to explain at every
closing.

- With *One Cost Method* ticked, a product category can only use the cost method and the
  valuation of the company: creating or changing a category to another method is refused.
- *Align the categories* puts every category of the company on its method in one step.
  Odoo recomputes the cost of the products of every category whose method changes, so the
  current costs are saved first, in a JSON attachment on the company, to allow a targeted
  revert.

**No stock move without a value**

A product that enters the stock at zero value — an opening inventory counted without
costs, a quantity typed on the product form, a receipt at price zero — leaves the stock at
zero value too, and the cost of goods sold of every later sale is zero. With
*Block Unvalued Moves* ticked:

- an incoming move of a storable product is refused when its value would be zero: receipt
  without a price, inventory gain or quantity update of a product without cost, return
  valued at zero;
- an outgoing move is refused when the product has no cost.

**Control lists** (*Inventory > Reporting > Valuation Control*)

- categories using another cost method than the company;
- storable products without cost;
- stock valued at zero: incoming moves valued at zero with quantity still left in stock,
  that the next sales will take out at zero cost;
- moves valued at zero in the last 30 days.

The module blocks the moves validated by users. Moves validated by a process the user does
not drive, such as the orders of the Point of Sale, are handled by *Stock Valuation Guard -
Point of Sale*, which stops the product at the cart instead.
