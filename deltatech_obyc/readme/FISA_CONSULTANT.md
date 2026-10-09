# Fișă Modul: Determinarea conturilor de stoc (OBYC)

**Modul:** `deltatech_obyc`
**Utilizator principal:** Contabil (gestiune, venituri/cheltuieli), consultant de implementare, administrator Odoo
**Prioritate:** 🔴 Ridicată (schimbă conturile tuturor notelor de stoc ale produselor cu clasă de evaluare și momentul în care se înregistrează costul mărfii vândute)

---

## 1. Scop business

Modulul aduce în Odoo un mecanism de tip **OBYC** (determinarea automată a conturilor, după
modelul SAP): conturile notelor de stoc nu mai vin din categoria produsului, ci dintr-o
**matrice de reguli** stabilită de contabil. O regulă se alege după combinația:

- **cheie de tranzacție** (recepție, livrare, retur, transfer, inventar, producție, cost de achiziție, venit);
- **clasă de evaluare** a produsului (marfă, materie primă, produs finit, ambalaj etc.);
- **arie de evaluare** (companie, depozit sau locație, din modulul `deltatech_valuation_area`);
- **modificator de cont** (opțional, de pe tipul de operațiune sau de pe jurnal);
- **companie**.

Astfel, aceeași operațiune (de exemplu o livrare) poate merge pe conturi diferite pentru mărfuri
și pentru produse finite, sau pentru gestiuni diferite, fără categorii de produs duplicate.

**Decizie de model, diferită de Odoo 19 standard:** pentru produsele cu clasă de evaluare,
**costul mărfii vândute se înregistrează la livrare**, pe nota mișcării de stoc (cheia
**Livrare stoc**, de exemplu Dr 607 / Cr 371 la mărfuri, Dr 711 / Cr 345 la produse finite).
**Factura de vânzare conține doar venitul și TVA** (Dr 4111 / Cr 707 + 4427), fără linii de cost.
Odoo 19 standard, în evaluarea în timp real, înregistrează costul la postarea facturii; cu OBYC
acest lucru nu se mai întâmplă, ca să nu se dubleze costul. Produsele fără clasă de evaluare
rămân pe comportamentul standard Odoo.

**Nu este suportată:** evidența gestiunilor la preț cu amănuntul (371 cu adaos comercial pe 378 și
TVA neexigibilă pe 4428). Modulul înregistrează stocul la cost; adaosul și TVA-ul din prețul cu
amănuntul nu se calculează. Contul 378 nu se folosește drept cont de evaluare.

## 2. Bază legală și context

- **OMFP 1802/2014, pct. 95, 283, 290 și 440–441** — bunurile se scot din gestiune la transferul
  controlului către client, care, de regulă, coincide cu livrarea, nu cu facturarea. Pe această
  bază costul mărfii vândute se înregistrează la livrare. **Pct. 283 alin. (2)** enumeră
  excepțiile (consignație, stocuri la dispoziția clientului etc.), tratate la OBYC-003.
- **OMFP 1802/2014, pct. 53 alin. (2)–(3) și pct. 310 alin. (3)** — veniturile și cheltuielile
  aceleiași tranzacții se recunosc simultan; creanțele pentru care până la finele lunii nu s-a
  întocmit factura se înregistrează pe **418 „Clienți - facturi de întocmit"**, pe baza
  documentelor de livrare (OBYC-002).
- **OMFP 1802/2014, pct. 69** — stornarea se face fie cu semnul minus („în roșu"), fie prin
  înregistrarea inversă („în negru"), după politica contabilă. La companiile cu țara fiscală
  România, Odoo activează **Contabilitate storno** implicit; variantele „fără storno" din fișă
  apar doar dacă bifa este scoasă.
- **Codul fiscal, art. 281 și art. 282** — faptul generator al TVA este livrarea bunurilor
  (art. 281 alin. (1); excepțiile de la alin. (2)–(4) — consignație, bunuri trimise spre probă,
  stocuri la dispoziția clientului — sunt tratate la OBYC-003), iar TVA devine exigibilă la data
  livrării (art. 282 alin. (1)); factura emisă înainte
  de livrare face TVA exigibilă la emitere (art. 282 alin. (2) lit. a)); la TVA la încasare
  exigibilitatea se amână la încasare (art. 282 alin. (3)).
- Cazurile pe care modelul „cost la livrare" **nu** le acoperă încă (livrat nefacturat la sfârșit
  de lună, consignație, factură înainte de livrare) sunt descrise la secțiunea 9 și în
  `readme/bugs.md`, cu procedura manuală.

## 3. Utilizatori și roluri

- **Contabil** — definește clasele de evaluare, modificatorii de cont și matricea de reguli;
  verifică notele generate și face notele manuale de la secțiunea 9.
- **Gestionar / operator depozit** — validează recepții, livrări, retururi; nu configurează nimic,
  dar notele se generează la validarea documentelor lui.
- **Operator facturare** — emite facturile de vânzare; vede că factura nu mai conține liniile de cost.

Roluri recomandate pentru testare:
- Administrator funcțional (Inventar: Administrator, Contabilitate: Contabil) — configurarea din
  secțiunea 5; câmpul **Clasă de evaluare** de pe produs e vizibil doar utilizatorilor cu drepturi
  contabile;
- Utilizator operațional (Inventar: Utilizator) — recepția, livrarea, returul;
- Contabil — verificarea notelor și a facturilor.

## 4. Conturi și date implicate

Conturi folosite în exemplele din fișă (planul de conturi RO):

| Cont | Rol în fluxul OBYC |
|---|---|
| 371 Mărfuri | cont de evaluare (stocul) pentru clasa „Marfă" |
| 301 Materii prime | cont de evaluare pentru clasa „Materie primă" |
| 345 Produse finite | cont de evaluare pentru clasa „Produs finit" |
| 408 Furnizori - facturi nesosite | contrapartida recepției și a returului la furnizor; contul liniei de produs de pe factura de furnizor |
| 607 Cheltuieli privind mărfurile | costul mărfii vândute, înregistrat la livrare |
| 601 Cheltuieli cu materiile prime | consumul în producție |
| 711 Venituri aferente costurilor stocurilor de produse | costul produselor finite livrate (în debit); obținerea produselor finite (în credit) |
| 707 Venituri din vânzarea mărfurilor | venitul de pe factura de vânzare a mărfurilor |
| 701 Venituri din vânzarea produselor finite | venitul de pe factura de vânzare a produselor finite (704 / 708 pentru servicii, respectiv activități diverse) |
| 4111 Clienți, 4427 TVA colectată | factura de vânzare |
| 401 Furnizori, 4426 TVA deductibilă | factura de furnizor (TVA din taxe, în afara OBYC) |
| 418 Clienți - facturi de întocmit, 419 Clienți - creditori | livrat nefacturat (OBYC-002), factură înainte de livrare (OBYC-004) — note manuale |

**Cum se citesc conturile unei reguli** (comportamentul din cod, important la configurare):

*Nota mișcării de stoc* (recepție, livrare, retur, transfer, inventar, producție, livrare directă):

| Cont sursă al regulii | Nota generată |
|---|---|
| completat | Dr **Cont de evaluare** / Cr **Cont sursă** (Contul destinație nu se folosește) |
| gol | Dr **Cont destinație** / Cr **Cont de evaluare** |
| toate cele trei conturi goale | nu se generează notă |

*Linia de produs de pe factură* (de la versiunea 19.0.1.0.4 a modulului):

| Document | Regula folosită | Contul liniei de produs |
|---|---|---|
| factură client, notă de credit client | **Venituri** | **Cont destinație** (707; 701 la produse finite) |
| factură de furnizor, notă de credit furnizor | **Recepție stoc de la furnizor** | **Cont sursă** (408) |

Contul se alege după tipul documentului. Dacă acel cont al regulii este gol, linia ia **Contul de
evaluare** al regulii. Pe facturi modificatorul de cont nu se folosește, deci se caută regula fără
modificator. Factura de furnizor rezultă Dr 408 + Dr 4426 = Cr 401 și stinge 408 de la recepție.

Nota de credit ia **același cont** ca factura. Cu **Contabilitate storno** (implicit la firmele RO)
se înregistrează în roșu, pe aceeași parte ca factura: Dr 4111 −V / Cr 707 −V + Cr 4427 −V la
client; Dr 408 −V + Dr 4426 −V / Cr 401 −V la furnizor. Fără storno, Odoo inversează partea
(de exemplu Dr 707 + Dr 4427 / Cr 4111).

**Aria de evaluare pe factură** se ia din livrarea sau recepția liniei de comandă (vânzare sau
achiziție); la o factură fără comandă se folosește aria companiei. Creați regulile **Venituri** și
**Recepție stoc de la furnizor** pentru fiecare arie din care se livrează sau se recepționează,
plus pentru aria companiei; altfel factura se oprește cu mesajul „Nu s-a găsit nicio regulă…".

*Costul de achiziție (landed cost)*: Dr **Cont de evaluare** al regulii **Costuri Adiționale
Stoc** / Cr contul completat pe linia de cost (**Contul liniei de cost**); Contul sursă și Contul
destinație nu se folosesc. Contul liniei de cost trebuie să fie contul pe care s-a înregistrat
factura de transport, ca acel cont să se stingă (detalii la Pasul 10).

Date minime pentru demo:
- companie românească („RO Company"), în RON, cu planul de conturi RO și evaluare în timp real;
- o arie de evaluare (aici „[MAG] Magazin central"), cu jurnal de stoc propriu;
- o clasă de evaluare („[MF] Marfă") și, opțional, un modificator de cont;
- un produs stocabil cu clasa de evaluare completată, categorie cu evaluare în timp real și cost
  mediu (costurile de achiziție cer cost mediu sau FIFO și se contabilizează doar în timp real);
  nota OBYC a mișcărilor de stoc se generează pentru orice produs cu clasă de evaluare, indiferent
  de metoda de evaluare a categoriei (vezi secțiunea 9);
- un furnizor și un client.

## 5. Configurare inițială

1. **Activați aria de evaluare pe companie:** *Inventar → Configurare → Setări*, blocul
   **Evaluare** → bifați **Folosește zonă de evaluare** și alegeți **Arie de evaluare** a companiei.
   Fără arie de evaluare activă, regulile se caută cu aria goală.
2. **Creați ariile de evaluare:** *Inventar → Configurare → Gestiunea depozitului → Zonă de evaluare*.
   Dacă notele de stoc ale unei arii trebuie să meargă pe un jurnal dedicat, completați
   **Jurnal de stoc**. Aria se poate pune și pe depozit sau pe locație (prioritate: locația
   internă, apoi depozitul, apoi compania).
3. **Definiți clasele de evaluare:** *Inventar → Configurare → Configurare determinare cont →
   Clasă de evaluare* (cod + nume, afișate ca `[COD] Nume`).
4. **Definiți modificatorii de cont (opțional):** *Inventar → Configurare → Configurare determinare
   cont → Modificatori de cont*. Se pun pe **tipul de operațiune** (câmpul **Modificator de cont**,
   lângă depozit) pentru mișcările de stoc și pe **jurnal** (câmpul **Modificator de cont**, lângă
   companie) pentru costurile de achiziție validate pe acel jurnal. Pe facturi modificatorul nu se
   folosește. Exemplu: modificatorul „[INT] Transferuri interne" pe tipul de operațiune de transfer
   intern, cu o regulă proprie.
5. **Completați clasa pe produse:** pe produs, tabul **Contabilitate**, grupul **Clasă de evaluare**.
6. **Creați matricea de reguli:** *Inventar → Configurare → Configurare determinare cont →
   Determinare cont produs*. Pentru fiecare combinație folosită (cheie, clasă, arie, modificator)
   completați conturile după convenția din secțiunea 4. Exemplu pentru **mărfuri**:

   | Cheie de tranzacție | Cont sursă | Cont destinație | Cont de evaluare | Nota rezultată |
   |---|---|---|---|---|
   | Recepție stoc de la furnizor | 408 | — | 371 | Dr 371 / Cr 408; factura de furnizor: linia pe 408 (Cont sursă) |
   | Retur la furnizor | — | 408 | 371 | Dr 408 / Cr 371 (cu storno: Dr 371 −V / Cr 408 −V) |
   | Livrare stoc | — | 607 | 371 | Dr 607 / Cr 371 |
   | Retur de la client | 607 | — | 371 | Dr 371 / Cr 607 (cu storno: Dr 607 −V / Cr 371 −V) |
   | Venituri | — | 707 | — | factura de vânzare și nota de credit: linia pe 707 (Cont destinație) |
   | Costuri Adiționale Stoc | — | — | 371 | Dr 371 / Cr contul liniei de cost |
   | Livrare directă (dropship) | 408 | — | 607 | Dr 607 / Cr 408 |
   | Retur dropshipping (client → furnizor) | 607 | — | 408 | Dr 408 / Cr 607 (cu storno: Dr 607 −V / Cr 408 −V) |
   | Transfer intern (aceeași arie) | — | — | — | fără notă (valoarea stocului nu se schimbă) |
   | Ajustare inventar plus (plusuri, inventar → gestiune) | 607 | — | 371 | Dr 371 / Cr 607 |
   | Ajustare inventar minus (lipsuri, gestiune → inventar) | — | 607 | 371 | Dr 607 / Cr 371 |

   Regulile **Livrare directă**, **Retur dropshipping** și **Recepție stoc de la furnizor**
   trebuie să folosească **același cont 408**: factura furnizorului pentru o livrare directă își ia
   contul din regula **Recepție stoc de la furnizor** (Cont sursă) și trebuie să stingă 408 din nota
   livrării directe.

   Exemplu pentru **produse finite** (clasa „Produs finit", cont de evaluare 345):

   | Cheie de tranzacție | Cont sursă | Cont destinație | Cont de evaluare | Nota rezultată |
   |---|---|---|---|---|
   | Recepție producție (producție → gestiune) | 711 | — | 345 | Dr 345 / Cr 711 (obținerea produselor finite) |
   | Livrare stoc | — | 711 | 345 | Dr 711 / Cr 345 |
   | Retur de la client | 711 | — | 345 | Dr 345 / Cr 711 (cu storno: Dr 711 −V / Cr 345 −V) |
   | Venituri | — | 701 | — | factura: linia pe 701 (704 / 708 pentru alte venituri) |
   | Ajustare inventar plus (plusuri) | 711 | — | 345 | Dr 345 / Cr 711 |
   | Ajustare inventar minus (lipsuri) | — | 711 | 345 | Dr 711 / Cr 345 |

   Exemplu pentru **materii prime** (clasa „Materie primă", cont de evaluare 301):

   | Cheie de tranzacție | Cont sursă | Cont destinație | Cont de evaluare | Nota rezultată |
   |---|---|---|---|---|
   | Recepție stoc de la furnizor | 408 | — | 301 | Dr 301 / Cr 408 |
   | Consum producție (gestiune → producție) | — | 601 | 301 | Dr 601 / Cr 301 |
   | Ajustare inventar plus (plusuri) | 601 | — | 301 | Dr 301 / Cr 601 |
   | Ajustare inventar minus (lipsuri) | — | 601 | 301 | Dr 601 / Cr 301 |

   Plusul la inventar (locația de inventar → gestiune) folosește cheia **Ajustare inventar plus**,
   lipsa (gestiune → locația de inventar) cheia **Ajustare inventar minus**; până la versiunea
   19.0.1.0.6 cheile erau inversate (OBYC-005, secțiunea 9). Plusurile de
   inventar se înregistrează pe seama contului de cheltuială (607 la mărfuri, 601 la materii prime)
   sau a contului 711 la produse finite, după funcțiunea contului de stoc din OMFP 1802/2014 (la 371:
   „constatate plus la inventar … (607, 758)", unde 758 privește bunurile primite cu titlu gratuit).
   Plusurile se evaluează la valoarea justă (pct. 75 alin. (1) lit. d)); verificați costul
   produsului înainte de ajustare. Imputarea și TVA-ul lipsurilor se fac manual (secțiunea 6,
   „Note de monografie").

   **Transfer între arii prin tranzit** (gestiuni diferite, de exemplu 371.01 Magazin central și
   371.02 Depozit, cu 371.09 Mărfuri în tranzit între gestiuni ca analitic de trecere):

   | Cheie de tranzacție | Arie | Cont sursă | Cont destinație | Cont de evaluare | Nota rezultată |
   |---|---|---|---|---|---|
   | Ieșire transfer intern (gestiune → tranzit) | Magazin central | — | 371.09 | 371.01 | Dr 371.09 / Cr 371.01 |
   | Intrare transfer intern (tranzit → gestiune) | Depozit | 371.09 | — | 371.02 | Dr 371.02 / Cr 371.09 |

   O notă Dr 371 / Cr 371 (același cont sintetic) este legitimă aici: analiticele diferă, iar nota
   de ieșire poartă aria gestiunii care predă, cea de intrare aria gestiunii care primește. Transferul
   direct între locații interne din arii diferite nu este permis (secțiunea 9). **De verificat pe o
   mișcare de test** că notele de tranzit au valoare: în Odoo 19 locația de tranzit a companiei este
   evaluată, iar mișcarea gestiune → tranzit nu este nici intrare, nici ieșire, deci valoarea ei
   poate rămâne 0; fluxul nu are încă test automat.
7. **Storno:** *Facturare (sau Contabilitate) → Configurare → Setări*, blocul **Contabilitate
   storno** → verificați că **Contabilitate storno** este bifat (la firmele RO este bifat implicit).

Regula se caută **exact** pe combinația cheie + clasă + arie + modificator + companie: o regulă cu
modificator gol nu acoperă un tip de operațiune care are modificator. Dacă toate cele trei conturi
ale unei reguli sunt goale, mișcarea nu generează notă contabilă.

## 6. Flux de utilizare

### Pasul 1 — Matricea de reguli OBYC

*Inventar → Configurare → Configurare determinare cont → Determinare cont produs.*

Lista arată, pe fiecare rând, o regulă: cheia de tranzacție, modificatorul, clasa, aria și cele
trei conturi. Verificați că pentru fiecare operațiune pe care o veți face există un rând cu clasa
și aria produsului, iar conturile respectă convenția din secțiunea 4. În captură: la **Livrare
stoc** Contul sursă e gol, Contul destinație 607, Contul de evaluare 371; la **Venituri** doar
Contul destinație (707); la **Recepție stoc de la furnizor** Contul sursă 408 și Contul de
evaluare 371.

![Matricea OBYC](screenshots/01_account_determination_matrix.png)

### Pasul 2 — Formularul unei reguli

Deschideți din listă regula **Livrare stoc**. Grupul **Condiții** conține aria de evaluare, cheia
de tranzacție, clasa de evaluare, modificatorul de cont (aici gol) și compania; grupul **Conturi**
conține cele trei conturi (marcate ①②③):

1. **Găsiți pe ecran:** ① Cont sursă — gol; ② Cont destinație — 607000; ③ Cont de evaluare — 371000.
2. **Verificați:** fiindcă Contul sursă e gol, livrarea va genera Dr 607 / Cr 371 (convenția din
   secțiunea 4). Regula nu are modificator, deci se aplică doar tipurilor de operațiune fără
   modificator de cont.

![Formular regulă OBYC](screenshots/02_account_determination_form.png)

### Pasul 3 — Clasele de evaluare

*Inventar → Configurare → Configurare determinare cont → Clasă de evaluare* (titlul paginii:
„Clasă de evaluare produs"). Lista claselor de evaluare, cu codul și numele în coloane separate (aici MF, Marfă). În câmpurile
de selecție (produs, regulă) clasa apare ca `[COD] Nume`, de exemplu „[MF] Marfă".

![Clase de evaluare](screenshots/03_valuation_class_list.png)

### Pasul 4 — Aria de evaluare cu jurnal de stoc propriu

*Inventar → Configurare → Gestiunea depozitului → Zonă de evaluare* → deschideți aria.
Câmpul **Jurnal de stoc** (marcat) este completat cu „Stoc - Magazin central": notele OBYC ale
mișcărilor din această arie se postează pe acest jurnal, nu pe jurnalul de stoc al companiei.

![Arie de evaluare cu jurnal](screenshots/04_valuation_area_journal.png)

### Pasul 5 — Produsul cu clasă de evaluare

*Inventar → Produse → Produse* → deschideți produsul → tabul **Contabilitate**.
Câmpul **Clasă de evaluare** (marcat) este „[MF] Marfă". Fără clasă, produsul urmează fluxul
standard Odoo (conturile din categorie). Conturile de venituri/cheltuieli de pe produs nu sunt
folosite pentru produsele cu clasă de evaluare: contează doar matricea.

![Produs cu clasă de evaluare](screenshots/05_product_valuation_class.png)

### Pasul 6 — Recepția de la furnizor și nota ei

*Inventar → Operații → Transferuri → Recepții* → **Validează** recepția de 10 buc. În baza demo
recepția e făcută fără comandă de achiziție, deci se valorizează la costul produsului (100 lei/buc.);
dintr-o comandă de achiziție valoarea vine din prețul comenzii.
Nota se găsește în *Facturare → Contabilitate → Note contabile* (aplicația se numește
*Contabilitate* când e instalată contabilitatea completă), după referința recepției; tabul
**Elemente jurnal**:

1. **Găsiți pe ecran:** jurnalul „Stoc - Magazin central" (jurnalul ariei), referința recepției,
   liniile 371000 Mărfuri (debit) și 408100 Furnizori - facturi nesosite (credit).
2. **Verificați:** Dr 371 = Cr 408 = 1.000,00 lei; conturile sunt cele din regula **Recepție stoc
   de la furnizor**, nu cele din categoria produsului; jurnalul este al ariei.

![Notă OBYC recepție](screenshots/06_stock_move_obyc_entry.png)

### Pasul 6b — Factura de furnizor: linia de produs pe 408

*Facturare → Furnizori → Facturi* → **Nou(ă)** → furnizor „Furnizor Demo SRL", produsul recepționat,
10 buc. × 100 lei, TVA 21% → **Confirmă** → tabul **Elemente jurnal**.

1. **Găsiți pe ecran:** liniile 408100 Furnizori - facturi nesosite (debit 1.000,00 lei), 442600
   TVA deductibilă (debit 210,00 lei) și 401100 Furnizori (credit 1.210,00 lei).
2. **Verificați:** linia de produs este pe 408, Contul sursă al regulii **Recepție stoc de la
   furnizor**, **nu** pe 371: stocul nu se mai debitează a doua oară (OBYC-001). După factură, 408
   pentru această recepție are sold zero, dacă prețul și cursul facturii sunt cele de la recepție;
   altfel vezi „Note de monografie".

![Factură de furnizor pe 408](screenshots/11_vendor_bill_408.png)

### Pasul 7 — Returul la furnizor cu storno (înregistrare în roșu)

Cu **Contabilitate storno** activ pe companie: din recepție, butonul **Retur** → 5 buc. →
**Validează** returul, apoi deschideți nota lui din *Note contabile*. Returul la furnizor se face
pe tipul de operațiune Livrări (referință MAG/OUT/…), ca și livrarea din Pasul 8.

1. **Găsiți pe ecran:** aceleași conturi ca la recepție (371 pe debit, 408 pe credit), cu sume
   negative.
2. **Verificați:** Dr 371 = −500,00 lei, Cr 408 = −500,00 lei — nota apare „în roșu", nu ca o
   notă „neagră" inversată (Dr 408 / Cr 371). Fără storno, returul ar fi Dr 408 / Cr 371 cu sume
   pozitive.

![Storno retur](screenshots/07_storno_return.png)

### Pasul 8 — Livrarea la client: costul mărfii vândute

*Inventar → Operații → Transferuri → Livrări* → **Validează** livrarea (2 buc.), apoi deschideți
nota din *Note contabile*, după referința livrării.

1. **Găsiți pe ecran:** jurnalul ariei, referința livrării, liniile 607000 Cheltuieli privind
   mărfurile (debit) și 371000 Mărfuri (credit).
2. **Verificați:** Dr 607 = Cr 371 = 200,00 lei (2 buc. × costul mediu de 100 lei). **Costul
   mărfii vândute se înregistrează acum, la livrare**, din regula **Livrare stoc** — nu va mai
   apărea pe factură.

![Notă livrare: cost la livrare](screenshots/08_delivery_cogs_entry.png)

### Pasul 9 — Factura de vânzare: doar venit și TVA

*Facturare → Clienți → Facturi* → **Nou(ă)** → client „Client Demo SRL", produsul livrat,
2 buc. × 150 lei, TVA 21% → **Confirmă** → tabul **Elemente jurnal**.

1. **Găsiți pe ecran:** liniile 707000 Venituri din vânzarea mărfurilor (credit 300,00 lei),
   442700 TVA colectată (credit 63,00 lei) și 411100 Clienți (debit 363,00 lei).
2. **Verificați:** **nu există** linii 607/371 pe factură — costul a fost deja înregistrat la
   livrare (Pasul 8), deci nu se dublează. Venitul este pe 707, Contul destinație al regulii
   **Venituri**. Emiteți factura în luna livrării; altfel aplicați procedura OBYC-002 (secțiunea 9).

![Factură de vânzare fără linii de cost](screenshots/09_sale_invoice_no_cogs.png)

### Pasul 10 — Costul de achiziție (landed cost) pe o recepție

*Inventar → Operații → Ajustări → Costuri adiționale* → document nou pe o recepție de 10 buc.,
**Jurnal**: „Stoc - Magazin central", linie „Transport marfă" de 50 lei cu contul 408100,
împărțire după cantitate → **Calculează** → **Validează**, apoi deschideți nota documentului.
Nota se postează pe jurnalul ales în document, nu pe jurnalul ariei.

1. **Găsiți pe ecran:** liniile 371000 Mărfuri (debit) și contul liniei de cost (aici 408100,
   credit).
2. **Verificați:** Dr 371 = Cr 408 = 50,00 lei; contul de stoc vine din regula **Costuri Adiționale
   Stoc** (Contul de evaluare), contul de credit e cel completat pe linia de cost; valoarea
   recepției crește cu 50 lei.

![Notă cost de achiziție](screenshots/10_landed_cost_entry.png)

**Contul liniei de cost** trebuie să fie contul pe care se înregistrează factura transportatorului,
ca acesta să se stingă. În exemplu linia are 408, deci factura de transport se înregistrează
Dr 408 + Dr 4426 = Cr 401, iar nota costului de achiziție stinge 408 (Dr 371 / Cr 408).

Dacă documentul **Costuri adiționale** se creează din factura de furnizor (butonul de creare a
costurilor adiționale de pe factură), Odoo pune pe linia de cost **contul de cheltuială al
produsului de transport**. Configurați acest cont
la **408** (pe produsul „Transport marfă" sau pe categoria lui), nu la un cont de cheltuieli
(624): altfel factura debitează 624, iar costul de achiziție creditează 624 în cursul anului, ceea
ce contrazice funcțiunea contului; transportul aferent achiziției face parte din costul de
achiziție al mărfii (OMFP 1802/2014, pct. 8 subpct. 6).

În demo toată marfa recepției este încă în stoc. Dacă o parte fusese deja livrată, Odoo
capitalizează pe 371 doar partea aferentă cantității rămase; partea livrată rămâne în sold pe
contul liniei de cost (408) și se trece manual pe 607 (711 la produse finite), cu notă contabilă
Dr 607 / Cr 408.

### Note de monografie și raportare

Note generate în baza demo (marfă, cost mediu 100 lei/buc.):

| Operațiune | Cheie de tranzacție | Debit | Credit | Sumă |
|---|---|---|---|---|
| Recepție de la furnizor (10 buc.) | Recepție stoc de la furnizor | 371 | 408 | 1.000,00 |
| Factura de furnizor (10 × 100 lei + TVA 21%) | Recepție stoc de la furnizor (Cont sursă) | 408 / 4426 | 401 | 1.210,00 = 1.000,00 + 210,00 |
| Retur la furnizor (5 buc.), **fără** storno | Retur la furnizor | 408 | 371 | 500,00 |
| Retur la furnizor (5 buc.), **cu** storno | Retur la furnizor | 371 | 408 | −500,00 |
| Livrare la client (2 buc.) | Livrare stoc | 607 | 371 | 200,00 |
| Factura de vânzare (2 × 150 lei + TVA 21%) | Venituri (Cont destinație) | 4111 | 707 / 4427 | 363,00 = 300,00 + 63,00 |
| Retur de la client, **cu** storno (implicit la firmele RO) | Retur de la client | 607 | 371 | −V |
| Retur de la client, **fără** storno | Retur de la client | 371 | 607 | V |
| Cost de achiziție (transport) | Costuri Adiționale Stoc | 371 | contul liniei de cost (aici 408) | 50,00 |
| Livrare directă furnizor → client | Livrare directă | 607 | 408 | valoarea mișcării |
| Retur livrare directă, **cu** storno | Retur dropshipping | 607 | 408 | −V |
| Livrare produse finite | Livrare stoc (clasa produs finit) | 711 | 345 | V |
| Obținere produse finite din producție | Recepție producție | 345 | 711 | V |
| Consum de materii prime | Consum producție | 601 | 301 | V |

**Inventar: plusuri și lipsuri.** OBYC face doar nota de stoc (tabelele din secțiunea 5):
plusuri la marfă Dr 371 / Cr 607, la materii prime Dr 301 / Cr 601, la produse finite Dr 345 /
Cr 711; lipsuri Dr 607 / Cr 371, Dr 601 / Cr 301, respectiv Dr 711 / Cr 345. Restul se face
**manual**, cu notă contabilă:
- **imputarea** lipsei: Dr 4282 (personal) sau Dr 461 (terți) / Cr 7581, **fără TVA colectată**:
  sumele imputate nu sunt contravaloarea unor operațiuni în sfera TVA (HG 1/2016, Titlul VII,
  pct. 78 alin. (6) lit. a));
- **TVA aferentă lipsurilor nejustificate**: deducerea se ajustează (Codul fiscal, art. 304
  alin. (1) lit. c)); nu se ajustează la bunurile distruse, pierdute sau furate, dovedite conform
  art. 304 alin. (2) lit. a). Nota uzuală este Dr 635 / Cr 4426 (sau Cr 4427); rândul din D300 și contul de
  credit se stabilesc **cu contabilul**;
- **impozitul pe profit**: lipsurile neimputabile și TVA-ul aferent lor sunt nedeductibile (Codul
  fiscal, art. 25 alin. (4) lit. c)), cu excepțiile prevăzute acolo.

**Diferențe de preț și de curs între recepție și factura de furnizor.** Recepția se înregistrează
la prețul comenzii, factura de furnizor la prețul și cursul ei. OBYC nu generează note de
diferență de preț (cheile **Diferență de preț** nu sunt folosite), deci diferența rămâne în sold
pe 408. Regularizarea se face **manual**:
- diferența de preț: Dr/Cr 371 față de 408 pentru partea încă în stoc și Dr/Cr 607 (711 la
  produse finite) față de 408 pentru partea deja vândută;
- diferența de curs pe 408 (achiziții în valută): Dr 665 / Cr 408 (pierdere) sau Dr 408 / Cr 765
  (câștig).

Atenție: la postarea facturii de furnizor dintr-o comandă de achiziție, Odoo 19 recalculează
valoarea mișcării de recepție (și costul mediu) după prețul facturii, fără notă contabilă. Până la
nota de regularizare, valoarea stocului din Odoo diferă de soldul 371 cu diferența de preț a
stocului rămas; de verificat la controlul lunar.

Observații:
- **Livrarea directă (dropship)** generează notă cu valoare: mișcarea furnizor → client se
  valorizează (înainte nota ieșea cu 0). Livrarea directă nu modifică stocul propriu și nici
  costul mediu al produsului. Nota directă Dr 607 / Cr 408, fără trecere prin 371, este o
  simplificare acceptabilă: marfa nu intră în gestiunea proprie. Sunt două moduri de a
  înregistra livrarea directă, iar alegerea se face din configurare:
  - **(a) Direct, fără stoc** — regula **Livrare directă** (Dr 607 / Cr 408), o singură notă pe
    mișcarea furnizor → client. Este varianta implicită. Economic e corectă; formal, contrapartida
    lui 607 nu este cea din funcțiunea contului când stocurile se țin în inventar permanent.
  - **(b) Prin gestiune, în 2 pași** — se configurează ruta cu recepție în gestiune (furnizor →
    gestiune, regula **Recepție stoc de la furnizor**: Dr 371 / Cr 408) urmată de livrare
    (gestiune → client, regula **Livrare stoc**: Dr 607 / Cr 371). Soldul 371 rămâne zero,
    iar marfa apare în fișa de magazie și în rapoartele de stoc. Este varianta care respectă
    funcțiunile conturilor 371, 408 și 607 (OMFP 1802/2014, pct. 290); marfa trece fizic prin
    gestiune, deci nu mai este livrare directă propriu-zisă.
  - **Contul 357 este nerecomandat** la livrarea directă: este pentru marfa proprie aflată la un
    terț (consignație, custodie), cu marfa trecută întâi prin 371 (Dr 357 / Cr 371), nu pentru
    marfa livrată direct de furnizor. Corespondența Dr 357 / Cr 401 sau Dr 357 / Cr 408 nu este
    prevăzută în funcțiunea conturilor din OMFP 1802/2014 (357 se alimentează doar din 371);
    efectul fiscal este nul (costul ajunge oricum în 607), dar la control este o corespondență
    neprevăzută. Unele articole de specialitate propun 357 în locul lui 371; fără temei în
    OMFP, nu îl folosiți decât dacă marfa rămâne efectiv la furnizor, în custodie (contract de
    custodie, transferul riscurilor, proces-verbal de predare-primire), și atunci pe traseul
    371 → 357 → 607. Dacă regula este totuși configurată cu 357 pe contul de evaluare,
    documentați alegerea împreună cu contabilul clientului.
  - **Factura furnizorului nu determină data livrării** și nici a transferului dreptului de a
    dispune de bunuri (art. 281 alin. (6) Cod fiscal); poate însă muta **exigibilitatea TVA**,
    dacă se emite înaintea livrării (art. 282 alin. (2) lit. a)).
  - **Limită:** o mișcare generează o singură notă cu două linii, deci Dr 371 / Cr 408 urmat de
    Dr 607 / Cr 371 pe o **singură** mișcare furnizor → client nu se poate obține din
    configurare (vezi `readme/ROADMAP.md`).
  - Dacă factura furnizorului vine **înainte** de livrarea la client, tratați-o ca avans
    (Dr 409 / Cr 401), nu ca stoc; marfa pe drum la sfârșitul lunii, cu riscurile transferate,
    se ține în 327. Cele două cazuri se înregistrează manual.
- **Liniile notelor de stoc** poartă produsul, **cantitatea semnată** (pozitivă pe debit,
  negativă pe credit; la storno semnul se inversează odată cu suma) și unitatea de măsură —
  necesare evaluării cantitativ-valorice din `deltatech_stock_valuation`. La inversarea unei note
  de stoc fără storno (butonul **Intrare inversă**), cantitatea se inversează odată cu partea
  (`deltatech_valuation_area` 19.0.1.0.3), deci evaluarea ajunge la zero, nu dublează cantitatea.
- **Storno** se aplică doar mișcărilor de retur (cele care au o mișcare de origine returnată):
  nota „neagră" a regulii de retur devine tranzacția inițială cu sume negative. De aceea regula
  de retur trebuie să fie oglinda regulii operațiunii inițiale.
- **Retur de la client la produse finite:** pe lângă nota de stoc (Dr 711 −V / Cr 345 −V cu
  storno), se emite nota de credit către client, care reduce baza de impozitare (Codul fiscal,
  art. 287 lit. b)); linia ei ia contul 701 din regula **Venituri**.
- **TVA aferentă facturilor nesosite** nu este tratată de OBYC. Dacă firma înregistrează manual
  Dr 4428 / Cr 408 la recepție, la sosirea facturii trebuie înregistrat tot manual Dr 408 /
  Cr 4428, pentru că Odoo pune TVA-ul facturii direct pe 4426.

## 7. Legături cu alte module / declarații

| Modul | Rol |
|---|---|
| `deltatech_valuation_area` | ariile de evaluare (companie/depozit/locație) și jurnalul de stoc pe arie — dependență obligatorie |
| `stock_account` | evaluarea în timp real; OBYC înlocuiește conturile notelor de stoc pentru produsele cu clasă |
| `stock_landed_costs` | costurile de achiziție; OBYC dă contul de stoc prin cheia **Costuri Adiționale Stoc** |
| `purchase_stock` | recepțiile din comenzi de achiziție |
| `deltatech_stock_valuation` | (opțional) evaluarea cantitativ-valorică pe arie, construită din liniile notelor OBYC |
| `account` (storno) | înregistrarea în roșu a retururilor |
| Jurnalul de TVA / D300 (`l10n_ro`) | D300 se calculează din grilele fiscale (tag-urile de taxă) ale liniilor de factură, nu din soldul 4427; OBYC nu schimbă taxele, iar o notă contabilă manuală pe 4427 nu apare în D300 |

**Ce e automat:**
- alegerea regulii și a conturilor la fiecare mișcare de stoc a unui produs cu clasă de evaluare;
- contul liniei de produs pe facturi și note de credit (Venituri → Cont destinație, Recepție →
  Cont sursă);
- jurnalul notelor de stoc (jurnalul ariei, dacă e completat); costul de achiziție se postează pe
  jurnalul ales în documentul Costuri adiționale;
- costul mărfii vândute la livrare și lipsa liniilor de cost pe factura de vânzare;
- inversarea în roșu a retururilor, cu storno activ;
- valorizarea mișcărilor de livrare directă.

**Ce rămâne manual:**
- întreținerea matricei de reguli (o regulă lipsă blochează validarea documentului);
- veniturile pentru livrările nefacturate la sfârșit de lună (418), consignația și facturile
  emise înainte de livrare (secțiunea 9);
- alegerea contului de pe linia de cost la costurile de achiziție și tratarea părții deja livrate;
- regularizarea diferențelor de preț și de curs rămase pe 408;
- imputarea lipsurilor, ajustarea TVA și impozitul pe profit la inventar;
- corecția facturilor postate înainte de versiunea 19.0.1.0.4 (secțiunea 9, OBYC-001).

## 8. Verificări pentru consultant

- [ ] produsul are **Clasă de evaluare** (tabul Contabilitate) și categorie cu evaluare în timp real
- [ ] compania are **Folosește zonă de evaluare** bifat și o arie de evaluare; aria are **Jurnal de stoc**, dacă se dorește jurnal separat
- [ ] există regulă pentru fiecare combinație cheie + clasă + arie + modificator folosită (inclusiv tipurile de operațiune cu modificator)
- [ ] conturile regulilor respectă convenția: Cont sursă completat → Dr evaluare / Cr sursă; Cont sursă gol → Dr destinație / Cr evaluare
- [ ] regula **Venituri** are 707 (701 la produse finite) în **Cont destinație**; regula **Recepție stoc de la furnizor** are 408 în **Cont sursă**
- [ ] regulile **Livrare directă**, **Retur dropshipping** și **Recepție stoc de la furnizor** folosesc același cont 408
- [ ] nota recepției: Dr 371 / Cr 408, pe jurnalul ariei
- [ ] factura de furnizor: linia de produs pe 408 (Dr 408 + 4426 / Cr 401), nu pe 371 (captura 11)
- [ ] nota livrării: Dr 607 / Cr 371 (sau Dr 711 / Cr 345 la produse finite)
- [ ] nota de stoc poartă **data validării** documentului, nu data efectivă a mișcării: validați recepțiile și livrările în luna în care au avut loc
- [ ] factura de vânzare: Dr 4111 / Cr 707 + 4427, **fără** linii 607/371; nota de credit pentru retur pe același 707 (reducerile de preț acordate după facturare se înregistrează pe 709, manual)
- [ ] factura cu două sau mai multe produse OBYC (clase diferite) se confirmă, fiecare linie pe contul clasei ei
- [ ] cu **Contabilitate storno** activ, nota returului are sume negative pe **aceleași conturi** ca operațiunea inițială
- [ ] costul de achiziție: Dr 371 / Cr contul liniei de cost; contul liniei de cost este contul facturii de transport (408), care se stinge; produsul de transport nu are ca cont de cheltuială 624
- [ ] costul de achiziție este pe jurnalul ales în document; recepția avea toată marfa în stoc sau partea livrată a fost tratată manual
- [ ] livrarea directă furnizor → client are notă cu valoare (nu 0) și nu modifică stocul propriu
- [ ] liniile notelor de stoc au produs, cantitate semnată (pozitivă pe debit, negativă pe credit) și unitate de măsură
- [ ] la ajustările de inventar, plusul folosește regula **Ajustare inventar plus** și lipsa regula **Ajustare inventar minus**; la bazele actualizate de la o versiune anterioară 19.0.1.0.6, regulile au fost verificate (OBYC-005); imputarea și TVA-ul lipsurilor sunt înregistrate manual
- [ ] **lunar:** soldul 371 (301, 345) = raportul de evaluare a stocului pe arie, la aceeași dată
- [ ] **lunar:** soldul 408 = recepțiile nefacturate; analitic pe furnizor / recepție, fără solduri rămase din diferențe de preț sau de curs
- [ ] **lunar:** livrările nefacturate la sfârșitul lunii au factura cu data contabilă în luna livrării sau nota pe 418 cu inversare pe 1 a lunii următoare (OBYC-002), nu pe amândouă
- [ ] regulile **Venituri** și **Recepție stoc de la furnizor** există pentru fiecare arie din care se livrează sau se recepționează și pentru aria companiei (facturile fără comandă)
- [ ] nota de credit (client sau furnizor) este pe același cont ca factura, în roșu cu storno activ

## 9. Mesaje de eroare frecvente

| Mesaj | Cauză | Remediere |
|---|---|---|
| „Nu s-a găsit nicio regulă de determinare a contului pentru cheia de tranzacție '…', modificatorul de cont '…', clasa de evaluare '…', zona de evaluare '…' și compania '…'." | nu există regulă pentru combinația exactă (adesea: tipul de operațiune are modificator, iar regula nu); numele cheii apare în engleză | butonul **Mergi la configurare** deschide lista de reguli; la **Nou(ă)** condițiile vin precompletate — adăugați conturile și salvați |
| „Cheia de tranzacție nu a putut fi determinată pentru mișcarea de la {source_usage} la {dest_usage}." | mișcare între tipuri de locații pe care modulul nu le cunoaște (de exemplu tranzit → client); acoladele rămân în text, fără tipurile de locații (defect de afișare) | refaceți fluxul prin locații interne sau cereți extinderea cheilor |
| „Zona de evaluare nu este definită" | compania folosește arii de evaluare, dar nici compania, nici depozitul, nici locația nu au arie | completați aria pe companie, depozit sau locație |
| „Locațiile sursă și destinație trebuie să aibă aceeași zonă de evaluare pentru mișcările interne." | transfer intern între locații din arii diferite | folosiți un transfer prin tranzit (chei **Ieșire / Intrare transfer intern**, exemplul din secțiunea 5) |
| „Cheia de tranzacție nu este definită. Setați-o în context." | un flux standard cere conturile unui produs cu clasă de evaluare fără să treacă prin OBYC | semnalați fluxul echipei de dezvoltare; temporar, procesați produsul fără clasă |

**Limitări cunoscute** (detaliate în `readme/bugs.md`; nu sunt funcționalități):

- **OBYC-001 — reparat în 19.0.1.0.4.** Înainte de această versiune, linia de produs de pe
  factură lua Contul de evaluare al regulii: venitul facturii de vânzare putea ajunge pe 371, iar
  factura de furnizor debita din nou 371 (în loc de 408), lăsând 408 nestins. **Facturile postate
  înainte de 19.0.1.0.4 rămân cu contul greșit**: după actualizare, comparați soldul 371 cu
  raportul de evaluare a stocului pe arie și soldul 408 cu recepțiile nefacturate, apoi corectați
  diferențele prin notă contabilă (de exemplu Dr 408 / Cr 371 pentru facturile de furnizor, Dr 371 /
  Cr 707 pentru facturile de vânzare; pentru notele de credit vechi: Dr 371 / Cr 408 la furnizor, iar
  la client, în roșu, Dr 371 −V / Cr 707 −V). Dacă regula **Venituri** fusese configurată cu 707 în toate
  cele trei conturi, se poate lăsa așa; configurarea recomandată are 707 doar în Cont destinație.
- **OBYC-002 — fără venituri de facturat (418) pentru livrat nefacturat.** Livrarea din luna M
  înregistrează costul în M, venitul apare doar la factura din M+1. TVA este exigibilă la livrare
  (Codul fiscal, art. 282 alin. (1)); art. 319 alin. (16) obligă doar la emiterea facturii până pe
  15 a lunii următoare, nu mută exigibilitatea. D300 se calculează din grilele fiscale ale
  facturilor, deci o notă manuală pe 4427 nu apare în D300. Alegeți **una** dintre variante,
  nu pe amândouă (altfel venitul se dublează în luna M):
  - **(a) preferat — factura cu data contabilă în luna M.** Emiteți factura în luna livrării sau
    până pe 15 a lunii M+1 cu **data contabilă** în luna M (dacă perioada nu este blocată). Venitul
    și TVA-ul intră în luna M prin factură, **fără** nota pe 418 și fără inversare;
  - **(b) factura cu data contabilă în luna M+1.** La sfârșitul lunii M, notă contabilă manuală
    **Dr 418 = Cr 707** (701 la produse finite), **fără TVA**, pe baza avizelor de livrare
    (OMFP 1802/2014, pct. 53 alin. (2)–(3) și pct. 310 alin. (3)); după postare, butonul
    **Intrare inversă** cu data 1 a lunii M+1 (nota inversă cu dată viitoare se postează automat
    la acea dată). Factura din M+1 se postează normal (Dr 4111 / Cr 707 + 4427): fără inversare,
    venitul s-ar dubla. TVA-ul livrării se trece **manual** în D300 al lunii M și se scade din
    D300 al lunii M+1, unde intră prin factură. În această variantă soldul 4427 din contabilitate
    diferă de D300 în luna M; alternativ, nota se face Dr 418 = Cr 707 + Cr 4428 și Dr 4428 = Cr 4427
    (funcțiunea contului 418 include TVA aferentă), tot cu inversare pe 1 a lunii M+1 — alegerea și
    închiderea TVA a lunii M se stabilesc cu contabilul;
  - **TVA la încasare** (art. 282 alin. (3)): TVA rămâne pe 4428 până la încasare, ca la orice
    factură;
  - asistentul standard de venituri angajate din Vânzări nu poate fi folosit pentru produsele cu
    clasă de evaluare: cere conturile produsului fără cheie de tranzacție și se oprește cu eroarea
    „Cheia de tranzacție nu este definită".
- **OBYC-003 — consignație, bunuri trimise spre probă sau păstrate la dispoziția clientului.**
  Orice ieșire spre o locație de client folosește **Livrare stoc** și înregistrează costul imediat
  (Dr 607 / Cr 371), deși controlul nu s-a transferat (corect: Dr 357 / Cr 371 la expediere în
  consignație). Aceste fluxuri se tratează manual.
- **OBYC-004 — factura emisă înainte de livrare.** O factură integrală (nu de avans) postată
  înainte de livrare înregistrează venitul pe 707, deși ar trebui tratată ca avans (Dr 4111 /
  Cr 419 + 4427; TVA exigibilă la emiterea facturii, art. 282 alin. (2) lit. a)). Recomandarea este
  factura de avans până la livrare; atenție însă: asistentul standard de facturi de avans din
  Vânzări cere conturile produsului fără cheie de tranzacție (`_get_down_payment_account`), deci,
  după cod, se oprește cu „Cheia de tranzacție nu este definită" pe comenzile cu produse cu clasă de
  evaluare — de verificat pe o comandă de test înainte de a recomanda fluxul clientului. Dacă
  factura finală deduce avansul, Odoo stinge singur 419 și TVA-ul avansului, **fără** notă
  manuală. Nota Dr 419 = Cr 707 (701), fără TVA nou, se face doar când o factură integrală postată
  înainte de livrare a fost reclasificată manual pe 419; OMFP pct. 311^1 vorbește de sume
  încasate, pentru facturile neîncasate aceasta este practica uzuală, de confirmat cu contabilul.
- **OBYC-005 — reparat în 19.0.1.0.6.** Înainte de această versiune, lipsa la inventar folosea
  cheia **Ajustare inventar plus**, iar plusul cheia **Ajustare inventar minus**. **La actualizare**,
  regulile configurate după comportamentul vechi (o regulă „plus" care debitează cheltuiala, o
  regulă „minus" care debitează stocul) trebuie să-și schimbe cheia între ele, altfel plusurile se
  înregistrează ca lipsuri și invers; actualizarea modulului le semnalează în jurnalul serverului
  („OBYC-005: account determination rule …"), fără să le modifice.
- **OBYC-006 — reparat în 19.0.1.0.6.** Nota OBYC se generează doar pentru produsele stocabile
  din categorii cu evaluare în timp real, cu cantitate nenulă și fără proprietar terț (marfa în
  custodie nu se evaluează), ca în Odoo standard. Pentru celelalte mișcări nu se mai cere regulă,
  iar o mișcare pe care nici Odoo standard nu o evaluează (de exemplu furnizor → locația de
  inventar) se validează fără notă. Lipsa regulii la o mișcare evaluată în timp real oprește în
  continuare validarea, cu trimitere la configurare. Marfa cu proprietar terț (custodie,
  consignație primită) nu se înregistrează în 371: se ține în afara bilanțului, în contul 8033,
  prin notă manuală (OMFP 1802/2014, pct. 284 alin. (2) lit. a)). Pentru produsele cu evaluare
  periodică (inventar intermitent, pct. 291), intrările se înregistrează pe cheltuieli la factura
  furnizorului, iar stocul se regularizează la inventarul de la sfârșitul perioadei.
- **OBYC-007 — reparat în 19.0.1.0.5–19.0.1.0.6:** mesajul de eroare arată tipurile de locații, titlul regulii
  arată eticheta cheii, fără „None" pentru modificator gol, iar mesajul „regulă lipsă" arată cheia
  în limba utilizatorului. Nu sunt defecte: storno-ul aplicat și liniilor standard ale produselor
  fără clasă (retururile se înregistrează în roșu la toate produsele firmelor cu storno) și costul
  de achiziție pe marfă parțial livrată (comportamentul nucleului `stock_landed_costs`, Pasul 10).
- **OBYC-008 — facturile de avans din comandă (dedus din cod, netestat).** Asistentul de factură de
  avans din comanda de vânzare cere conturile produsului fără cheie de tranzacție și se oprește
  probabil cu „Transaction key is not defined” pe comenzile cu produse OBYC. Testați pe baza
  clientului înainte de a folosi fluxul OBYC-004.
- **OBYC-009 — transfer prin tranzit cu valoare 0 (dedus din cod, netestat).** Mișcarea gestiune →
  tranzit nu primește valoare în Odoo 19, deci nota OBYC poate ieși cu 0; nu folosiți ruta prin
  tranzit fără un test pe baza clientului.
- Cheile **Evaluare stoc**, **Diferență de preț** și **Diferență de preț la recepție stoc** apar
  în listă, dar nu sunt folosite de fluxurile actuale; diferențele de preț nu au tratament OBYC
  (secțiunea 6, „Note de monografie").
- Gestiunile la preț cu amănuntul (378 / 4428) nu sunt suportate (secțiunea 1).

## 10. Capturi de ecran

Capturile sunt generate automat de testul `tests/test_screenshots.py` (mixinul `ScreenshotCase`
din `l10n_ro_doc_screenshots`, import defensiv), pe „RO Company", în RON, în limba română, pe
planul de conturi RO. Testul verifică întâi notele contabile (conturi și sume) și contul liniei de
produs de pe factura de vânzare și de pe cea de furnizor, apoi capturează ecranele. Se regenerează, pe o bază fără date demo, cu:

```bash
./odoo/odoo-bin -c odoo.conf -d test19 -i deltatech_obyc,l10n_ro,l10n_ro_doc_screenshots \
    --test-tags=/deltatech_obyc:TestObycScreenshots --stop-after-init --http-port=8170
```

| Fișier | Conținut |
|---|---|
| `01_account_determination_matrix.png` | matricea de reguli OBYC (Determinare cont produs); Venituri doar cu Cont destinație 707 |
| `02_account_determination_form.png` | formularul regulii Livrare stoc: Condiții și Conturi (①②③) |
| `03_valuation_class_list.png` | lista claselor de evaluare |
| `04_valuation_area_journal.png` | aria de evaluare cu Jurnal de stoc propriu |
| `05_product_valuation_class.png` | produsul cu Clasă de evaluare (tab Contabilitate) |
| `06_stock_move_obyc_entry.png` | nota recepției: Dr 371 / Cr 408, pe jurnalul ariei |
| `11_vendor_bill_408.png` | factura de furnizor: Dr 408 + 4426 / Cr 401, linia de produs pe 408 (OBYC-001) |
| `07_storno_return.png` | returul la furnizor cu storno: Dr 371 −500 / Cr 408 −500 |
| `08_delivery_cogs_entry.png` | nota livrării: Dr 607 / Cr 371 (costul la livrare) |
| `09_sale_invoice_no_cogs.png` | factura de vânzare: Dr 4111 / Cr 707 + 4427, fără linii de cost |
| `10_landed_cost_entry.png` | nota costului de achiziție: Dr 371 / Cr contul liniei de cost |

## 11. Observații pentru manual

- Păstrați explicit **decizia „costul la livrare"** și diferența față de Odoo standard: cititorii
  care cunosc Odoo vor căuta liniile de cost pe factură.
- Tabelul cu **convenția de citire a conturilor** (secțiunea 4) este esențial: numele câmpurilor
  („sursă", „destinație") nu spun singure ce cont se debitează, iar pe facturi contul se alege
  după tipul documentului.
- Limitările **OBYC-001…OBYC-009** trebuie prezentate ca atare, cu procedura manuală, până la
  rezolvarea lor; reverificați `readme/bugs.md` înainte de fiecare ediție a manualului (OBYC-001
  este reparat, dar procedura de corecție a facturilor vechi rămâne utilă la migrări).
- Etichetele din interfață sunt în română („Zonă de evaluare" în meniu, „Arie de evaluare" pe
  câmpuri); de la 19.0.1.0.6 titlul formularului unei reguli afișează eticheta cheii, fără
  modificatorul gol (de exemplu `Livrare stoc - Marfă - Magazin central`); capturile generate
  înainte de această versiune arată încă titlul vechi.
- Unele etichete din nucleul Odoo apar netraduse sau ciudat traduse în capturi (grilele fiscale
  „09 - TAX BASE", „09 - VAT", „24 - TAX BASE", „24 - VAT", butonul „Tăiere" de pe linia de venit); nu țin de acest modul.
