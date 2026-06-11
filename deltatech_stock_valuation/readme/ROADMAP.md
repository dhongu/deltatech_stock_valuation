# Roadmap

## Evaluare la nivel de depozit (warehouse) — planificat, înaintea `deltatech_valuation_lot`

Infrastructura SQL e deja multi-arie (agregările și propagarea grupează pe
`valuation_area_id`); hardcodarea pe „companie" e în setup (`set_stock_valuation_at_company_level`),
în filtrele de arie unică din refresh și în asignarea liniilor NULL către aria companiei.

Livrabile, în ordine:

1. **Script setup**: creează `valuation.area` per depozit, leagă
   `warehouse.valuation_area_id`, marchează conturile de evaluare.
2. **Script backfill aml**: asignează `valuation_area_id` pe liniile contabile istorice —
   (a) note de stoc: prin `stock_move.account_move_id` → depozitul din locația mișcării;
   (b) facturi: prin `purchase_line_id`/`sale_line_ids` → `move_ids` → depozit;
   (c) restul: raport de linii nealocabile (număr + valoare) cu alegere explicită
   a consultantului. Raport de acoperire per cale.
3. **Refresh generalizat**: pașii 1–6 fără filtrul de arie unică / per-arie;
   invariant verificabil: suma evaluărilor pe arii = evaluarea pe companie.
4. **Transferuri inter-depozite** (dezvoltare separată, condiție de producție pentru
   clienții cu mișcări frecvente între depozite): `_get_valuation_area` blochează azi
   mișcările interne cu arii diferite; transferul inter-arii trebuie modelat ca două
   evenimente (ieșire din aria A + intrare în aria B) prin tranzit — cheile OBYC
   `internal_transfer_out/in` există deja ca enum, fluxul nu e implementat.

Estimare: 1–3 ≈ 2–3 zile (backfill-ul e grosul); 4 ≈ încă 2–3 zile.
Scriptul de backfill e util și de sine stătător la migrări.
