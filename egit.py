import pandas as pd
from sklearn.preprocessing import LabelEncoder
import xgboost as xgb
import pickle

print("Yapay zeka verileri okuyor ve öğreniyor... Lütfen bekleyin. 🧠")

# 1. Az önce oluşturduğumuz Veri setini yükle
df = pd.read_csv('Dipol_Turizm_Kapsamli_Veri.csv')

# 2. Yazıları sayıya çevir (Yapay zeka metin anlamaz, sadece sayılardan anlar)
le_dict = {}
kategorik_sutunlar = ['Cinsiyet', 'Tatil_Turu', 'Atmosfer', 'Grup_Tipi', 'Yeme_Icme', 'Cevre', 'Konaklama_Tipi', 'Onerilen_Yer']

for sutun in kategorik_sutunlar:
    le = LabelEncoder()
    df[sutun] = le.fit_transform(df[sutun])
    le_dict[sutun] = le

# 3. Giriş ve Çıkış verilerini ayır
X = df.drop(['Onerilen_Yer', 'Gecelik_Fiyat_TL'], axis=1) # Bütçe ve anket cevaplarına bakarak...
y = df['Onerilen_Yer'] # ...hangi tatil yerinin uygun olacağını tahmin et.

# 4. Yapay Zekayı Eğit (XGBoost algoritması ile)
model = xgb.XGBClassifier(use_label_encoder=False, eval_metric='mlogloss')
model.fit(X, y)

# 5. Eğitilmiş Beyni Kaydet (Bunu web sitemizin arkasına bağlayacağız)
with open('tatil_modeli.pkl', 'wb') as f:
    pickle.dump(model, f)

with open('ceviriciler.pkl', 'wb') as f:
    pickle.dump(le_dict, f)

print("İşlem Tamam! Yapay zeka tüm verileri öğrendi ve 'tatil_modeli.pkl' dosyası olarak kaydedildi. Artık çok zeki! 🚀")