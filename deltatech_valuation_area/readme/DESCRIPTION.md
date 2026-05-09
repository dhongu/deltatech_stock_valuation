## Deltatech Valuation Area

Modul pentru definirea și gestionarea **ariilor de evaluare** a stocului, inspirat din conceptul SAP
de **Valuation Area** (nivel de evaluare per depozit sau locație).

### Funcționalități principale

- **Activare per companie** — funcționalitatea poate fi activată sau dezactivată individual pentru fiecare companie
- **Definire arii de evaluare** cu cod scurt, nume și jurnal contabil dedicat
- **Asociere la nivel de companie, depozit sau locație** — flexibilitate maximă în organizarea evaluării
- **Propagare automată** a ariei de evaluare pe liniile contabile (`account.move.line`) generate din mișcările de stoc
- **Arie obligatorie** pentru produse stocabile (dacă este activată pe companie) — validare prin metodă extensibilă
- **Editare manuală** permisă pe linia contabilă (pentru corecții excepționale)

### Modele extinse

- `valuation.area` — modelul principal: cod, nume, companie, jurnal stoc
- `res.company` — câmpuri `use_valuation_area` (activare) și `valuation_area_id` (arie implicită)
- `stock.warehouse` — câmp `valuation_area_id` (arie per depozit)
- `stock.location` — câmp `valuation_area_id` (arie per locație, prioritate maximă)
- `account.move.line` — câmp `valuation_area_id` (stocat, calculat automat din mișcările de stoc) și metodă de validare `_is_valuation_area_required`

### Logica de determinare a ariei (prioritate)

La generarea liniilor contabile dintr-o mișcare de stoc, aria se determină în ordinea:

1. **Locația destinație** (dacă este internă) — prioritate maximă
2. **Locația sursă** (dacă este internă)
3. **Depozitul** asociat mișcării
4. **Compania** — fallback implicit

> ⚠️ **Constrângere:** Transferurile interne între locații cu arii de evaluare diferite nu sunt permise.
> Sursa și destinația trebuie să aparțină aceleiași arii de evaluare.

### Propagarea ariei pe liniile contabile

```
res.company.valuation_area_id       ← fallback implicit
stock.warehouse.valuation_area_id   ← per depozit
stock.location.valuation_area_id    ← per locație (prioritate maximă)
        ↓
stock.move._get_valuation_area()    ← determină aria din locații
        ↓
account.move.line.valuation_area_id ← stocat pe linia contabilă
```

Metoda `_prepare_account_move_line` este extinsă pentru a injecta automat `valuation_area_id`
pe fiecare linie contabilă generată din mișcările de stoc.

### Configurare

Ariile de evaluare se configurează din meniul **Inventar > Configurare > Arii de Evaluare**.
Pentru fiecare arie se specifică:

- **Nume** — denumire descriptivă
- **Cod** — cod scurt utilizat în determinarea conturilor contabile
- **Companie** — compania căreia îi aparține aria
- **Jurnal stoc** — jurnalul contabil pentru tranzacțiile de stoc din această arie

### Metodă de evaluare suportată

> ⚠️ **Important:** Acest modul este proiectat pentru metoda de evaluare **AVCO (cost mediu ponderat)**.
> Nu este compatibil cu produsele configurate cu metoda **FIFO**.

Ariile de evaluare agregează liniile contabile (`account.move.line`) per produs și arie, calculând un cost mediu ponderat.
Metoda FIFO necesită urmărirea straturilor individuale de cost, informație care se pierde prin această agregare.

### Dependențe

- `stock_account` — evaluare stoc standard Odoo
