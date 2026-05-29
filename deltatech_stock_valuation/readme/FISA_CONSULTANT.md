# Fișă Modul: Product Stock Valuation

**Modul:** `deltatech_stock_valuation`  
**Rol principal:** evaluare de stoc pe produs + arie de evaluare + cont contabil, bazată pe note contabile  
**Utilizatori principali:** contabil stocuri, controller, administrator Odoo

---

## 1. Scop

Modulul adaugă un strat de evaluare paralel cu mecanismul standard Odoo. În loc
să ia drept sursă mișcările de stoc sau straturile clasice, el reconstruiește
valoarea și cantitatea din `account.move.line` postate.

Rezultatul este urmărit în două modele:

- `product.valuation` — soldul curent;
- `product.valuation.history` — istoricul lunar.

Granularitatea actuală este:

- produs;
- arie de evaluare;
- cont contabil;
- companie.

## 2. Când este util

- când vrei reconciliere mai bună între stoc și contabilitate;
- când ai nevoie de raportare pe arii de evaluare;
- când există corecții contabile manuale și vrei ca evaluarea să urmărească exact
  notele postate;
- când modelul de cost folosit este **AVCO**.

## 3. Configurare

### 3.1 Condiții de bază

Modulul depinde de `deltatech_valuation_area`, deci compania trebuie să aibă
Valuation Area activă și o arie implicită configurată.

### 3.2 Setări companie

Meniu: `Inventar → Configurare → Setări`

Câmpuri relevante:

| Câmp | Rol |
|---|---|
| `Valuation Area Level` | nivelul de lucru: company / warehouse / location |
| `Valuation Area` | aria implicită a companiei |

Important: fluxul de **refresh** livrat în UI este funcțional doar când
`Valuation Area Level = company`.

### 3.3 Conturi de evaluare

Pe `account.account` există câmpul:

- **Stock Valuation** (`is_for_stock_valuation`)

Acest marcaj spune modulului ce conturi intră în calcul.

### 3.4 Categorii de produs

Pe categorie există opțiunea:

- **Use Valuation Area Price**

Când este activă, ieșirile din stoc folosesc prețul din `product.valuation`
pentru aria și contul curent, nu doar `standard_price`.

Regulă importantă: opțiunea nu este compatibilă cu **FIFO**. La încercarea de
activare pe categorie FIFO apare mesajul:

> `Category '...': Use Valuation Area Price is not compatible with FIFO costing method. Please use AVCO.`

## 4. Flux operațional

### Pasul 1 — marcați conturile de evaluare

Marcați conturile contabile care trebuie urmărite cu **Stock Valuation**.

În practică, metoda `set_stock_valuation_at_company_level()` marchează automat
conturile de evaluare din categoriile de produs ce au cont de stoc configurat.

### Pasul 2 — generați sau corectați notele contabile

Sursa de adevăr este `account.move.line` în stare **posted**, cu:

- produs;
- cantitate;
- cont;
- arie de evaluare.

### Pasul 3 — reconstruiți istoricul

Din Setări, consultantul are la dispoziție secțiunea **Refresh valuation** cu
butonul **Execute Next Step**. Fluxul rulează în 7 pași:

1. ștergere istoric;
2. calcul mișcări lunare;
3. completare luni lipsă;
4. calcul sold final curent;
5. propagare solduri pe produse, în batch-uri;
6. ștergere linii goale;
7. recalcul `product.valuation`.

Există și:

- **Reset to Step 1**
- **Recompute Product Valuation**
- **Start Auto Refresh** / **Stop**

Auto-refresh folosește un cron care rulează la 2 minute și se oprește singur
după finalizarea ciclului.

### Pasul 4 — consultați rezultatul

Meniuri:

- `Product Valuation`
- `Product Valuation History`

Acestea sunt accesibile din zona de control/raportare a stocului și oferă listă,
formular și pivot.

## 5. Ce calculează efectiv

### 5.1 `product.valuation`

Reține soldul curent:

- `quantity`
- `amount`
- `price`

Prețul este determinat în principal ca:

- `amount_final / quantity_final`, dacă există stoc final;
- altfel `debit / quantity_in`, dacă există doar intrări în ultima lună.

### 5.2 `product.valuation.history`

Reține pe lună:

- sold inițial;
- intrări / ieșiri;
- debit / credit;
- sold final.

Cantitățile sunt reconstruite din `account.move.line`, convertite în UoM-ul
produsului.

## 6. Reguli importante

| Situație | Comportament actual |
|---|---|
| documentul contabil nu este postat | nu intră în evaluare |
| linia nu are produs | nu intră în evaluare |
| contul nu este marcat `Stock Valuation` | nu intră în evaluare |
| nivelul ariei nu este `company` | butoanele de refresh nu sunt utile, iar refresh-ul returnează fără acțiune |
| categorie cu FIFO și `Use Valuation Area Price` | blocată prin validare |
| lipsă evaluare pentru aria curentă la ieșire | se revine la `standard_price`, cu warning în log |

## 7. Unde se vede în interfață

- produs / template — tabel `Product Valuations`
- cont contabil — bifa `Stock Valuation`
- categorie produs — `Use Valuation Area Price`
- Setări Inventar — `Valuation Area Level`, refresh și auto-refresh
- meniuri dedicate:
  - `Product Valuation`
  - `Product Valuation History`

## 8. Verificări utile pentru consultant

- [ ] compania are arie implicită și nivel corect de evaluare
- [ ] conturile de stoc relevante sunt marcate `Stock Valuation`
- [ ] liniile contabile postate au produs, cantitate și arie
- [ ] refresh-ul rulează complet până la pasul 7
- [ ] soldul din `Product Valuation` corespunde ultimei luni din `Product Valuation History`
- [ ] categoria nu folosește FIFO dacă e activ `Use Valuation Area Price`

## 9. Limitări cunoscute

- modulul este declarat **Alpha** în manifest;
- direcția livrată este pentru **AVCO**, nu pentru **FIFO**;
- refresh-ul operațional complet este tratat doar pentru nivelul `company`;
- evaluarea depinde de calitatea datelor contabile, nu de o reconciliere automată
  cu toate scenariile logistice;
- când nu există evaluare per arie, ieșirea folosește fallback la `standard_price`.

## 10. Capturi recomandate

- [ ] [SCREENSHOT: cont contabil cu bifa Stock Valuation]
- [ ] [SCREENSHOT: categorie produs cu Use Valuation Area Price]
- [ ] [SCREENSHOT: Setări Inventar cu Refresh valuation]
- [ ] [SCREENSHOT: Product Valuation list]
- [ ] [SCREENSHOT: Product Valuation History pivot]
- [ ] [SCREENSHOT: template produs cu tabel Product Valuations]
