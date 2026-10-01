# Ce e nou în 19.0 — Evaluarea stocului

## Funcționalități noi
- **Arii de evaluare, activabile per companie.** Poți urmări valoarea stocului separat pe arii (de exemplu pe depozit sau pe linie de business), cu propagarea automată a ariei pe mișcările de stoc și pe notele contabile aferente.
- **Prețuri pe arie de evaluare**, definite la nivel de categorie de produs, cu avertizare când metoda de cost aleasă (FIFO) nu este compatibilă cu acest mod de lucru.
- **Reevaluare pe pași, cu procesare incrementală.** Recalcularea nu mai e o operațiune „totul sau nimic": se face în pași, poate fi resetată și repornită, poate rula automat, iar progresul e vizibil în timpul rulării — esențial pe baze cu istoric mare.
- **Raport de verificare a balanței**, care confruntă valoarea stocului cu soldurile contabile și scoate la iveală diferențele înainte să le găsească auditorul.
- **Cantitățile apar pe notele contabile** generate de mișcările de stoc, deci o notă poate fi verificată fără să deschizi documentul-sursă.

## Îmbunătățiri
- **Recalculări sensibil mai rapide** pe bazele cu istoric lung, prin optimizarea interogărilor de construire a istoricului de evaluare.
- **Mesaje de eroare inteligibile** în locul erorilor tehnice atunci când lipsește configurarea necesară.
- **Unicitatea evaluării per produs este garantată din nou** la nivel de bază de date, cu deduplicarea automată a înregistrărilor rămase din versiunile anterioare.
