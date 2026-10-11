Evaluarea stocului pe fiecare lot / număr de serie.

### Funcționalități

- **Preț propriu pe lot** — câmpurile `Unit Price`, `Input Price`, `Input date` și `Inventory value`
  pe lot/serie, completate la recepția de la furnizor.
- **Ieșiri la prețul lotului** — mișcarea de ieșire a unui produs cu urmărire se valorizează cu
  suma `preț lot × cantitate` pe fiecare linie, deci și nota contabilă urmează costul real al lotului.
  Liniile fără lot sau cu lot fără preț rămân la costul calculat de Odoo.
- **Valoarea stocului în `stock.quant`** — coloana *Value* și prețul unitar al quantului se calculează
  din prețul lotului (pe serie, din `Inventory value`).
- **Inventar** — liniile din `deltatech_stock_inventory` preiau prețul lotului.

Modulul nu folosește valorizarea nativă pe lot din Odoo (`lot_valuated`, `lot.standard_price`) și
nu trebuie activată împreună cu ea pe aceleași produse.

**Raportul de evaluare pe conturi** (Inventar → Rapoarte → Stock Valuation) și închiderea evaluării
stocului iau valoarea produselor cu urmărire din prețul fiecărui lot. Prețurile loturilor nu au istoric:
pentru o dată din trecut se folosește cantitatea lotului la acea dată înmulțită cu prețul curent, deci
raportul trebuie rulat după înregistrarea tuturor landed cost-urilor și a facturilor.
