# Fișa consultant: OBYC - Rutarea clasei 6 la costuri adiționale

## 1. Scop business

Costul de achiziție (transport, taxe) adăugat la o recepție se capitalizează în stoc: Dr 371 Mărfuri.
Contul de stoc vine din regula OBYC **Costuri Adiționale Stoc** (`landed_cost`), nu de pe locație.
Dacă linia de cost are un cont de cheltuieli (clasa 6), nota standard este Dr 371 / Cr 6xx. Modulul
permite, pe companie, ca acest credit să treacă printr-un cont intermediar tehnic, pentru exporturi
(de exemplu SAGA) care cer note echilibrate pe perechi.

## 2. Bază legală

OMFP 1802/2014, cap. 1 sec. 1.2 pct. 6: cheltuielile de transport direct atribuibile achiziției intră
în costul de achiziție. Verificat cu Pacioli (11.11.2026): efectul net Dr 371 / Cr 6xx și cel prin
contul intermediar este identic; contul intermediar este o soluție tehnică, nu are un cont
OMFP consacrat, iar soldul lui trebuie să fie zero la fiecare operațiune.

## 3. Configurare

1. *Inventar → Configurare → Setări*, blocul **Evaluare**: **Metoda pentru creditul clasei 6**
   = *Prin cont intermediar* și **Cont intermediar** (cont tehnic definit de politica contabilă a
   firmei; nu se folosește 482 doar pentru că e disponibil).
2. Regula OBYC `Costuri Adiționale Stoc` cu **Contul de evaluare** completat.
3. Produsul de transport cu contul de cheltuială al liniei de cost (408 dacă nota trebuie să stingă
   un 408; vezi fișa `deltatech_obyc`, Pasul 10).

## 4. Flux de utilizare

*Inventar → Operații → Ajustări → Costuri adiționale*: document pe o recepție, linie „Transport” de
50 lei cu cont 624, **Calculează**, **Validează**. Același document se poate crea din factura de
furnizor (butonul de costuri adiționale): recepțiile comenzii de achiziție neacoperite de alt cost
și contul fiecărei linii se iau din factură.

## 5. Note generate (10 buc., 50 lei)

| Metodă | Debit | Credit | Sumă |
|---|---|---|---|
| Standard | 371 | 624 | 50,00 |
| Prin cont intermediar | 371 | intermediar | 50,00 |
| | intermediar | 624 | 50,00 |

Nu se rutează: clasa 609, conturile din afara clasei 6, debitul unui cost negativ.
Partea de marfă deja livrată nu se capitalizează (Odoo capitalizează doar cantitatea rămasă în stoc);
diferența se regularizează manual pe 607.

## 6. Verificări

Soldul contului intermediar trebuie să fie 0; valoarea recepției crește cu 50 lei; nota e pe
jurnalul ales în documentul de costuri adiționale.
