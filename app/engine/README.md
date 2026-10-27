# app/engine

Planlama motoru. Sözleşme: `docs/09-motor-arayuzu.md`.

- `interface.py`: sabit arayüz (EngineInput, PlanningData, Engine, PlanResult)
- `fake.py`, `fixtures/plan_v0.json`: sahte motor (0.5); gerçek motor Aşama 10'da `build_engine`'de devreye girer
- `data.py`: salt okunur veri erişimi (core.*, veri versiyonuna göre)
- `loader.py` → `job.py` (iş süreci) → `writer.py` (tek işlemde yazma, K-70)
- `service.py`: motor servisi (üst süreç; kalp atışı, süre bütçesi, çöküş, K-71)
- `submit.py`: plan hesabı isteği (PlanRun + iş)

Aşama 10'da eklenecekler: prep (ön hesap), mrp, model, solvers (adaptörler), post (son hesap), warnings, metrics.
