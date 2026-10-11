## 19.0.1.0.0 (2026-10-05)

- Migrare din 18.0. Logica bazată pe `stock.valuation.layer` este înlocuită: ieșirea se valorizează
  în `stock.move._set_value` (valoarea mișcării = suma `preț lot × cantitate`), iar costul unitar al
  recepției se citește din `stock.move._get_price_unit()`.
- Un lot fără preț propriu nu mai valorizează ieșirea la 0, ci la costul calculat de Odoo; la fel
  quantul și liniile de inventar.
- Dispar: filtrul pe straturile de evaluare (`_search`/`read_group`), valorizarea transferului intern
  prin straturi, câmpul `location_id` pe lot (există în nucleul 19) și modificarea raportului de
  inventar.
- Raportul „Stock Valuation” și închiderea evaluării stocului (`res.company.stock_value`) iau valoarea
  produselor cu urmărire de pe loturi, nu din totalul FIFO/mediu al produsului calculat de nucleu. Cu
  dată în trecut se folosește cantitatea lotului la acea dată × prețul curent al lotului, deci raportul
  se rulează după toate modificările de valoare (landed cost, facturi).
- Recepția unui lot care mai are stoc: la același preț ca ultima recepție costul unitar al lotului rămâne
  (crește doar `Inventory value`); la preț diferit recepția este refuzată cu o eroare, pentru că prețul
  propriu al lotului nu poate reprezenta două costuri. Un lot fără stoc primește prețul noii recepții.
- Incompatibil cu `l10n_ro_stock_account`: modulul este declarat în `excludes`, pentru că „FIFO pe locație”
  valorizează ieșirile pe straturi și ignoră prețul lotului.
