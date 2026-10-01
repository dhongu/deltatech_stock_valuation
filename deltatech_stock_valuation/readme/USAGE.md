## Mod de utilizare

Modulul calculează evaluarea stocului direct din notele contabile postate, pe combinația
**produs × arie de evaluare × cont contabil**. Mai jos sunt pașii de configurare și fluxul de lucru.

### 1. Configurare inițială (o singură dată)

Toți pașii necesită drepturi de **Administrator de sistem**.

1. **Activează aria de evaluare**
   Mergi la **Inventar → Configurare → Setări**, secțiunea *Valuation*.
   - Bifează *Use Valuation Area*.
   - Setează *Valuation Area Level* pe **Company** (singurul nivel suportat complet în acest moment).
   - Câmpul *Valuation Area* se completează automat la salvare (se creează o arie pentru companie).

2. **Marchează conturile de evaluare a stocului**
   La salvarea setărilor, conturile de evaluare a stocului din categoriile de produse
   (`property_stock_valuation_account_id`) sunt marcate automat cu *Stock Valuation*
   (`is_for_stock_valuation`).
   Poți marca/demarca manual orice cont din **Contabilitate → Configurare → Plan de conturi**,
   deschizând contul și bifând caseta **Stock Valuation**.

   > Doar mișcările de pe conturile marcate intră în evaluare. Pe aceste conturi, aria de
   > evaluare devine **obligatorie** pe liniile contabile ale produselor stocabile.

3. *(Opțional)* **Descărcare de gestiune la cost mediu**
   Dacă vrei ca ieșirile din stoc să fie valorizate la costul mediu din `product.valuation`
   (în loc de prețul standard), deschide categoria de produse
   (**Inventar → Configurare → Categorii de produse**) și bifează **Use Valuation Area Price**.
   - Caseta este disponibilă doar pentru categoriile cu metodă **AVCO** (cost mediu).
   - Este **incompatibilă cu FIFO** — activarea pe o categorie FIFO ridică eroare.

### 2. Fluxul zilnic

Nu este nevoie de operații suplimentare: la **postarea** oricărei note contabile (factură furnizor,
factură client, retur, notă manuală) care conține linii pe un cont de evaluare a stocului,
modulul recalculează automat:

- linia curentă din **Product Valuation** (cantitate, valoare, preț mediu);
- linia lunii respective din **Product Valuation History**.

Semnul mișcărilor este dedus din tipul documentului:

| Tip document | Efect asupra cantității |
|---|---|
| Factură furnizor (`in_invoice`) | + intrare |
| Retur la furnizor (`in_refund`) | − ieșire |
| Factură client (`out_invoice`) | − ieșire |
| Retur de la client (`out_refund`) | + intrare |

### 3. Vizualizarea evaluării

- **Inventar → Operațiuni → Product Valuation** — soldul curent (preț mediu, cantitate, valoare)
  per produs / arie / cont. Există și vizualizare *pivot*.
- **Inventar → Operațiuni → Product Valuation History** — istoricul lunar: sold inițial, intrări,
  ieșiri, debit, credit, sold final. Util pentru reconcilierea cu balanța contabilă pe fiecare lună.

Înregistrările sunt **doar pentru citire** (nu se creează/șterg manual) — ele reflectă notele contabile.

### 4. Recalculare completă

Necesară după **prima instalare**, după **import de date** sau după corecții contabile retroactive.
Disponibilă în **Inventar → Configurare → Setări**, secțiunea *Valuation* (doar Administrator de sistem).

**Recomandat — un singur clic:**

- **Recompute All (Background)** — repornește ciclul de la primul pas și lasă un cron să execute
  automat toți cei **7 pași**, unul câte unul, fără intervenția utilizatorului. Cron-ul reține în
  parametri pasul curent, deci „știe" mereu ce mai are de executat. După fiecare pas primești o
  **notificare** (toast) cu pasul executat și durata, iar în setări vezi indicatorii *Next step* și
  *Last refresh progress*. Când termină, cron-ul se oprește singur.
  Cât rulează, butonul devine **Stop Background Refresh** și apare indicatorul *Running…*.

Cei 7 pași: ștergere istoric → calcul mișcări lunare → completare luni lipsă → sold ultima lună →
propagare solduri → ștergere linii goale → evaluare curentă. Pasul 5 (propagarea) se execută în
loturi, în mai multe reprize, pentru a nu bloca bazele de date mari.

**Manual (avansat / depanare):**

- **Execute Next Step** — execută un singur pas (cele 7 click-uri manuale).
- **Reset to Step 1** — repornește ciclul de la primul pas.
- **Recompute Product Valuation** — recalculează doar soldul curent din ultima lună de istoric.

Echivalent programatic (ex. din shell sau acțiune server):

```python
# Reconstruiește istoricul lunar din notele contabile, apoi soldul curent
env["product.valuation.history"]._recompute_all_amount()
env["product.valuation"]._recompute_all_amount()
```

### 5. Verificarea consistenței cu contabilitatea

Pentru o lună dată, suma `amount_final` din **Product Valuation History** pe un cont de evaluare
trebuie să corespundă soldului contabil al acelui cont (modulul folosește `account.move.line`
ca sursă de adevăr, deci consistența este garantată prin construcție).

### 6. Mesaje și depanare frecvente

- **„Valuation Area is required for stockable products"** — produsul este stocabil și linia
  contabilă este pe un cont de evaluare, dar nu are arie de evaluare. Verifică nivelul ariei pe
  companie și că documentul are o arie validă.
- **„Use Valuation Area Price is not compatible with FIFO"** — schimbă metoda categoriei pe AVCO
  sau dezactivează *Use Valuation Area Price*.
- **Linii excluse din evaluare (UoM produs lipsă)** — la recalcularea completă, liniile cu produse
  fără unitate de măsură pe șablon sunt ignorate; un avertisment în log indică numărul și valoarea lor.
