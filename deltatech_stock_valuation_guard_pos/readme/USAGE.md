1. Tick *Block Unvalued Moves* in *Inventory > Configuration > Settings*, section
   *Valuation* (module *Stock Valuation Guard*). Registers opened before need a reload.
2. In the register, a storable product without cost cannot be added to the order: the
   register shows *Product without cost* and the cart stays as it was. Ask the manager to
   set the cost of the product, then reload the register.

   ![The register with the Product without cost message over the product list](static/description/en/01_pos_produs_fara_cost.png)

Refunds, consumables and services are not blocked. A variant chosen in the variant
configurator is not checked; it shows up in the control lists of *Stock Valuation Guard*.
