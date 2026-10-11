## 19.0.1.0.0 (2026-10-05)

- Migrare din 18.0. Propagarea se face acum din `stock.move._set_value`, deci acoperă și factura de
  furnizor și modificarea prețului din comandă, nu doar landed cost-ul.
- Repartizarea pe loturi ia în calcul doar cantitatea din recepție rămasă în stoc, chiar dacă același
  lot a mai intrat și pe alte recepții.
- Nota contabilă a landed cost-ului capitalizează în contul de stoc partea din recepție rămasă pe loturi,
  nu restul FIFO pe produs calculat de nucleu. Când se livrează un lot din altă recepție decât cea cu
  landed cost, contabilitatea și prețul lotului rămân astfel la aceeași sumă.
