# deltatech_valuation_lot — Plan de implementare

> Status: planificat (modulul nu e încă implementat). Plan agreat la 10.06.2026.

## Poziționare

Odoo 19 are valorizare nativă pe lot în `stock_account` (`product.lot_valuated`,
`stock.lot.standard_price` / `avg_cost` / `total_value`; ieșirile sunt valorizate per
`stock.move.line` la prețul lotului). Acest modul NU reconstruiește stratul logistic —
adaugă ce lipsește: **evaluarea contabilă pe lot × arie de evaluare × cont contabil**,
derivată din notele contabile și reconciliabilă cu balanța, peste suita
`deltatech_stock_valuation`.

Comercial: „cost real pe lot / identificare specifică, cu comportament FIFO" (cu removal
strategy FIFO/FEFO) — pentru clienți cu trasabilitate: alimentar, farma, șarje de producție.
Echivalentul SAP: batch valuation / Material Ledger.

## Decizie de arhitectură: sub-ledger paralel (NU split pe aml)

**Decizie (10.06.2026): nu se sparge `account.move.line` per lot** — intervenția ar fi
prea brutală (impact pe facturare, reconciliere, SAF-T/e-Factura, volum jurnale).

Arhitectura aleasă: model nou **`product.valuation.lot.line`** — câte o înregistrare per
(linie contabilă de stoc, lot), cu `quantity` și `amount`. Linia contabilă rămâne una
singură; detalierea pe lot e paralelă (pattern-ul liniilor analitice / SAP Material Ledger).

**Invariant**: suma alocărilor unei linii contabile = soldul liniei (constrâns la creare,
verificabil în raport). Evaluarea pe lot agregă sub-ledger-ul; evaluarea pe
produs/arie/cont continuă să agrege aml-ul direct — cele două se închid una în alta
prin construcție.

Avantaje: zero impact pe contabilitate (aml identice), jurnale neschimbate, sub-ledger-ul
se poate reconstrui oricând din datele logistice. Cost: un join în plus în agregările pe
lot + disciplina invariantului sumă-alocări.

## Iterații

### IT0 — Spike și decizii (~1 zi)
- Explorare `lot_valuated` nativ pe test19: de unde se citește defalcarea pe lot la
  postare — `stock.move.move_line_ids` (lot + cantitate) plus valoarea per lot calculată
  de core în `_set_value`. De confirmat că informația e disponibilă în momentul generării
  notei contabile.
- Reprezentarea „fără lot" în constrângerile de unicitate (NULL are semantici speciale la
  UNIQUE; PG15+ are `NULLS NOT DISTINCT`, altfel valoare-santinelă).
- Gate-uri: `company.valuation_lot_level` (câmp existent în `deltatech_stock_valuation`,
  până acum nefolosit) = comutator global al stratului contabil; declanșator per produs =
  `product.lot_valuated` (core).

### IT1 — Sub-ledger-ul (1–2 zile)
- `product.valuation.lot.line`: `aml_id` (ondelete cascade), `lot_id`, `quantity`,
  `amount`; indexuri pe `aml_id`, `lot_id`; unicitate (aml, lot).
- Populare la postare: hook în fluxul existent (`account.move._recompute_valuation` are
  deja momentul potrivit) — pentru produsele `lot_valuated`, defalcă valoarea liniei pe
  loturi din `stock.move.line`-urile mișcării asociate; verificare sumă = sold aml,
  diferențele de rotunjire pe alocarea cea mai mare.
- De-postare/ștergere: alocările cad prin cascade; recalcularea pe chei le regenerează.
- **Unealtă de reconstrucție**: metodă care regenerează sub-ledger-ul istoric din
  `stock.move.line` (echivalentul refresh-ului complet, pentru baze existente).

### IT2 — Dimensiunea lot în evaluare (2–3 zile, nucleul)
- `lot_id` pe `product.valuation` + `product.valuation.history`; cheile devin
  (produs, lot, arie, cont, companie); constrângerile suprascrise cu lot.
- Agregările pentru celulele cu lot citesc din **sub-ledger join aml** (pentru
  stare/dată/cont/arie); celulele fără lot rămân pe aml-ul produselor fără `lot_valuated`.
- Pasul „completare luni lipsă" (calendar CROSS JOIN) se SARE pentru rândurile cu lot
  (altfel volumul explodează); `_propagate_balances` și pașii 4/5 din refresh primesc
  lotul în PARTITION BY.
- `account.move._get_valuation_keys` extins cu loturile din sub-ledger.

### IT3 — Preț de descărcare per lot × arie (1–2 zile)
- Core dă preț per lot global pe companie; diferențiatorul acestui modul: la
  `use_valuation_area_price` + `lot_valuated`, costul ieșirii vine din `product.valuation`
  pe **lot × arie**. Fallback: lot fără evaluare → prețul core al lotului
  (`stock.lot.standard_price`).
- Verificare de consistență stoc↔contabilitate per lot (material pentru raportul din IT5).

### IT4 — Diferențe factură + landed costs (~2 zile)
- Facturile furnizor nu poartă loturi: diferențele de preț se alocă în sub-ledger
  proporțional pe loturile recepțiilor legate
  (`purchase_line_id → move_ids → move_line_ids.lot_id`); fallback pe celula fără lot.
- Landed costs alocate pe lot proporțional cu valoarea recepției — costul lotului se
  ajustează retroactiv (mai corect decât FIFO clasic).
- Doar alocările se schimbă — nota contabilă rămâne neatinsă.

### IT5 — UI + raport + documentație (~1 zi)
- Lot în vederile `product.valuation` (list/form, filtre, group by).
- În `deltatech_valuation_report`, al doilea nivel de verificare: per cont, „sold aml cu
  produs" vs. „total sub-ledger pe loturi" — diferența = alocări lipsă/incomplete, cu
  drill-down.
- DESCRIPTION/USAGE/CONFIGURE, fișă consultant, banner Apps Store.

### IT6 — Validare end-to-end (~1 zi)
- Scenariul-etalon FIFO: recepție L1 100 buc@10, L2 100 buc@12, livrare 150 buc cu
  removal FIFO → cost 1.600 (100×10 + 50×12).
- Storno pe lot; ajustare valorică pe lot; retur.
- Performanță la reconstrucția sub-ledger-ului pe volume; validare pe dump de client cu
  loturi reale.

## Riscuri asumate (de documentat în DESCRIPTION)

- Același număr de lot re-recepționat la alt preț → medie în interiorul lotului; de aceea
  metoda se prezintă ca „identificare specifică", nu „FIFO pur".
- Produsele fără tracking rămân pe CMP (celula fără lot) — limitarea e per produs.
- Compatibilitate `l10n_ro_stock_cmp_periodic`: corecțiile valorice lunare merg pe celula
  fără lot (sau alocate proporțional — de decis în IT4).

## Estimare

~8–12 zile dezvoltare, livrabil incremental: IT1+IT2 = nucleul funcțional.

## Dependențe (deja rezolvate în deltatech_stock_valuation, commit b80172f)

- formula unică de clasificare a cantităților (helper `_get_quantity_in_out_sql`)
- propagarea soldurilor prin window function (`_propagate_balances`)
- recalcularea la de-postare/schimbare dată pe chei (`_recompute_valuation_keys`)
- constrângerile `models.Constraint` (O19) + migrarea de dedup
