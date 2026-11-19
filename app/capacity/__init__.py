"""Kapasite yönetimi (K-185, ekran 30, fonksiyon 24): geçerlilik kuralı, hesap ve tetikleyiciler.

Girişler `param` şemasındadır (çalışma düzeni, verimlilik, ek mesai limiti, bakım ve duruş, fabrika takvimi); senaryonun geçerli satırları
`app/params/resolve.py` ile çözülür. Hesap kaynak grubu × kaynak × gün tanesindedir; önbellek (`app/periods/cache.py`) bu hesapla kurulur,
motor aynı hesabı doğrudan okur (`app.periods.values`).
"""
