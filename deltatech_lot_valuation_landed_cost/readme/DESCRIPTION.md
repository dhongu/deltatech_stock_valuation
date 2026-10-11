Modul-punte între evaluarea pe loturi (`deltatech_lot_valuation`) și modificările de valoare ale
recepțiilor. Când valoarea unei recepții se schimbă după validare, diferența se repartizează pe
loturile ei și modifică prețul lotului (`Unit Price`, `Inventory value`), cu o notă în chatter-ul lotului.

Surse de modificare acoperite, printr-un singur mecanism (`stock.move._set_value`):

- **Landed cost** validat pe recepție.
- **Factura de furnizor** postată cu alt preț decât cel al recepției.
- **Prețul din comanda de achiziție** modificat după recepție, și valoarea manuală a mișcării.

Se ajustează doar cantitatea din recepție care mai este în stoc; partea deja livrată nu mai modifică
prețul lotului. Schimbarea cantității unei recepții nu modifică prețul unitar al lotului.

Landed cost-ul urmează stocul real: partea din recepție care se află efectiv în stoc, pe loturi, se
capitalizează (în prețul lotului și în contul de stoc), iar restul rămâne pe cheltuială. Nucleul Odoo
stabilește restul recepției FIFO, pe produs, ceea ce nu coincide cu loturile livrate în altă ordine.
