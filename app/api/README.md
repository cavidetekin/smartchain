# app/api

FastAPI uygulaması. Kurallar: `docs/08-api.md`.

- `main.py`: uygulama (`create_app`)
- `settings.py`: ayarlar (`SMARTCHAIN_*`, `.env`)
- `logging_setup.py`, `middleware.py`: log ve takip numarası
- `errors.py`: tek tip hata cevabı, `AppError`
- `db.py`: veritabanı oturumu
- `notify.py`: WebSocket bağlantıları ve iş kuyruğu izleyicisi (K-69)
- `routers/` → `services/` → `repositories/` (iş kuyruğu için `app/jobs/`)
