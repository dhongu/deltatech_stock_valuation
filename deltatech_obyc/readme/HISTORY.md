## 19.0.1.0.1 (2026-08-19)

- Fix: mișcările dropship (supplier -> customer) pentru produsele cu clasă de evaluare OBYC nu
  erau valorizate — `stock.move.value` rămânea 0, deoarece core-ul `stock_account` completează
  acest câmp doar pentru mișcările `is_in`, nu și pentru `is_dropship`. Nota contabilă generată
  imediat după era postată cu debit=0/credit=0 — aparent înregistrată, dar fără valoare.
