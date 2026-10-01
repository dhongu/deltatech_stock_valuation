# Fișă Modul: Arii de evaluare a stocului (Valuation Area)

**Modul:** `deltatech_valuation_area`
**Utilizator principal:** contabil stocuri, administrator Odoo, manager depozit
**Prioritate:** 🟡 Medie (infrastructură: are efect complet împreună cu `deltatech_stock_valuation` și/sau `deltatech_obyc`)

> Fișă pentru **Odoo 20**, actualizată la 01.10.2026 (pornind de la fișa din 19.0): regulile de
> determinare a ariei au fost reverificate pe codul Odoo 20 (vezi limitările de la secțiunea 11),
> iar în Setări există o setare nouă, **Păstrează valoarea mișcării la recalcularea retroactivă**,
> care există doar în Odoo 20 (pasul 1). Etichetele de mai jos sunt cele din interfața RO.

---

## 1. Scop business

Modulul introduce **aria de evaluare** — o unitate de evidență a stocului sub nivelul companiei
(conceptul SAP *Valuation Area*): un depozit, o gestiune sau o locație care trebuie urmărită
separat valoric. Aria se stabilește pe companie (implicit), pe depozit sau pe locație internă și
se scrie automat pe liniile notelor contabile care au produs. Pe această etichetă se sprijină
modulele de evaluare pe arie (`deltatech_stock_valuation`, prețul mediu pe arie) și de determinare
a conturilor (`deltatech_obyc`, conturi și jurnal per arie). Folosit singur, modulul **etichetează**
liniile contabile; nu produce rapoarte valorice.

## 2. Bază legală și context

Modulul nu implementează o cerință legală anume. Este un instrument de organizare a evidenței
stocurilor pe gestiuni/arii, util firmelor care țin stocul pe mai multe depozite sau puncte de
lucru și vor evidența valorică separată pe fiecare.

Context de metodă: modulul este proiectat pentru evaluarea la **cost mediu ponderat (AVCO)**.
Ariile agregă liniile contabile pe produs și arie, ceea ce nu păstrează straturile de cost cerute
de **FIFO** — produsele pe FIFO nu sunt suportate de evaluarea pe arii.

## 3. Utilizatori și roluri

| Rol | Ce face | Drepturi necesare |
|---|---|---|
| Administrator Odoo | activează ariile pe companie și alege aria implicită | Administrare / Setări |
| Manager depozit | completează aria pe depozite și locații | Inventar / Administrator (câmpul e vizibil doar acestui grup) |
| Contabil-șef / administrator contabil | definește ariile și jurnalele lor de stoc | Contabilitate / **Administrator** (doar acest grup poate crea, modifica sau șterge arii; ceilalți utilizatori interni le pot doar citi) **+ Inventar / Administrator**, ca să vadă meniul **Configurare** din Inventar, unde se află ariile |
| Contabil stocuri | verifică aria pe notele de stoc și pe facturi | Contabilitate / Contabil; pentru lista **Elemente jurnal** e nevoie de cel puțin drept de citire în Contabilitate |

Pentru testare: un utilizator cu **Inventar / Administrator** + **Contabilitate / Administrator**
acoperă tot fluxul; pentru pasul 1 este nevoie și de drepturi de administrare (Setări). Atenție:
managerul de depozit vede meniul ariilor, dar fără Contabilitate / Administrator nu poate crea arii;
invers, contabilul-șef fără Inventar / Administrator are dreptul să creeze arii, dar nu vede meniul.

## 4. Conturi și date implicate

| Cont | Rol în demo |
|---|---|
| 371 Mărfuri | contul de stoc al produselor (linia care primește aria și cantitatea semnată) |
| 607 Cheltuieli privind mărfurile | contul de pierderi pus pe locația de ajustare a inventarului (contrapartida notei de stoc automate) |
| 4426 TVA deductibilă | TVA 21% pe factura de furnizor din pasul 8 |
| 401 Furnizori | contrapartida facturii de furnizor din pasul 8 |
| 707 / 4427 / 4111 | venitul, TVA colectată și clientul pe factura de client din pasul 9 |

Datele minime pentru demo (sunt și cele din capturi):

- compania **RO Company**, plan de conturi RO, monedă RON;
- aria **[STD] Arie standard** (implicită pe companie), pe jurnalul de stoc al companiei
  (**Evaluare stocuri**);
- aria **[DEP] Arie depozit**, cu jurnal de stoc propriu (**Stoc depozit**), pusă pe depozitul
  **Depozit central** și pe locația lui de stoc **DC/Stoc**;
- o locație internă separată, **DC/Raft magazin**, cu aria **[STD]**;
- un produs stocabil dintr-o categorie cu evaluarea perpetuă (în interfață: **Perpetual (at
  invoicing)** — eticheta nu are traducere RO în Odoo 20), metoda de cost **Average Cost (AVCO)**
  și cont de stoc 371, pentru nota de stoc automată și pentru factura de furnizor;
- partenerii **Furnizor Demo SRL** și **Client Demo SRL**;
- setarea **Locații de stocare** activă (pentru meniul **Locații**).

## 5. Configurare inițială

1. **Inventar → Configurare → Setări**, secțiunea **Evaluare**: bifați **Folosește arii de
   evaluare** (pasul 1). Câmpul pentru aria implicită apare sub bifă, dar îl completați abia
   după ce creați ariile (pașii 2–3). Lăsați bifată (valoarea implicită) setarea **Păstrează
   valoarea mișcării la recalcularea retroactivă**, dacă nu ați decis altfel cu contabilul
   (vezi pasul 1).
2. **Inventar → Configurare → Gestiunea depozitului → Arii de evaluare** (meniul e vizibil doar
   pentru *Contabilitate / Administrator*, singurul grup care poate scrie ariile): creați ariile.
3. Reveniți în Setări și alegeți **Arie de evaluare** = aria implicită a companiei; **Salvează**.
4. **Inventar → Configurare → Gestiunea depozitului → Depozite**: completați **Arie de evaluare** pe depozitele evaluate
   separat (pasul 4).
5. **Inventar → Configurare → Gestiunea depozitului → Locații** (meniul apare doar cu setarea
   **Locații de stocare** activă): completați **Arie de evaluare** doar pe locațiile
   interne care au altă arie decât depozitul lor; celelalte iau aria depozitului (pasul 4).
6. Pentru ca stocul să genereze note contabile automate (pasul 6): categoria produsului cu
   evaluarea **Perpetual (at invoicing)** și, pe locația de ajustare a inventarului, contul de
   pierderi completat: **Inventar → Configurare → Gestiunea depozitului → Locații**, scoateți
   filtrul implicit **Intern**, deschideți locația de ajustare a inventarului (în baza demo
   „Inventory adjustment", tip **Pierdere la inventar**) și completați **Cont pierderi** = 607.

## 6. Flux de utilizare

### Pasul 1 — Activarea ariilor pe companie

**Inventar → Configurare → Setări**, secțiunea **Evaluare**. Bifați **Folosește arii de
evaluare** ①; sub bifă apare câmpul **Arie de evaluare** — aria implicită a companiei, folosită
când nici locația, nici depozitul nu au arie. Apăsați **Salvează**.

La prima configurare ariile nu există încă: lăsați câmpul gol, creați ariile (pașii 2–3) și
reveniți aici să alegeți aria implicită (vezi secțiunea 5, punctul 3).

Cât timp bifa nu e activă, modulul nu completează și nu cere aria nicăieri (cantitatea cu semn
și unitatea de măsură se scriu totuși pe notele de stoc, vezi pasul 6). Setarea e per companie:
celelalte companii din bază nu sunt afectate.

În același bloc apare setarea **Păstrează valoarea mișcării la recalcularea retroactivă** ②,
**bifată implicit** pe fiecare companie. Ea există doar în Odoo 20 și privește o schimbare a
versiunii: când o mișcare de stoc deja validată își schimbă poziția în timp (i se modifică data,
i se corectează cantitatea după validare sau o intrare este reevaluată după ce stocul a fost deja
descărcat), Odoo 20 reia valorizarea tuturor mișcărilor ulterioare ale produsului și **rescrie
valoarea ieșirilor** deja validate, dar **nu corectează notele contabile deja postate**.

| Setare | Efect |
|---|---|
| bifată (implicit) | mișcările validate își păstrează valoarea calculată la validare, ca în Odoo 19; valoarea stocului rămâne egală cu notele contabile postate |
| debifată | se aplică reluarea standard Odoo 20; valoarea ieșirilor se rescrie, iar valoarea stocului și contabilitatea pot ajunge să difere |

**Atenție:** modulul doar oferă setarea; ea are efect numai împreună cu `deltatech_stock_valuation`
(produsele din categoriile evaluate la prețul ariei) și cu `deltatech_obyc` (produsele cu clasă de
evaluare OBYC). Pentru celelalte produse, și când este instalat doar acest modul, Odoo 20 aplică
mereu reluarea standard, oricum ar fi setarea. Schimbați setarea doar cu acordul contabilului.

![Setări Inventar — Folosește arii de evaluare, aria implicită și Păstrează valoarea mișcării](screenshots/01_setari_use_valuation_area.png)

### Pasul 2 — Lista ariilor de evaluare

**Inventar → Configurare → Gestiunea depozitului → Arii de evaluare**. Lista arată, pentru fiecare arie, **Cod**,
**Nume**, **Companie** și **Jurnal de stoc**. Butonul **Nou(ă)** creează o arie nouă.

![Lista ariilor de evaluare](screenshots/02_valuation_area_list.png)

### Pasul 3 — Formularul ariei: cod și jurnal de stoc

Deschideți o arie din listă (sau creați una). Completați:

| Câmp | Rol |
|---|---|
| **Cod** ① | cod scurt, obligatoriu; apare în numele afișat `[COD] Nume` (regulile de conturi din `deltatech_obyc` se leagă de arie, nu de cod) |
| **Nume** | denumirea ariei, obligatorie |
| **Companie** | compania căreia îi aparține aria (implicit compania curentă) |
| **Jurnal de stoc** ② | jurnalul pe care se înregistrează notele de stoc ale ariei — **folosit doar dacă este instalat `deltatech_obyc`**; se pot alege doar jurnale de tip *Diverse* ale companiei ariei |

Numele afișat al ariei are forma **`[COD] Nume`** (ex. „[STD] Arie standard").

Despre **Jurnal de stoc**: cu `deltatech_obyc` instalat, mișcările produselor care au **clasă de
evaluare OBYC** dintr-o arie cu jurnal propriu primesc nota de stoc pe jurnalul ariei; restul
mișcărilor rămân pe jurnalul de stoc al companiei. Fără `deltatech_obyc`, câmpul este doar
informativ: notele de stoc merg mereu pe jurnalul de stoc al companiei (vezi pasul 6, unde aria
[DEP] are jurnalul „Stoc depozit", dar nota e pe „Evaluare stocuri").

![Formularul ariei — Cod și Jurnal de stoc](screenshots/03_valuation_area_form.png)

### Pasul 4 — Aria pe depozit

**Inventar → Configurare → Gestiunea depozitului → Depozite**. Coloana **Arie de evaluare** (opțională, afișată implicit)
arată aria fiecărui depozit; o completați din formularul depozitului, câmpul **Arie de evaluare**
de lângă adresă. În captură, **Depozit central** are aria **[DEP] Arie depozit**, care înlocuiește
aria implicită a companiei pe mișcările depozitului.

Aria depozitului se aplică tuturor mișcărilor pe locațiile lui interne, inclusiv ajustărilor de
inventar și transferurilor create manual: depozitul se deduce din locație (de la versiunea
20.0.1.0.4; înainte, aceste mișcări cădeau pe aria implicită a companiei, VA-001). Aria pusă pe o
locație (pasul 5) are prioritate față de cea a depozitului. În demo, DC/Stoc are explicit aceeași
arie [DEP] ca depozitul.

![Lista depozitelor cu coloana Arie de evaluare](screenshots/04_depozit_valuation_area.png)

### Pasul 5 — Aria pe locația internă

**Inventar → Configurare → Gestiunea depozitului → Locații** (meniul apare doar cu setarea
**Locații de stocare** activă), deschideți locația. În grupul **Informații suplimentare**,
câmpul **Arie de evaluare** ① (vizibil doar pentru Inventar / Administrator). Aria locației are
**prioritate maximă** și se ia doar pentru locațiile de tip **Intern**.

Aria **nu se moștenește** de la locația părinte: o locație internă fără arie proprie (inclusiv
sublocațiile, rafturile) ia aria depozitului ei, apoi pe cea a companiei. O mișcare între două
locații interne este refuzată la validare dacă ariile lor efective (proprie → depozit → companie)
diferă (secțiunea 9).

![Formularul locației — Arie de evaluare](screenshots/05_locatie_valuation_area.png)

### Pasul 6 — Nota de stoc generată automat

Nota din captură se obține printr-o ajustare de inventar: **Inventar → Operații → Ajustări →
Inventariere fizică**, linia produsului pe **DC/Stoc**, **Cantitate numărată** = 5, apoi
**Aplică**. Ecranul ajustării este cel standard Odoo; modulul intervine abia pe nota contabilă
rezultată, pe care o deschideți din **Facturare → Examinare → Control → Elemente jurnal** (sau din
jurnalul **Evaluare stocuri**).

Notele contabile generate din mișcările de stoc primesc automat, pe fiecare linie cu produs:

- **aria de evaluare**, determinată în ordinea:
  1. locația destinație, dacă e internă și are arie;
  2. locația sursă, dacă e internă și are arie;
  3. depozitul mișcării (vezi atenționarea de la pasul 4);
  4. aria implicită a companiei;
- **cantitatea, cu semn**: pozitivă pe linia de debit, negativă pe linia de credit;
- **unitatea de măsură** a produsului.

În Odoo 20 standard liniile notelor de stoc nu poartă cantitate; fără completarea automată,
evaluarea pe arii ar pierde cantitățile. În Odoo 20 nota de stoc se generează automat doar pentru
produsele cu evaluare perpetuă și doar la mișcările spre/din locațiile cu cont propriu
(ajustarea de inventar — cont de pierderi, producția — cont de cost); recepțiile și livrările
obișnuite se înregistrează contabil prin facturi (pasul 8).

Semnul cantității se stabilește după partea liniei (debit/credit), nu după valoarea mișcării de
stoc. În Odoo 20 valoarea unei mișcări de ieșire este **negativă** (în Odoo 19 era pozitivă), dar
sumele de pe notă rămân pozitive, iar regula de semn a cantității este aceeași ca în Odoo 19.

Exemplul din captură: plus de 5 bucăți la inventar pe **DC/Stoc** — nota are aria **[DEP] Arie
depozit** pe ambele linii (aria locației destinație), cantitatea +5 pe linia de debit 371 și −5 pe
linia de credit 607. Coloana **Arie de evaluare** e opțională în lista liniilor: o afișați din
butonul de coloane opționale din capul tabelului. Cantitatea nu are coloană în lista liniilor
notei; o verificați la pasul 7.

![Notă de stoc generată automat la plus de inventar, cu aria pe linii](screenshots/06_nota_stoc_automata.png)

### Pasul 7 — Cantitatea semnată pe linia notei de stoc

**Facturare** (sau **Contabilitate**, cu Enterprise) **→ Examinare → Control → Elemente jurnal**, deschideți
linia 371 a notei de la pasul 6. În grupul **Valoare**, câmpul **Cantitate** ① arată **5,00**
(pozitiv, linia e de debit); în grupul **Produs** ② apare produsul. Linia 607 a aceleiași note
are cantitatea **−5,00**. Câmpul e doar de citire. Meniul **Elemente jurnal** cere cel puțin drept
de citire în Contabilitate.

Această cantitate semnată este cea pe care `deltatech_stock_valuation` o agregă pe arie.

![Formularul liniei 371 — Cantitate +5 și Produs](screenshots/07_linie_stoc_cantitate.png)

### Pasul 8 — Factura de furnizor pentru marfa recepționată

În demo, marfa (10 buc, cost 20 lei/buc) a fost recepționată întâi pe **DC/Raft magazin**
printr-o recepție manuală (**Inventar → Operații → Transferuri → Recepții**), fără comandă de
achiziție; factura vine la același preț, 20 lei/buc. Cu
evaluarea **Perpetual (at invoicing)**, recepția nu generează notă contabilă: în Odoo 20 marfa
intră valoric în 371 prin factura de furnizor.

**Facturare → Furnizori → Facturi**, factura postată, tab-ul **Elemente jurnal**. Pe linia
produsului, coloana opțională **Arie de evaluare** e completată automat: aria se ia din mișcarea
de stoc legată (recepția comenzii de achiziție, respectiv livrarea comenzii de vânzare pe facturile
de client), altfel din aria implicită a companiei. Liniile fără produs (TVA, furnizor) rămân fără
arie. În captură, factura nu e legată de recepție (nu există comandă de achiziție), deci primește
aria implicită **[STD] Arie standard** pe linia 371 — aceeași cu aria raftului pe care a intrat
marfa. Coloana nu există în tab-ul **Linii factură**, doar în **Elemente jurnal**.

**Atenție:** aria liniei se calculează la alegerea produsului și nu se mai recalculează. Dacă
factura (ciorna) e creată **înaintea** recepției comenzii de achiziție, linia primește aria
implicită, iar validarea ulterioară a recepției nu o schimbă. Verificați și, dacă e cazul,
corectați aria în tab-ul **Elemente jurnal** cât timp factura e ciornă. Factura sosită înaintea
mărfii se tratează contabil, după politica firmei, pe 327 „Mărfuri în curs de aprovizionare”;
modulul nu intervine în această înregistrare.

Cât timp compania folosește ariile, linia cu produs **stocabil** **nu poate rămâne fără arie**:
golirea ei blochează salvarea cu mesajul de la secțiunea 9. Aria se completează însă pe **orice**
linie cu produs (inclusiv servicii și consumabile): dacă compania nu are arie implicită și linia
nu are o mișcare legată, chiar alegerea produsului pe linie e refuzată („Aria de evaluare nu este
definită") — pe facturi și pe orice linie contabilă cu produs, creată de alte documente.

![Factură de furnizor — aria pe linia produsului, în Elemente jurnal](screenshots/08_factura_furnizor_valuation_area.png)

### Pasul 9 — Factura de client: liniile de descărcare a costului

În demo, 3 buc au fost livrate întâi din **DC/Raft magazin** printr-o livrare manuală (**Inventar →
Operații → Transferuri → Livrări**), fără comandă de vânzare; livrarea nu generează notă (locația
client nu are cont propriu), descărcarea se face prin factură.

**Facturare → Clienți → Facturi**, factura postată, tab-ul **Elemente jurnal**. Pentru un produs
cu evaluare perpetuă, Odoo 20 adaugă la postare liniile de descărcare a costului: **Dr 607** (contul
de cheltuială al categoriei) / **Cr 371**, la costul produsului. Aceste linii primesc aria, ca și
linia de venit 707 (orice linie cu produs): aria livrării comenzii de vânzare legate sau, fără
comandă, aria implicită. În captură: 3 buc vândute cu 150 lei, descărcare la cost 3 × 20 = 60 lei,
aria **[STD]** pe liniile 707, 371 și 607.

**Atenție la cantitate:** pe liniile de descărcare cantitatea este cea facturată, **pozitivă pe
ambele linii** (+3 și pe 371, și pe 607); modulul pune semnul doar pe notele generate din
mișcările de stoc (pasul 6). Cantitatea nu are coloană în lista liniilor; o verificați deschizând
linia din **Elemente jurnal**, ca la pasul 7.

![Factură de client — liniile de descărcare 607/371 cu aria](screenshots/09_factura_client_descarcare.png)

**Note contabile manuale.** De la versiunea 20.0.1.0.4, lista **Elemente jurnal** a unei note
contabile introduse manual are coloanele opționale **Produs**, **Cantitate**, **UM** și **Arie de
evaluare** (afișați-le din meniul coloanelor opționale); o corecție pe arie (de exemplu un sold
inițial) poate purta astfel produsul, cantitatea semnată și aria. Lista generală a elementelor de
jurnal are coloanele opționale **Cantitate** și **Arie de evaluare**.

### Note de monografie și raportare

Modulul **nu schimbă conturile** și nici sumele: notele rămân cele din Odoo standard (sau din
`deltatech_obyc`); modulul adaugă pe linii aria, cantitatea semnată și unitatea de măsură.

| Operațiune (demo) | Debit | Credit | Arie pe linii | Cantitate |
|---|---|---|---|---|
| Plus la inventar, 5 buc × 20 lei, pe DC/Stoc (pasul 6) | 371 Mărfuri 100,00 | 607 Cheltuieli privind mărfurile 100,00 | [DEP] pe ambele | +5 pe 371, −5 pe 607 |
| Lipsă la inventar (sens invers) | 607 | 371 | aria locației sursă | +q pe 607, −q pe 371 |
| Recepție 10 buc × 20 lei pe DC/Raft magazin (pasul 8) | — (fără notă, evaluare la facturare) | — | — | — |
| Factură de furnizor pentru marfa recepționată, 10 buc × 20 lei + TVA 21% (pasul 8) | 371 Mărfuri 200,00 și 4426 TVA deductibilă 42,00 | 401 Furnizori 242,00 | [STD] doar pe linia 371 | 10 (cantitatea facturată) |
| Livrare 3 buc din DC/Raft magazin (pasul 9) | — (fără notă, descărcare la facturare) | — | — | — |
| Factură de client, 3 buc × 150 lei + TVA 21% (pasul 9) | 4111 Clienți 544,50 | 707 Venituri din vânzarea mărfurilor 450,00 și 4427 TVA colectată 94,50 | [STD] pe linia 707 | 3 |
| Descărcarea gestiunii pe aceeași factură (pasul 9) | 607 Cheltuieli privind mărfurile 60,00 | 371 Mărfuri 60,00 | [STD] pe ambele | +3 pe ambele (nesemnată) |

Control demo: sold 371 = 100,00 + 200,00 − 60,00 = 240,00 lei = stocul de 12 buc × 20 lei (cost
mediu AVCO 20 lei/buc).

Contul 607 pe plus/lipsă la inventar vine din contul de pierderi configurat pe locația de
ajustare (o singură valoare pentru ambele sensuri, în Odoo 20); dacă firma folosește alt cont,
modulul nu îl influențează. Nota de stoc la lipsă acoperă doar scoaterea din gestiune: eventuala
ajustare a TVA dedusă pentru lipsurile nejustificate și imputarea lipsurilor către gestionar se
înregistrează separat, conform Codului fiscal (art. 304, ajustarea TVA deduse) și politicii firmei;
nici Odoo, nici modulul nu le generează.

## 7. Legături cu alte module / declarații

| Modul | Rol |
|---|---|
| `stock_account` (Odoo) | generează notele de stoc pe care modulul le completează cu aria |
| `deltatech_stock_valuation` | calculează valoarea și prețul mediu **pe arie** din liniile etichetate; are nevoie de cantitatea semnată; respectă setarea **Păstrează valoarea mișcării la recalcularea retroactivă** pentru ieșirile evaluate la prețul ariei |
| `deltatech_obyc` | determină conturile pe arie + clasă de evaluare și pune nota de stoc pe **Jurnalul de stoc al ariei**; respectă aceeași setare pentru produsele cu clasă de evaluare |

Nu are legătură directă cu declarații ANAF.

**Ce e automat:** aria, cantitatea semnată și unitatea de măsură pe notele de stoc; aria pe
orice linie de factură/notă cu produs (inclusiv liniile de descărcare de pe factura de client);
blocarea liniilor cu produs stocabil fără arie.

**Ce rămâne manual:** definirea ariilor și a jurnalelor; decizia asupra setării **Păstrează
valoarea mișcării la recalcularea retroactivă**; completarea ariei pe fiecare depozit și
pe locațiile interne care au altă arie decât depozitul lor. Pe notele contabile manuale,
produsul, cantitatea, UM și aria se completează din coloanele opționale ale listei **Elemente
jurnal** (vezi pasul 9).

## 8. Verificări pentru consultant

- [ ] compania are bifat **Folosește arii de evaluare** și o **Arie de evaluare** implicită
- [ ] **Păstrează valoarea mișcării la recalcularea retroactivă** este bifată (implicit) sau debifarea ei e decisă și consemnată împreună cu contabilul
- [ ] fiecare arie are **Cod** și, dacă se folosește `deltatech_obyc`, **Jurnal de stoc** al aceleiași companii
- [ ] depozitele evaluate separat au aria completată; locațiile cu altă arie decât depozitul lor o au setată explicit
- [ ] pe o notă de stoc automată (ex. ajustare de inventar), coloana **Arie de evaluare** arată aria locației, pe toate liniile cu produs
- [ ] în **Elemente jurnal**, linia de debit a notei de stoc are **Cantitate** pozitivă, iar linia de credit cantitate negativă, egală în valoare absolută
- [ ] pe o factură de furnizor cu produs stocabil, tab-ul **Elemente jurnal** arată aria pe linia produsului (aria recepției legate sau, fără comandă, aria implicită)
- [ ] la o factură de furnizor creată înaintea recepției, aria de pe linie a fost verificată/corectată înainte de postare
- [ ] pe o factură de client cu produs perpetuu, liniile de descărcare 607/371 au aria completată (cantitatea lor este pozitivă pe ambele linii — comportament cunoscut)
- [ ] utilizatorul care definește ariile are **Contabilitate / Administrator**
- [ ] produsele evaluate pe arii sunt pe **cost mediu (AVCO)**, nu pe FIFO
- [ ] fără `deltatech_obyc`: notele de stoc sunt pe jurnalul de stoc al companiei, indiferent de jurnalul ariei (comportament așteptat)

## 9. Mesaje de eroare frecvente

| Mesaj | Cauză | Remediere |
|---|---|---|
| „Aria de evaluare este obligatorie pentru produsele stocabile. Dacă produsul nu este stocabil, o puteți lăsa necompletată." | pe o linie de notă/factură cu produs stocabil s-a golit **Arie de evaluare**, iar compania folosește ariile | completați aria pe linie |
| „Aria de evaluare nu este definită" | compania folosește ariile, dar nu are arie implicită, iar linia (sau mișcarea) nu găsește arie pe locație/depozit; apare chiar la alegerea oricărui produs (inclusiv serviciu) pe linia unei facturi | alegeți aria implicită în Setări (pasul 1) sau completați aria pe locație/depozit |
| „Locațiile sursă și destinație trebuie să aibă aceeași arie de evaluare pentru mișcările interne." | la validarea unei mișcări (sau a unei linii a ei, de exemplu la putaway pe o sublocație) între două locații interne ale căror arii efective (proprie → depozit → companie) diferă; cu sau fără `deltatech_obyc` (de la versiunea 20.0.1.0.4) | păstrați sursa și destinația în aceeași arie sau treceți transferul printr-o locație de tranzit |

## 10. Capturi de ecran

Capturile din `readme/screenshots/` sunt **generate automat** din `tests/test_screenshots.py`
(mixinul `ScreenshotCase` din `l10n_ro_doc_screenshots`, import defensiv), în **limba română**, pe
„RO Company", în RON, pe planul de conturi RO (`setup_country("ro")`), în ordinea pașilor:

1. `01_setari_use_valuation_area.png` — Setări Inventar, secțiunea Evaluare: bifa, aria implicită și setarea Păstrează valoarea mișcării la recalcularea retroactivă.
2. `02_valuation_area_list.png` — lista ariilor cu Cod / Nume / Companie / Jurnal de stoc.
3. `03_valuation_area_form.png` — formularul ariei [STD], cu Cod și Jurnal de stoc evidențiate.
4. `04_depozit_valuation_area.png` — lista depozitelor, coloana Arie de evaluare ([DEP]).
5. `05_locatie_valuation_area.png` — formularul locației DC/Raft magazin, câmpul Arie de evaluare.
6. `06_nota_stoc_automata.png` — nota de stoc automată la plus de inventar (Dr 371 / Cr 607, aria [DEP]).
7. `07_linie_stoc_cantitate.png` — formularul liniei 371 a notei automate: Cantitate 5,00 și Produs.
8. `08_factura_furnizor_valuation_area.png` — factura de furnizor pentru marfa recepționată (Dr 371 200 + 4426 42 / Cr 401 242), aria [STD] pe linia produsului.
9. `09_factura_client_descarcare.png` — factura de client cu liniile de descărcare (Dr 607 / Cr 371), aria [STD] pe liniile cu produs.

Regenerare:

```bash
.venv/bin/python odoo/odoo-bin -c odoo.conf -d <db> -i l10n_ro,deltatech_valuation_area,l10n_ro_doc_screenshots \
    --without-demo=all --test-tags=fise_screenshots --stop-after-init --http-port=8170
```

## 11. Observații pentru manual

- **Terminologie:** de la versiunea 20.0.1.0.4 interfața RO folosește peste tot „arie de evaluare"
  (meniul **Arii de evaluare**, bifa din Setări, mesajele de eroare); pe bazele existente,
  traducerile se reîncarcă la actualizarea modulului.
- **Transferurile interne directe între arii diferite sunt refuzate** la validare (de la versiunea
  20.0.1.0.4, cu sau fără `deltatech_obyc`). Înainte, fără `deltatech_obyc`, un astfel de transfer
  trecea fără eroare, iar valoarea rămânea pe aria sursă (verificat pe Odoo 20, la 01.10.2026);
  verificați transferurile vechi. Ruta prin tranzit nu a fost verificată pe o bază de test. Suportul complet pentru transferuri între arii este planificat (roadmap evaluare
  pe depozit).
- **Aria depozitului** se aplică, de la versiunea 20.0.1.0.4, tuturor mișcărilor pe locațiile lui
  interne. Înainte, ajustările de inventar și transferurile manuale cădeau pe aria implicită a
  companiei dacă locația de stoc nu avea arie proprie (VA-001); verificați notele de inventar
  anterioare pe bazele configurate doar pe depozit.
- **Jurnalul de stoc al ariei** are efect doar cu `deltatech_obyc` și doar pentru produsele cu
  clasă de evaluare OBYC.
- Modulul este infrastructură: nu livrează singur rapoarte valorice; valoarea pe arie o calculează
  `deltatech_stock_valuation`.
- Metoda suportată este **AVCO**; produsele pe FIFO nu sunt compatibile cu evaluarea pe arii.
- **Păstrează valoarea mișcării la recalcularea retroactivă** există doar în Odoo 20 și are efect
  doar cu `deltatech_stock_valuation` sau `deltatech_obyc`. În manual, prezentați-o ca setare de
  contabil: bifată = valori stabile, egale cu notele postate (ca în Odoo 19); debifată = reluarea
  standard Odoo 20, cu risc de diferențe între valoarea stocului și contabilitate.
- Unele etichete din Odoo 20 standard sau din localizare nu au traducere RO (ex. evaluarea
  categoriei „Perpetual (at invoicing)", „Average Cost (AVCO)", butoanele „Journal Items” și „No
  Review” de pe documentele contabile, grilele fiscale „TAX BASE” / „VAT”); manualul le poate cita
  așa cum apar.
- Capturile documentelor contabile (pașii 6–9) sunt făcute din aplicația Inventar; în meniul
  Facturare ecranele sunt identice.
