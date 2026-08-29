# Ce e nou în 19.0 — Determinarea conturilor (OBYC)

## Funcționalități noi
- **Jurnal contabil per arie de evaluare.** Nota de stoc a unei mișcări dintr-o arie cu jurnal propriu ajunge pe jurnalul acelei arii, nu pe jurnalul unic folosit implicit de Odoo — util când depozitele sau liniile de business se închid separat.
- **Storno la retururi.** Retururile se înregistrează prin stornarea notei inițiale, nu ca o notă nouă în sens invers, ceea ce păstrează rulajele conturilor curate.
- **Determinarea conturilor acoperă și costurile suplimentare de achiziție (landed cost).**

## Îmbunătățiri
- **Valorizarea dropship nu afectează costul mediu al stocului real** — confirmat prin teste pentru produsele ținute simultan pe stoc propriu și în dropship.
