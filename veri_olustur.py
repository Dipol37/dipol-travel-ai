import pandas as pd
import random

print("Dipol Turizm için kapsamlı Yurt İçi ve Yurt Dışı veri seti oluşturuluyor, lütfen bekleyin...")

# Anket Seçeneklerimiz
cinsiyet_listesi = ['Kadın', 'Erkek']
kisi_sayisi_listesi = [1, 2, 3, 4, 5, 6]
tatil_turu_listesi = ['Doğa', 'Deniz', 'Orman', 'Macera', 'Kültür']
atmosfer_listesi = ['Sessiz', 'Eğlenceli', 'Aktif', 'Gece Hayatı', 'Sessiz ve Aktif']
grup_tipi_listesi = ['Aile (Bebekli)', 'Aile (Çocuksuz)', 'Balayı', 'Arkadaş Grubu', 'Tek Kişi']
yeme_icme_listesi = ['Her Şey Dahil', 'Sadece Kahvaltı', 'Yemeksiz']
cevre_listesi = ['Havuz', 'Deniz', 'Orman', 'Ada', 'Dağ']
konaklama_listesi = ['Otel', 'Bungalov', 'Airbnb', 'Villa']

# KAPSAMLI YERLER VE ORTALAMA GECELİK FİYATLAR
yerler_ve_fiyatlar = [
    ('Antalya - Kaş (Deniz/Eğlence)', 3500), 
    ('Muğla - Fethiye (Deniz/Macera)', 4000), 
    ('Rize - Ayder (Doğa/Orman)', 2500), 
    ('Nevşehir - Kapadokya (Macera/Balayı)', 3500), 
    ('Bolu - Yedigöller (Doğa/Sessiz)', 2000), 
    ('İzmir - Alaçatı (Eğlence/Gece Hayatı)', 4500),
    ('Antalya - Olympos (Doğa/Bungalov)', 1500),
    ('Maldivler (Lüks/Ada/Balayı)', 25000), 
    ('Bali - Endonezya (Doğa/Egzotik)', 15000),
    ('Phuket - Tayland (Ada/Aktif)', 12000), 
    ('Santorini - Yunanistan (Deniz/Balayı)', 9000),
    ('Seyşeller (Lüks/Ada)', 28000), 
    ('İsviçre Alpleri (Dağ/Doğa)', 18000), 
    ('Norveç Fiyortları (Doğa/Macera)', 20000),
    ('Kenya - Masai Mara Safari (Macera/Orman)', 16000), 
    ('Machu Picchu - Peru (Macera/Kültür)', 14000),
    ('İbiza - İspanya (Gece Hayatı/Deniz)', 12000), 
    ('Amsterdam - Hollanda (Eğlence/Aktif)', 8000),
    ('Mykonos - Yunanistan (Gece Hayatı)', 11000), 
    ('Las Vegas - ABD (Gece Hayatı/Eğlence)', 15000)
]

veriler = []

for i in range(500):
    cinsiyet = random.choice(cinsiyet_listesi)
    kisi_sayisi = random.choice(kisi_sayisi_listesi)
    tatil_turu = random.choice(tatil_turu_listesi)
    atmosfer = random.choice(atmosfer_listesi)
    grup_tipi = random.choice(grup_tipi_listesi)
    yeme_icme = random.choice(yeme_icme_listesi)
    cevre = random.choice(cevre_listesi)
    konaklama = random.choice(konaklama_listesi)
    
    secilen_yer_fiyat = random.choice(yerler_ve_fiyatlar)
    onerilen_yer = secilen_yer_fiyat[0]
    gecelik_fiyat = secilen_yer_fiyat[1] + random.randint(-1000, 2500) 
    butce = gecelik_fiyat + random.randint(-2000, 5000)

    veriler.append([cinsiyet, kisi_sayisi, tatil_turu, atmosfer, grup_tipi, yeme_icme, cevre, konaklama, butce, onerilen_yer, gecelik_fiyat])

sutunlar = ['Cinsiyet', 'Kisi_Sayisi', 'Tatil_Turu', 'Atmosfer', 'Grup_Tipi', 'Yeme_Icme', 'Cevre', 'Konaklama_Tipi', 'Butce_TL', 'Onerilen_Yer', 'Gecelik_Fiyat_TL']
df = pd.DataFrame(veriler, columns=sutunlar)

dosya_adi = 'Dipol_Turizm_Kapsamli_Veri.csv'
df.to_csv(dosya_adi, index=False, encoding='utf-8-sig')

print(f"Mükemmel! '{dosya_adi}' adında tüm dünyayı kapsayan 500 satırlık dev veri setin başarıyla oluşturuldu! 🌍✈️")