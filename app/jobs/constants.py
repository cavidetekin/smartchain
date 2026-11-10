"""adm.Job değerleri; veri modelinde (docs/02) yazıldığı gibi saklanır (K-67)."""

STATUS_QUEUED = "Sırada"
STATUS_RUNNING = "Çalışıyor"
STATUS_DONE = "Bitti"
STATUS_FAILED = "Hata"
STATUS_CANCELLED = "İptal"
STATUSES = (STATUS_QUEUED, STATUS_RUNNING, STATUS_DONE, STATUS_FAILED, STATUS_CANCELLED)
ACTIVE_STATUSES = (STATUS_QUEUED, STATUS_RUNNING)

CHANNEL_NIGHT = "Gece"
CHANNEL_INTERACTIVE = "Hesaplama"
CHANNEL_EXCEL = "Excel"  # K-93, K-129: dışa aktarım ve ön kontrol; kendi sınırı, yeniden hesabı bekletmez
CHANNEL_PULL = "Veri çekme"  # K-130: elle ve gece çekim; aynı anda tek çekim
CHANNEL_PROCESSING = "Veri işleme"  # K-134: rules, tablo içi ve tablolar arası validasyon
CHANNELS = (CHANNEL_INTERACTIVE, CHANNEL_NIGHT, CHANNEL_EXCEL, CHANNEL_PULL, CHANNEL_PROCESSING)

TYPE_NIGHT_SCENARIO = "Gece senaryosu"
TYPE_WORKSPACE = "Çalışma"
TYPE_TRANSFER = "Aktarım"  # staging → core (K-152, K-153)
TYPE_DATE_QUERY = "Termin sorgusu"
TYPE_EXPORT = "Dışa aktarım"  # K-91, K-93: motor servisi Excel dosyası üretir
TYPE_PRECHECK = "Excel ön kontrol"  # K-129: motor servisi yüklenen dosyayı kontrol eder
TYPE_PULL = "Veri çekme"  # K-130: motor servisi view'ları okur, stg'ye yazar
TYPE_VALIDATION = "Validasyon"  # K-134: staging'in güncel hâlinde rules → validation
JOB_TYPES = (TYPE_NIGHT_SCENARIO, TYPE_WORKSPACE, TYPE_TRANSFER, TYPE_DATE_QUERY, TYPE_EXPORT, TYPE_PRECHECK, TYPE_PULL, TYPE_VALIDATION)
