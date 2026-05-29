# Fișă Modul: OBYC / Account Determination

**Modul:** `deltatech_obyc`  
**Rol principal:** determinarea automată a conturilor de stoc pe baza unei matrice de reguli  
**Utilizatori principali:** contabil, consultant implementare, administrator Odoo

---

## 1. Scop

Modulul aduce în Odoo un mecanism de tip **OBYC**: conturile nu mai sunt luate
doar din categoria de produs, ci dintr-o regulă determinată de combinația:

- cheie de tranzacție;
- clasă de evaluare;
- arie de evaluare;
- account modifier;
- companie.

Practic, modulul permite o mapare contabilă mai fină pentru recepții, livrări,
retururi, transferuri interne, inventar, producție și landed cost.

## 2. Date de bază

### 2.1 Evaluation Class

Meniu: `Inventar → Configurare → Account Determination Config → Evaluation Class`

Modelul `product.valuation.class` are:

- `Code`
- `Name`

Se afișează în formatul **`[CODE] Name`**.

### 2.2 Account Modifiers

Meniu: `Inventar → Configurare → Account Determination Config → Account Modifiers`

Modelul `account.modifier` are:

- `Code`
- `Name`

Și el se afișează în formatul **`[CODE] Name`**.

### 2.3 Product Account Determination

Meniu: `Inventar → Configurare → Account Determination Config → Product Account Determination`

Regula conține:

| Câmp | Rol |
|---|---|
| `Transaction Key` | tipul operațiunii |
| `Account Modifier` | diferențiere suplimentară |
| `Valuation Class` | clasa produsului |
| `Valuation Area` | aria de evaluare |
| `Company` | compania |
| `Source Account` | contul de sursă |
| `Destination Account` | contul de destinație |
| `Valuation Account` | contul de evaluare |

## 3. Unde se configurează pe documente și produse

- pe produs (`product.template`) se completează **Valuation Class**;
- pe tipul de operațiune stoc (`stock.picking.type`) se poate completa
  **Account Modifier**;
- pe jurnal (`account.journal`) există de asemenea **Account Modifier**;
- aria de evaluare vine din `deltatech_valuation_area`.

## 4. Chei de tranzacție folosite acum

Din codul actual, cele mai importante chei sunt:

- `stock_receipt`
- `return_to_supplier`
- `stock_delivery`
- `return_from_customer`
- `dropship`
- `dropship_return`
- `internal_transfer`
- `internal_transfer_out`
- `internal_transfer_in`
- `inventory_adjustment_plus`
- `inventory_adjustment_minus`
- `production_issue`
- `production_receipt`
- `price_difference`
- `landed_cost`
- `stock_income`

## 5. Cum decide regula

### 5.1 Pe mișcările de stoc

`stock.move` calculează `transaction_key` din combinația `usage` sursă/destinație.

Exemple din cod:

| Sursă | Destinație | Transaction Key |
|---|---|---|
| supplier | internal | `stock_receipt` |
| internal | customer | `stock_delivery` |
| customer | internal | `return_from_customer` |
| internal | supplier | `return_to_supplier` |
| internal | internal | `internal_transfer` |
| internal | transit | `internal_transfer_out` |
| transit | internal | `internal_transfer_in` |

Dacă nu poate determina cheia, modulul ridică eroare:

> `Transaction key could not be determined for the move from ... to ...`

### 5.2 Pe facturi

`account.move.line` suprascrie calculul contului pentru liniile de produs:

- document de vânzare → `stock_income`
- document de cumpărare → `stock_receipt`

Linia primește și `valuation_area_id`.

### 5.3 Dacă regula lipsește

În loc de eroare simplă, modulul ridică **RedirectWarning** spre configurarea
regulilor, cu precompletarea contextului. Mesajul începe cu:

> `No account determination rule found for transaction key '...'`

## 6. Flux recomandat de implementare

### Pasul 1 — creați ariile de evaluare

Fără `valuation.area`, regulile nu pot fi selectate corect.

### Pasul 2 — definiți clasele de evaluare

Faceți o clasificare contabilă a produselor: marfă, materie primă, produs finit,
ambalaj etc.

### Pasul 3 — atașați clasa pe produse

Completați **Valuation Class** pe șablonul produsului.

### Pasul 4 — definiți modificatorii contabili

Folosiți `Account Modifier` dacă aveți fluxuri care trebuie separate prin tip de
operațiune, jurnal sau scenariu.

### Pasul 5 — creați matricea de reguli

Pentru fiecare combinație importantă configurați:

- cheie tranzacție;
- clasă;
- arie;
- modifier;
- conturile sursă / destinație / evaluare.

### Pasul 6 — testați pe documente reale

Verificați recepție, livrare, retur și o factură de vânzare/cumpărare cu produs
care are `valuation_class_id`.

## 7. Comportament actual la note contabile de stoc

Pe `stock.move`, dacă produsul nu are `valuation_class_id`, modulul lasă fluxul
standard Odoo.

Dacă produsul are `valuation_class_id`, regula OBYC controlează nota:

- dacă toate cele trei conturi sunt goale, nu se mai creează NC;
- dacă există reguli, modulul decide contul de debit și credit din regula găsită;
- liniile generate păstrează și `product_id`, deci pot fi urmărite și în
  evaluarea pe arie.

Pentru `landed_cost`, cheia folosită este explicit `landed_cost`.

## 8. Verificări utile pentru consultant

- [ ] produsul are `Valuation Class`
- [ ] compania are `Valuation Area`
- [ ] există regulă pentru fiecare tranzacție testată
- [ ] tipul de picking are `Account Modifier`, dacă scenariul îl cere
- [ ] la facturi, contul produsului este recalculat pe baza regulii
- [ ] la mutări de stoc, cheia de tranzacție corespunde fluxului real

## 9. Limitări cunoscute

- multe explicații din `DESCRIPTION.md` sunt mai largi decât codul efectiv; fișa
  de față descrie doar comportamentul implementat acum;
- logica e foarte dependentă de existența unei matrice complete de reguli;
- dacă produsul nu are `valuation_class_id`, se revine la comportamentul standard;
- unele suprascrieri istorice din `stock.move` sunt comentate, deci nu toate
  scenariile descrise teoretic sunt active în codul curent;
- modulul se bazează pe `deltatech_valuation_area` pentru selecția ariei.

## 10. Capturi recomandate

- [ ] [SCREENSHOT: meniul Account Determination Config]
- [ ] [SCREENSHOT: formular Evaluation Class]
- [ ] [SCREENSHOT: formular Account Modifier]
- [ ] [SCREENSHOT: formular Product Account Determination]
- [ ] [SCREENSHOT: produs cu Valuation Class]
- [ ] [SCREENSHOT: picking type cu Account Modifier]
- [ ] [SCREENSHOT: mesaj RedirectWarning când lipsește regula]
