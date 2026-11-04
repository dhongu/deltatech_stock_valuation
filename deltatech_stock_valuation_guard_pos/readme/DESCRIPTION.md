Point of Sale side of *Stock Valuation Guard*.

The moves of a POS order are validated when the order reaches the server, after the
fiscal receipt was printed. Refusing them there would leave the order stuck in the
register, so this module moves the check to the cart:

- with *Block Unvalued Moves* ticked on the company, a storable product without cost
  cannot be added to an order: the register shows a message asking for the cost of the
  product;
- refunds are not blocked;
- the moves of POS orders are not checked again on the server.

A product template with several variants is checked only when the variant is given
directly (scan, variant card); when the variant is chosen in the configurator, the
product shows up in the control lists of *Stock Valuation Guard* instead.

The module is installed automatically with *Stock Valuation Guard* and *Point of Sale*.
