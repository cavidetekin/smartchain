// Bütün arayüz metinleri tek yerde (K-81). Faz 1'de yalnız Türkçe.

export const tr = {
  app: { name: "Smartchain" },
  menu: {
    search: "Ekran ara",
    searchHint: "Ctrl+K",
    noResults: "Eşleşen ekran yok",
    collapse: "Menüyü daralt",
    expand: "Menüyü aç",
    needsWorkspace: "Önce bir çalışma açın",
    groups: {
      planlama: "Planlama",
      takip: "Takip",
      veri: "Veri",
      parametre: "Parametre",
      yonetim: "Yönetim",
    },
  },
  context: {
    scenario: "Senaryo",
    planVersion: "Plan versiyonu",
    bucket: "Dönem",
    notYet: "Senaryo ve dönem seçimi 8.1'de gelir",
    dataVersion: (id: number, when: string) => `Veri v${id} · ${when}`,
    noData: "Veri yüklenmedi",
    apiDown: "API'ye ulaşılamıyor",
    dbDown: "Veritabanına ulaşılamıyor",
  },
  jobs: {
    title: "Arka plandaki işler",
    none: "İş yok",
    count: (running: number, queued: number) =>
      running + queued === 0 ? "İş yok" : `${running} çalışıyor · ${queued} sırada`,
    empty: "Son 24 saatte iş yok",
    queuePosition: (n: number) => `sıra ${n}`,
    connection: {
      connected: "Bildirimler bağlı",
      reconnecting: "Bağlantı yeniden kuruluyor",
      polling: "Yedek mod: 30 sn'de bir sorgulanıyor",
    },
  },
  user: {
    label: (id: number) => (id ? `Kullanıcı #${id}` : "Kullanıcı seçilmedi"),
    temporary: "Geçici kullanıcı; oturum 2.1'de gelir. Adres çubuğunda ?user_id= ile verilir.",
    fontSize: "Yazı boyutu",
    fontSizes: { 12: "Küçük", 13: "Standart", 14: "Rahat", 16: "Büyük" } as Record<number, string>,
    logout: "Çıkış",
    logoutLater: "Oturum 2.1'de gelir",
  },
  screen: {
    number: (no: string) => `Ekran ${no}`,
    comingIn: (step: string) => `Bu ekran ${step} adımında gelecek.`,
    notFound: "Sayfa bulunamadı",
    notFoundHint: "Adresi kontrol edin ya da menüden bir ekran seçin.",
    backHome: "Ana sayfaya dön",
  },
};
