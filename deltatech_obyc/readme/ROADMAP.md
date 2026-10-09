## Mai multe chei de tranzacție pe aceeași mișcare — planificat, fără client care să o ceară încă

Azi o mișcare de stoc are **o singură cheie** (din perechea de locații) și **o singură regulă**,
deci `_get_account_move_line_vals()` produce o notă cu **două linii** (debit și credit) pe o
singură sumă, `move.value`. Din acest motiv nu se pot obține din configurare:

- livrarea directă prin stoc pe o singură mișcare furnizor → client:
  Dr 371 / Cr 408 și, în același moment, Dr 607 / Cr 371 (cheile `stock_receipt` și
  `stock_delivery`, deja existente). Azi: ruta în 2 pași (furnizor → gestiune → client);
- consignația (OBYC-003, etapa 1: Dr 357 / Cr 371) fără o locație intermediară;
- gestiunea la preț de vânzare, cu adaos (378) și TVA neexigibil (4428) pe aceeași mișcare
  (la clienții cu retail se folosește familia OCA `l10n_ro_stock_account_retail`, care nu se
  instalează împreună cu OBYC).

**Schiță** (în SAP, o mișcare de mărfuri poate activa mai multe chei, iar documentul contabil
are câte o linie pe cheie):

1. `stock.move._get_obyc_postings()` întoarce o listă `[(transaction_key, amount)]`;
   implicit un singur element, `(cheia mișcării, move.value)` — comportamentul actual.
2. Schema aleasă prin configurare, pe `account.modifier` (câmp nou `posting_scheme`:
   `single` implicit, `dropship_via_stock`, mai târziu `retail`). Modificatorul e deja legat de
   tipul de operațiune, deci alegerea rămâne o configurare.
3. `_get_account_move_line_vals()` devine o buclă pe posting-uri: `_get_rule_account(key=...)`
   (parametru opțional) și o pereche debit/credit pe fiecare.

Impact de verificat: `_should_create_account_move` (regulile tuturor posting-urilor),
`account_move_line.py` și `product_template.py` (căutări de reguli pe chei fixe), hook-ul din
`deltatech_valuation_area` (aria pe liniile din `super()`), cantitatea semnată pe liniile de
sumă pură (0), retururile (schema inversă), portul pe 20.0 (hook-ul COGS diferă).

**Pe 20.0:** hook-ul COGS este pe `account.move._get_cogs_lines_vals`, iar mecanismul notelor de
stoc trebuie reverificat pe 20.0 înainte de implementare.

Etape, în ordine:

1. **Refactor fără schimbare de comportament** — lista cu un singur posting; testele
   existente rămân verzi.
2. **Schema `dropship_via_stock`** — teste pe livrare, retur și factura furnizorului care
   stinge 408; verificare Pacioli.
3. **Retail** — doar ca modul-punte separat, dacă apare un client care cere OBYC și gestiune la
   preț de vânzare; cere un strat de valori separat (cost, adaos, TVA), nu doar `value`.

Se reia la primul client care cere livrare directă prin stoc fără ruta în 2 pași, sau odată cu
OBYC-003, care folosește același mecanism.
