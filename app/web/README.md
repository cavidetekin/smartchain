# app/web

Arayüz (React + TypeScript, Vite). Kurallar: `docs/12-on-yuz.md`, K-81–K-83.

```
npm ci          # paketler (package-lock.json'daki sürümler)
npm run dev     # http://localhost:5173; /api ve /api/ws 127.0.0.1:8000'deki API'ye gider
npm test        # vitest
npm run build   # dist/ (installer/build.ps1 pakete web\ olarak koyar)
```

- `src/screens/catalog.ts`: menünün ve ekranların tek tanımı
- `src/shell/`: kabuk (kenar menü, bağlam çubuğu, iş göstergesi, kullanıcı menüsü)
- `src/i18n/tr.ts`: bütün metinler · `src/format.ts`: Türkçe sayı ve tarih
- `src/styles/`: palet ve kabuk düzeni (1.2'de stil sistemi)
