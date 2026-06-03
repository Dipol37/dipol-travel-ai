from flask import Flask, render_template, request, render_template_string
from database import veritabani_olustur, favori_ekle, favorileri_getir, favorileri_temizle, plan_ekle, planlari_getir
from jinja2 import TemplateNotFound
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
from openai import OpenAI
from google import genai
from google.genai import types
import requests
import os
import math
import random
import unicodedata
import base64
import json

load_dotenv()
app = Flask(__name__)
veritabani_olustur()

# =====================================================
# DiPol Travel AI - Profesyonel Final app.py
# Sistemler:
# 1) Akıllı Tatil Formu: /tatil-formu -> /tatil-sonuc
# 2) Destinasyon Planı: /destinasyonlar -> /hizli-plan -> /hizli-sonuc
# 3) Fotoğraftan Konum: /foto-konum -> /foto-sonuc
# Canlı veri:
# - Open-Meteo canlı hava durumu
# - Frankfurter canlı döviz kuru
# - Gün doğumu / gün batımı / nem / rüzgar / min-max sıcaklık
# Bütçe:
# - Konaklama, ulaşım, yeme-içme, aktivite, ekstra pay
# - Toplam, kişi başı, günlük kişi başı
# =====================================================


# -----------------------------------------------------
# Yardımcılar
# -----------------------------------------------------

def tr_key(text):
    text = str(text or "").strip().lower()
    text = text.replace("ı", "i").replace("İ", "i")
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return text


def para_format(tutar, para="₺"):
    try:
        tutar = int(round(float(tutar)))
    except Exception:
        tutar = 0
    metin = f"{tutar:,}".replace(",", ".")
    return f"₺{metin}" if para == "₺" else f"{para}{metin}"


def guvenli_int(deger, varsayilan, minimum, maksimum):
    try:
        sayi = int(deger)
    except (TypeError, ValueError):
        sayi = varsayilan
    return max(minimum, min(sayi, maksimum))


def safe_render(template_name, **context):
    # Sonu? sayfas? a??l?nca plan? otomatik veritaban?na kaydet
    if template_name == "sonuc.html" and context.get("sonuc"):
        try:
            plan_ekle(
                yer=context.get("sonuc", ""),
                toplam_ucret=context.get("butce_detay", {}).get("toplam", ""),
                kisi_basi=context.get("butce_detay", {}).get("kisi_basi", ""),
                gunluk_kisi_basi=context.get("butce_detay", {}).get("gunluk_kisi_basi", ""),
                ulasim=context.get("ulasim_secimi", ""),
                konaklama=context.get("konaklama_secimi", ""),
                kisi=context.get("kisi", 1),
                gun=context.get("gun", 1),
                butce_durumu=context.get("butce_durumu", "")
            )
        except Exception as e:
            print("Plan veritaban?na kaydedilemedi:", e)

    try:
        return render_template(template_name, **context)
    except TemplateNotFound:
        return render_template_string(f"""
        <!doctype html><html lang="tr"><head><meta charset="utf-8">
        <meta name="viewport" content="width=device-width,initial-scale=1">
        <title>DiPol Travel AI</title>
        <style>
        body{{margin:0;min-height:100vh;background:#06142b;color:white;font-family:Arial;display:flex;align-items:center;justify-content:center;text-align:center;padding:28px}}
        .card{{max-width:780px;background:rgba(255,255,255,.10);border:1px solid rgba(255,255,255,.18);border-radius:28px;padding:34px}}
        a{{display:inline-block;margin:8px;padding:13px 18px;border-radius:15px;background:linear-gradient(90deg,#8b5cff,#00d4ff);color:white;text-decoration:none;font-weight:bold}}
        </style></head><body><div class="card">
        <h1>DiPol Travel AI</h1>
        <p><b>{template_name}</b> dosyası bulunamadı ama sistem çalışıyor.</p>
        <p>templates klasörüne bu HTML dosyasını ekleyince özel tasarım açılır.</p>
        <a href="/">Ana Sayfa</a><a href="/tatil-formu">Akıllı Form</a><a href="/destinasyonlar">Destinasyonlar</a>
        </div></body></html>
        """, **context)


# -----------------------------------------------------
# 1) Veri Seti
# -----------------------------------------------------

DESTINASYONLAR = {}
OTEL_VERILERI = {}
GEZILECEK_YERLER = {}
GUNLUK_ROTALAR = {}

def destinasyon_ekle(ad, konum, para, kod, lat, lon, gunluk, etiketler, aciklama, rota, yol, aktiviteler, otel_ismi, telefon="+90 000 000 00 00", bolge="", ulke="Türkiye"):
    DESTINASYONLAR[ad] = {
        "konum": konum,
        "para": para,
        "kod": kod,
        "lat": lat,
        "lon": lon,
        "gunluk": int(gunluk),
        "etiketler": etiketler,
        "aciklama": aciklama,
        "rota": rota,
        "yol": yol,
        "aktiviteler": aktiviteler,
        "otel": {"isim": otel_ismi, "telefon": telefon},
        "bolge": bolge,
        "ulke": ulke
    }

    if ad not in OTEL_VERILERI:
        gece1 = int(gunluk * 0.95)
        gece2 = int(gunluk * 1.80)
        tip = "Şehir Oteli"
        if any(x in etiketler for x in ["deniz", "balayi", "lux", "resort"]):
            tip = "Resort / Butik Otel"
        elif any(x in etiketler for x in ["doga", "yayla", "bungalov", "kamp"]):
            tip = "Bungalov / Doğa Oteli"
        elif any(x in etiketler for x in ["kultur", "tarih"]):
            tip = "Butik / Kültür Oteli"

        OTEL_VERILERI[ad] = [
            {
                "isim": otel_ismi,
                "tip": tip,
                "paket": "Kahvaltı Dahil",
                "fiyat": f"{para_format(gece1, para)} - {para_format(gece2, para)} / gece",
                "puan": "4.6",
                "foto": "https://images.unsplash.com/photo-1566073771259-6a8506099945",
                "link": f"https://www.google.com/maps/search/{ad}+otel"
            },
            {
                "isim": f"{ad} Premium Stay",
                "tip": "Premium Otel",
                "paket": "Oda + Kahvaltı",
                "fiyat": f"{para_format(int(gunluk*1.25), para)} - {para_format(int(gunluk*2.35), para)} / gece",
                "puan": "4.7",
                "foto": "https://images.unsplash.com/photo-1551882547-ff40c63fe5fa",
                "link": f"https://www.google.com/maps/search/{ad}+premium+otel"
            }
        ]

    noktalar = [x.strip() for x in rota.split("→") if x.strip()]
    while len(noktalar) < 3:
        noktalar.append(f"{ad} Merkez")
    GEZILECEK_YERLER[ad] = [
        {"isim": noktalar[0], "zaman": "Sabah", "tur": "Gezi & Fotoğraf", "aciklama": f"{noktalar[0]}, {ad} rotasında öne çıkan ilk duraklardan biridir.", "link": f"https://www.google.com/maps/search/{noktalar[0]}"},
        {"isim": noktalar[1], "zaman": "Öğle", "tur": "Keşif & Deneyim", "aciklama": f"{noktalar[1]}, {ad} planında keşif ve mola için uygundur.", "link": f"https://www.google.com/maps/search/{noktalar[1]}"},
        {"isim": noktalar[2], "zaman": "Akşamüstü", "tur": "Manzara & Dinlenme", "aciklama": f"{noktalar[2]}, günü tamamlamak için güzel bir noktadır.", "link": f"https://www.google.com/maps/search/{noktalar[2]}"}
    ]

    GUNLUK_ROTALAR[ad] = [
        {"gun": "1. Gün", "sabah": f"{noktalar[0]} çevresinde başlangıç ve kahvaltı", "ogle": f"{noktalar[1]} gezisi ve öğle molası", "aksam": f"{noktalar[2]} ve serbest zaman"},
        {"gun": "2. Gün", "sabah": f"{ad} merkezde kısa yürüyüş", "ogle": aktiviteler, "aksam": "Manzara noktası, akşam yemeği ve dönüş hazırlığı"}
    ]


# Özel ve detaylı Türkiye destinasyonları
DETAYLI = [
    ("Kaş","turkiye","₺","TRY",36.1999,29.6414,3900,["deniz","doga","dinlenmek","kesif","otel"],"Kaş deniz, tekne turu ve sakin tatil isteyenler için güçlü bir rotadır.","Kaputaş Plajı → Kaş Merkez → Antiphellos Antik Tiyatro","Antalya üzerinden ulaşım sağlanır.","Tekne turu • Dalış • Plaj • Gün batımı","Kaş Deniz Manzaralı Butik Otel","Akdeniz","Türkiye"),
    ("Kalkan","turkiye","₺","TRY",36.2651,29.4137,4700,["deniz","lux","romantik","premium"],"Kalkan lüks, sakin ve romantik deniz tatili isteyenlere uygundur.","Kalkan Marina → Patara Plajı → Kaputaş","Antalya üzerinden ulaşım sağlanır.","Marina • Plaj • Gün batımı • Şık restoranlar","Kalkan Premium Hotel","Akdeniz","Türkiye"),
    ("Antalya","turkiye","₺","TRY",36.8969,30.7133,4200,["deniz","eglence","lux","aile"],"Antalya sahil, otel, şehir ve eğlence imkanlarını birlikte sunar.","Kaleiçi → Konyaaltı → Lara","Türkiye'nin birçok şehrinden ulaşım kolaydır.","Plaj • Kaleiçi • Şehir turu • Eğlence","Antalya Resort Hotel","Akdeniz","Türkiye"),
    ("Alanya","turkiye","₺","TRY",36.5444,31.9954,3600,["deniz","eglence","aile","otel"],"Alanya ekonomik ve hareketli deniz tatili isteyenlere uygundur.","Kleopatra Plajı → Alanya Kalesi → Damlataş Mağarası","Antalya üzerinden ulaşım sağlanır.","Plaj • Kale • Mağara • Sahil yürüyüşü","Alanya Beach Hotel","Akdeniz","Türkiye"),
    ("Bodrum","turkiye","₺","TRY",37.0344,27.4305,5200,["deniz","eglence","lux","otel","premium"],"Bodrum lüks, deniz, marina ve gece hayatı isteyenler için öne çıkar.","Bodrum Kalesi → Yalıkavak → Gümüşlük","Muğla üzerinden ulaşım sağlanır.","Beach club • Marina • Tekne turu • Gün batımı","Bodrum Premium Resort","Ege","Türkiye"),
    ("Fethiye","turkiye","₺","TRY",36.6592,29.1263,4300,["deniz","doga","macera","kesif"],"Fethiye Ölüdeniz, yamaç paraşütü ve doğa rotalarıyla öne çıkar.","Ölüdeniz → Kayaköy → Kelebekler Vadisi","Muğla üzerinden ulaşım sağlanır.","Yamaç paraşütü • Tekne turu • Plaj • Doğa yürüyüşü","Fethiye Sea View Hotel","Ege","Türkiye"),
    ("Marmaris","turkiye","₺","TRY",36.8550,28.2742,4100,["deniz","eglence","tekne","otel"],"Marmaris tekne turları ve hareketli yaz tatili isteyenlere uygundur.","Marmaris Marina → İçmeler → Turunç","Muğla üzerinden ulaşım sağlanır.","Tekne turu • Sahil yürüyüşü • Gece hayatı","Marmaris Marina Hotel","Ege","Türkiye"),
    ("Datça","turkiye","₺","TRY",36.7276,27.6848,3600,["deniz","sakin","doga","dinlenmek"],"Datça sakin, doğal ve kalabalıktan uzak deniz tatili isteyenlere uygundur.","Eski Datça → Palamutbükü → Knidos","Muğla üzerinden ulaşım sağlanır.","Sakin koylar • Fotoğraf • Sahil yürüyüşü","Datça Sakin Konaklama","Ege","Türkiye"),
    ("Çeşme","turkiye","₺","TRY",38.3228,26.3064,4600,["deniz","eglence","lux","premium"],"Çeşme Alaçatı, plajlar ve yaz eğlencesiyle premium bir rotadır.","Alaçatı → Ilıca Plajı → Çeşme Marina","İzmir üzerinden ulaşım sağlanır.","Plaj • Alaçatı sokakları • Marina • Kafe gezisi","Çeşme Boutique Hotel","Ege","Türkiye"),
    ("Alaçatı","turkiye","₺","TRY",38.2824,26.3746,4800,["deniz","eglence","lux","romantik"],"Alaçatı taş sokaklar, kafeler ve yaz atmosferi isteyenlere uygundur.","Alaçatı Çarşı → Ilıca → Hacımemiş","İzmir üzerinden ulaşım sağlanır.","Kafe • Plaj • Fotoğraf • Akşam gezisi","Alaçatı Boutique Stay","Ege","Türkiye"),
    ("Kapadokya","turkiye","₺","TRY",38.6431,34.8289,4100,["kultur","balayi","romantik","premium"],"Kapadokya balon manzarası, romantik atmosfer ve kültür gezisi için uygundur.","Göreme → Uçhisar → Avanos","Nevşehir üzerinden ulaşım sağlanır.","Balon seyri • ATV • Müze • Gün batımı","Cappadocia Cave Hotel","İç Anadolu","Türkiye"),
    ("Mardin","turkiye","₺","TRY",37.3129,40.7350,2800,["kultur","tarih","romantik","sehir"],"Mardin tarihi taş sokaklar ve kültür gezisi isteyenler için uygundur.","Eski Mardin → Dara Antik Kenti → Midyat","Güneydoğu Anadolu rotasıdır.","Tarihi sokaklar • Yerel lezzetler • Konak gezisi","Mardin Stone Hotel","Güneydoğu Anadolu","Türkiye"),
    ("Ayder Yaylası","turkiye","₺","TRY",40.9527,41.0950,3100,["doga","yayla","bungalov","dinlenmek"],"Ayder doğa, yayla, bungalov ve huzur isteyenlere uygundur.","Fırtına Deresi → Zil Kale → Pokut Yaylası","Rize üzerinden ulaşım sağlanır.","Yayla gezisi • Doğa yürüyüşü • Fotoğraf","Ayder Yayla Bungalov","Karadeniz","Türkiye"),
    ("Uzungöl","turkiye","₺","TRY",40.6190,40.2897,3000,["doga","yayla","sakin","aile"],"Uzungöl göl manzarası ve doğa tatili isteyenler için uygundur.","Uzungöl → Haldizen Yaylası → Seyir Tepesi","Trabzon üzerinden ulaşım sağlanır.","Göl yürüyüşü • Fotoğraf • Yayla gezisi","Uzungöl Lake Hotel","Karadeniz","Türkiye"),
    ("Sapanca","turkiye","₺","TRY",40.6914,30.2674,3500,["doga","bungalov","dinlenmek","haftasonu"],"Sapanca bungalov, göl ve kısa tatil isteyenler için uygundur.","Sapanca Gölü → Maşukiye → Kırkpınar","İstanbul ve Kocaeli çevresinden kolay ulaşım sağlar.","Göl kenarı • Bungalov • Kahvaltı • Doğa yürüyüşü","Sapanca Bungalov Resort","Marmara","Türkiye"),
    ("Abant","turkiye","₺","TRY",40.6036,31.2864,3300,["doga","sakin","kis","dinlenmek"],"Abant göl manzarası, doğa ve sakin tatil isteyenlere uygundur.","Abant Gölü → Gölcük → Yedigöller","Bolu üzerinden ulaşım sağlanır.","Göl yürüyüşü • Fotoğraf • Doğa molası","Abant Göl Oteli","Karadeniz","Türkiye"),
    ("Amasra","turkiye","₺","TRY",41.7463,32.3863,2900,["deniz","sakin","kultur"],"Amasra Karadeniz sahili ve sakin hafta sonu tatili için uygundur.","Amasra Kalesi → Boztepe → Çekiciler Çarşısı","Bartın üzerinden ulaşım sağlanır.","Sahil yürüyüşü • Balık restoranı • Manzara","Amasra Sahil Otel","Karadeniz","Türkiye"),
    ("Cunda","turkiye","₺","TRY",39.3327,26.6598,3500,["deniz","sakin","gastronomi","romantik"],"Cunda sahil, butik sokaklar ve gastronomi isteyenler için uygundur.","Cunda Sokakları → Aşıklar Tepesi → Taksiyarhis","Balıkesir Ayvalık üzerinden ulaşım sağlanır.","Sahil • Kafe • Fotoğraf • Yerel lezzetler","Cunda Butik Otel","Marmara","Türkiye"),
    ("İstanbul","turkiye","₺","TRY",41.0082,28.9784,4600,["sehir","kultur","eglence","premium"],"İstanbul kültür, boğaz, tarihi mekanlar ve şehir tatili için uygundur.","Sultanahmet → Galata → Boğaz","Türkiye’nin birçok şehrinden ulaşım kolaydır.","Müze • Boğaz turu • Kafe • Tarihi sokaklar","İstanbul City Hotel","Marmara","Türkiye"),
    ("İzmir","turkiye","₺","TRY",38.4237,27.1428,3800,["deniz","sehir","eglence","kultur"],"İzmir şehir, sahil, kafe kültürü ve yaz rotaları için uygundur.","Kordon → Alsancak → Alaçatı","Ege bölgesinde merkezi ulaşım noktalarından biridir.","Sahil yürüyüşü • Kafe • Plaj • Şehir gezisi","İzmir Kordon Hotel","Ege","Türkiye"),
    ("Ankara","turkiye","₺","TRY",39.9334,32.8597,3000,["sehir","kultur","tarih"],"Ankara müze, tarih ve şehir gezisi isteyenler için uygundur.","Anıtkabir → Hamamönü → Ankara Kalesi","İç Anadolu merkezli ulaşım sağlar.","Müze • Tarih • Kafe • Şehir gezisi","Ankara City Hotel","İç Anadolu","Türkiye"),
    ("Eskişehir","turkiye","₺","TRY",39.7767,30.5206,2800,["sehir","kultur","eglence"],"Eskişehir genç, hareketli ve kültürel şehir gezisi isteyenlere uygundur.","Odunpazarı → Porsuk Çayı → Sazova Parkı","İç Anadolu içinde kolay ulaşım sağlar.","Şehir turu • Kafe • Müze • Fotoğraf","Eskişehir Boutique Hotel","İç Anadolu","Türkiye"),
]

for d in DETAYLI:
    destinasyon_ekle(*d)

# 81 il temel paket: her il sonuç verebilsin diye otomatik rota/otel/gezilecek yer oluşturulur.
IL_VERILERI = [
    ("Adana",37.0000,35.3213,"Akdeniz",2600,["kultur","gastronomi","sehir"],"Taşköprü → Merkez Park → Sabancı Merkez Camii"),
    ("Adıyaman",37.7648,38.2786,"Güneydoğu Anadolu",2400,["kultur","tarih","kesif"],"Nemrut Dağı → Cendere Köprüsü → Perre Antik Kenti"),
    ("Afyonkarahisar",38.7569,30.5387,"Ege",2300,["termal","kultur","gastronomi"],"Afyon Kalesi → Frig Vadisi → Termal Oteller"),
    ("Ağrı",39.7191,43.0503,"Doğu Anadolu",2200,["doga","kultur","macera"],"İshak Paşa Sarayı → Ağrı Dağı Manzarası → Doğubayazıt"),
    ("Aksaray",38.3687,34.0370,"İç Anadolu",2300,["kultur","doga","tarih"],"Ihlara Vadisi → Hasan Dağı → Sultanhanı"),
    ("Amasya",40.6499,35.8353,"Karadeniz",2400,["kultur","tarih","sehir"],"Yalıboyu Evleri → Kral Kaya Mezarları → Amasya Kalesi"),
    ("Ankara",39.9334,32.8597,"İç Anadolu",3000,["sehir","kultur","tarih"],"Anıtkabir → Hamamönü → Ankara Kalesi"),
    ("Antalya",36.8969,30.7133,"Akdeniz",4200,["deniz","eglence","lux"],"Kaleiçi → Konyaaltı → Lara"),
    ("Ardahan",41.1105,42.7022,"Doğu Anadolu",2100,["doga","kis","kesif"],"Çıldır Gölü → Ardahan Kalesi → Yalnızçam"),
    ("Artvin",41.1828,41.8183,"Karadeniz",2600,["doga","macera","kamp"],"Karagöl → Borçka → Hatila Vadisi"),
    ("Aydın",37.8560,27.8416,"Ege",3300,["deniz","kultur","yaz"],"Kuşadası → Didim → Afrodisias"),
    ("Balıkesir",39.6484,27.8826,"Marmara",3200,["deniz","doga","gastronomi"],"Ayvalık → Cunda → Kaz Dağları"),
    ("Bartın",41.6358,32.3375,"Karadeniz",2600,["deniz","doga","sakin"],"Amasra → İnkumu → Güzelcehisar"),
    ("Batman",37.8812,41.1351,"Güneydoğu Anadolu",2300,["kultur","tarih","kesif"],"Hasankeyf → Malabadi Köprüsü → Batman Müzesi"),
    ("Bayburt",40.2552,40.2249,"Karadeniz",2100,["doga","kultur","sakin"],"Bayburt Kalesi → Aydıntepe Yeraltı Şehri → Çoruh Nehri"),
    ("Bilecik",40.1500,29.9833,"Marmara",2300,["tarih","kultur","sakin"],"Şeyh Edebali Türbesi → Söğüt → Pelitözü Göleti"),
    ("Bingöl",38.8847,40.4939,"Doğu Anadolu",2200,["doga","termal","kesif"],"Yüzen Ada → Kös Kaplıcaları → Hesarek"),
    ("Bitlis",38.4006,42.1095,"Doğu Anadolu",2200,["doga","tarih","kis"],"Nemrut Krater Gölü → Ahlat → Bitlis Kalesi"),
    ("Bolu",40.5760,31.5788,"Karadeniz",3000,["doga","kis","sakin"],"Abant → Yedigöller → Gölcük"),
    ("Burdur",37.7203,30.2908,"Akdeniz",2300,["doga","kultur","sakin"],"Salda Gölü → Sagalassos → Burdur Gölü"),
    ("Bursa",40.1828,29.0663,"Marmara",3400,["kultur","kis","sehir"],"Uludağ → Cumalıkızık → Ulu Camii"),
    ("Çanakkale",40.1553,26.4142,"Marmara",3300,["deniz","tarih","kultur"],"Troya → Bozcaada → Gökçeada"),
    ("Çankırı",40.6013,33.6134,"İç Anadolu",2200,["kultur","doga","sakin"],"Tuz Mağarası → Ilgaz → Çankırı Kalesi"),
    ("Çorum",40.5506,34.9556,"Karadeniz",2300,["tarih","kultur","gastronomi"],"Hattuşa → Alacahöyük → Çorum Müzesi"),
    ("Denizli",37.7765,29.0864,"Ege",3000,["termal","doga","kultur"],"Pamukkale → Hierapolis → Laodikya"),
    ("Diyarbakır",37.9144,40.2306,"Güneydoğu Anadolu",2500,["kultur","tarih","gastronomi"],"Diyarbakır Surları → On Gözlü Köprü → Hevsel Bahçeleri"),
    ("Düzce",40.8438,31.1565,"Karadeniz",2600,["doga","deniz","sakin"],"Akçakoca → Topuk Yaylası → Efteni Gölü"),
    ("Edirne",41.6771,26.5557,"Marmara",2800,["kultur","tarih","gastronomi"],"Selimiye Camii → Meriç Nehri → Karaağaç"),
    ("Elazığ",38.6810,39.2264,"Doğu Anadolu",2300,["doga","kultur","sakin"],"Harput → Hazar Gölü → Buzluk Mağarası"),
    ("Erzincan",39.7500,39.5000,"Doğu Anadolu",2300,["doga","macera","kultur"],"Girlevik Şelalesi → Kemaliye → Ergan Dağı"),
    ("Erzurum",39.9000,41.2700,"Doğu Anadolu",2600,["kis","kultur","tarih"],"Palandöken → Çifte Minareli Medrese → Erzurum Kalesi"),
    ("Eskişehir",39.7767,30.5206,"İç Anadolu",2800,["sehir","kultur","eglence"],"Odunpazarı → Porsuk Çayı → Sazova Parkı"),
    ("Gaziantep",37.0662,37.3833,"Güneydoğu Anadolu",2800,["gastronomi","kultur","tarih"],"Zeugma Müzesi → Bakırcılar Çarşısı → Gaziantep Kalesi"),
    ("Giresun",40.9128,38.3895,"Karadeniz",2500,["doga","deniz","yayla"],"Giresun Adası → Kümbet Yaylası → Mavi Göl"),
    ("Gümüşhane",40.4603,39.4814,"Karadeniz",2300,["doga","tarih","yayla"],"Karaca Mağarası → Santa Harabeleri → Limni Gölü"),
    ("Hakkari",37.5744,43.7408,"Doğu Anadolu",2200,["doga","macera","kis"],"Cilo Dağları → Mergabütan → Zap Vadisi"),
    ("Hatay",36.2028,36.1600,"Akdeniz",2700,["kultur","gastronomi","deniz"],"Antakya → Harbiye → Samandağ"),
    ("Iğdır",39.9237,44.0450,"Doğu Anadolu",2200,["doga","kultur","kesif"],"Tuzluca Tuz Mağarası → Ağrı Dağı Manzarası → Aras Vadisi"),
    ("Isparta",37.7648,30.5566,"Akdeniz",2500,["doga","gol","sakin"],"Eğirdir Gölü → Kovada Gölü → Lavanta Bahçeleri"),
    ("İstanbul",41.0082,28.9784,"Marmara",4600,["sehir","kultur","eglence"],"Sultanahmet → Galata → Boğaz"),
    ("İzmir",38.4237,27.1428,"Ege",3800,["deniz","sehir","eglence"],"Kordon → Alsancak → Alaçatı"),
    ("Kahramanmaraş",37.5753,36.9228,"Akdeniz",2400,["gastronomi","doga","kultur"],"Kapalı Çarşı → Başkonuş Yaylası → Germanicia"),
    ("Karabük",41.2061,32.6204,"Karadeniz",2500,["tarih","kultur","sakin"],"Safranbolu → Kristal Teras → Yenice Ormanları"),
    ("Karaman",37.1811,33.2150,"İç Anadolu",2200,["kultur","tarih","sakin"],"Karaman Kalesi → Taşkale → Manazan Mağaraları"),
    ("Kars",40.6013,43.0975,"Doğu Anadolu",2700,["kis","kultur","tarih"],"Ani Harabeleri → Çıldır Gölü → Kars Kalesi"),
    ("Kastamonu",41.3887,33.7827,"Karadeniz",2500,["doga","tarih","sakin"],"Ilgaz → Valla Kanyonu → Kastamonu Kalesi"),
    ("Kayseri",38.7205,35.4826,"İç Anadolu",2700,["kis","kultur","gastronomi"],"Erciyes → Kayseri Kalesi → Kapalı Çarşı"),
    ("Kırıkkale",39.8468,33.5153,"İç Anadolu",2100,["sakin","kultur","sehir"],"Çeşnigir Köprüsü → Karaahmetli Tabiat Parkı → Merkez"),
    ("Kırklareli",41.7351,27.2252,"Marmara",2600,["doga","deniz","sakin"],"İğneada → Dupnisa Mağarası → Longoz Ormanları"),
    ("Kırşehir",39.1458,34.1606,"İç Anadolu",2200,["kultur","sakin","tarih"],"Cacabey Medresesi → Japon Bahçesi → Seyfe Gölü"),
    ("Kilis",36.7165,37.1147,"Güneydoğu Anadolu",2100,["kultur","gastronomi","sakin"],"Kilis Evleri → Oylum Höyük → Ravanda Kalesi"),
    ("Kocaeli",40.8533,29.8815,"Marmara",3000,["sehir","deniz","doga"],"SEKA Park → Kartepe → Maşukiye"),
    ("Konya",37.8746,32.4932,"İç Anadolu",2500,["kultur","tarih","gastronomi"],"Mevlana Müzesi → Sille → Alaeddin Tepesi"),
    ("Kütahya",39.4192,29.9857,"Ege",2300,["termal","kultur","tarih"],"Aizanoi → Kütahya Kalesi → Termal Kaplıcalar"),
    ("Malatya",38.3552,38.3095,"Doğu Anadolu",2400,["kultur","doga","gastronomi"],"Aslantepe Höyüğü → Levent Vadisi → Orduzu"),
    ("Manisa",38.6191,27.4289,"Ege",2600,["kultur","doga","sehir"],"Spil Dağı → Sardes → Ağlayan Kaya"),
    ("Mardin",37.3129,40.7350,"Güneydoğu Anadolu",2800,["kultur","tarih","romantik"],"Eski Mardin → Dara Antik Kenti → Midyat"),
    ("Mersin",36.8121,34.6415,"Akdeniz",3200,["deniz","kultur","yaz"],"Kızkalesi → Tarsus → Cennet Cehennem"),
    ("Muğla",37.2153,28.3636,"Ege",4500,["deniz","lux","eglence"],"Bodrum → Fethiye → Marmaris"),
    ("Muş",38.9462,41.7539,"Doğu Anadolu",2100,["doga","kultur","sakin"],"Muş Ovası → Murat Köprüsü → Kayalıdere"),
    ("Nevşehir",38.6244,34.7239,"İç Anadolu",3800,["kultur","balayi","romantik"],"Kapadokya → Göreme → Uçhisar"),
    ("Niğde",37.9667,34.6833,"İç Anadolu",2300,["doga","kultur","sakin"],"Aladağlar → Gümüşler Manastırı → Niğde Kalesi"),
    ("Ordu",40.9862,37.8797,"Karadeniz",2600,["doga","deniz","yayla"],"Boztepe → Perşembe Yaylası → Yason Burnu"),
    ("Osmaniye",37.0742,36.2478,"Akdeniz",2200,["doga","kultur","sakin"],"Karatepe Aslantaş → Kastabala → Zorkun Yaylası"),
    ("Rize",41.0201,40.5234,"Karadeniz",3000,["doga","yayla","macera"],"Ayder Yaylası → Fırtına Deresi → Zil Kale"),
    ("Sakarya",40.7569,30.3781,"Marmara",3000,["doga","sakin","haftasonu"],"Sapanca → Acarlar Longozu → Taraklı"),
    ("Samsun",41.2867,36.3300,"Karadeniz",2700,["deniz","sehir","kultur"],"Bandırma Vapuru → Atakum → Amisos Tepesi"),
    ("Siirt",37.9274,41.9453,"Güneydoğu Anadolu",2200,["doga","kultur","gastronomi"],"Tillo → Botan Vadisi → Veysel Karani"),
    ("Sinop",42.0264,35.1551,"Karadeniz",2800,["deniz","sakin","doga"],"Hamsilos → Sinop Cezaevi → Akliman"),
    ("Sivas",39.7477,37.0179,"İç Anadolu",2400,["kultur","tarih","kis"],"Divriği Ulu Camii → Gök Medrese → Yıldız Dağı"),
    ("Şanlıurfa",37.1674,38.7955,"Güneydoğu Anadolu",2600,["kultur","tarih","gastronomi"],"Göbeklitepe → Balıklıgöl → Harran"),
    ("Şırnak",37.4187,42.4918,"Güneydoğu Anadolu",2100,["doga","kultur","kesif"],"Cudi Dağı → Kasrik Boğazı → Merkez"),
    ("Tekirdağ",40.9780,27.5110,"Marmara",2800,["deniz","gastronomi","haftasonu"],"Şarköy → Uçmakdere → Rakoczi Müzesi"),
    ("Tokat",40.3167,36.5500,"Karadeniz",2300,["kultur","tarih","doga"],"Ballıca Mağarası → Tokat Kalesi → Taşhan"),
    ("Trabzon",41.0027,39.7168,"Karadeniz",3000,["doga","yayla","kultur"],"Uzungöl → Sümela Manastırı → Boztepe"),
    ("Tunceli",39.1062,39.5483,"Doğu Anadolu",2300,["doga","macera","sakin"],"Munzur Vadisi → Ovacık → Pülümür"),
    ("Uşak",38.6823,29.4082,"Ege",2200,["doga","kultur","sakin"],"Ulubey Kanyonu → Blaundos → Uşak Müzesi"),
    ("Van",38.5012,43.3729,"Doğu Anadolu",2500,["doga","kultur","gol"],"Akdamar Adası → Van Gölü → Van Kalesi"),
    ("Yalova",40.6500,29.2667,"Marmara",2800,["termal","deniz","haftasonu"],"Termal Kaplıcaları → Sudüşen Şelalesi → Çınarcık"),
    ("Yozgat",39.8181,34.8147,"İç Anadolu",2100,["kultur","doga","sakin"],"Çamlık Milli Parkı → Saat Kulesi → Kazankaya Kanyonu"),
    ("Zonguldak",41.4564,31.7987,"Karadeniz",2600,["deniz","doga","tarih"],"Gökgöl Mağarası → Filyos → Cehennemağzı")
]

for ad, lat, lon, bolge, gunluk, etiketler, rota in IL_VERILERI:
    if ad not in DESTINASYONLAR:
        destinasyon_ekle(
            ad, "turkiye", "₺", "TRY", lat, lon, gunluk, etiketler,
            f"{ad}, {bolge} bölgesinde kullanıcı tercihlerine göre değerlendirilebilecek bir tatil ve gezi rotasıdır.",
            rota,
            "Çıkış şehrine göre mesafe ve süre değişir.",
            "Şehir gezisi • Yerel lezzetler • Fotoğraf noktaları • Serbest zaman",
            f"{ad} Merkez Otel",
            "+90 000 000 00 00",
            bolge,
            "Türkiye"
        )

# Yurt dışı destinasyonları
YURTDISI = [
    ("Paris","Fransa","€","EUR",48.8566,2.3522,160,["kultur","romantik","sehir","balayi"],"Paris sanat, kültür ve romantik şehir tatili için uygundur.","Eyfel Kulesi → Louvre → Montmartre","Uçakla ulaşım önerilir.","Müze • Kafe • Şehir turu • Seine yürüyüşü","Paris City Center Hotel","+33 000 000"),
    ("Roma","İtalya","€","EUR",41.9028,12.4964,145,["kultur","tarih","romantik","sehir"],"Roma tarih, kültür ve Avrupa şehir tatili için uygundur.","Kolezyum → Vatikan → Trevi Çeşmesi","Uçakla ulaşım önerilir.","Müze • Tarihi gezi • Kafe • Şehir yürüyüşü","Roma City Stay","+39 000 000"),
    ("Venedik","İtalya","€","EUR",45.4408,12.3155,165,["romantik","kultur","sehir","balayi"],"Venedik romantik kanallar ve kültür gezisi isteyenler için uygundur.","San Marco → Rialto Köprüsü → Gondol Rotası","Uçak + şehir içi ulaşım önerilir.","Gondol • Tarihi meydan • Fotoğraf","Venice Canal Hotel","+39 000 001"),
    ("Amsterdam","Hollanda","€","EUR",52.3676,4.9041,160,["sehir","kultur","eglence"],"Amsterdam kanal manzarası ve müze gezisi isteyenler için uygundur.","Kanallar → Van Gogh Müzesi → Dam Meydanı","Uçakla ulaşım önerilir.","Kanal turu • Müze • Şehir yürüyüşü","Amsterdam Canal Hotel","+31 000 000"),
    ("Barselona","İspanya","€","EUR",41.3874,2.1686,145,["deniz","sehir","kultur","eglence"],"Barselona deniz, şehir ve kültür tatilini birlikte sunar.","Sagrada Familia → Park Güell → Barceloneta","Uçakla ulaşım önerilir.","Plaj • Mimari • Şehir turu","Barcelona City Hotel","+34 000 000"),
    ("Prag","Çekya","€","EUR",50.0755,14.4378,115,["kultur","romantik","sehir","ekonomik"],"Prag ekonomik Avrupa kültür rotası isteyenler için uygundur.","Charles Köprüsü → Eski Şehir → Prag Kalesi","Uçakla ulaşım önerilir.","Tarihi meydan • Kafe • Fotoğraf","Prague Old Town Hotel","+420 000 000"),
    ("Viyana","Avusturya","€","EUR",48.2082,16.3738,150,["kultur","sehir","sanat"],"Viyana sanat, müzik ve şehir gezisi isteyenler için uygundur.","Schönbrunn → Stephansdom → Belvedere","Uçakla ulaşım önerilir.","Müze • Saray • Kafe","Vienna Art Hotel","+43 000 000"),
    ("Londra","İngiltere","£","GBP",51.5072,-0.1276,190,["sehir","kultur","eglence"],"Londra büyük şehir, kültür ve alışveriş rotası isteyenlere uygundur.","Big Ben → London Eye → British Museum","Uçakla ulaşım önerilir.","Müze • Alışveriş • Şehir turu","London Central Hotel","+44 000 000"),
    ("Atina","Yunanistan","€","EUR",37.9838,23.7275,120,["kultur","tarih","deniz"],"Atina tarih ve yakın Avrupa rotası isteyenler için uygundur.","Akropolis → Plaka → Monastiraki","Uçakla ulaşım önerilir.","Tarih • Kafe • Şehir yürüyüşü","Athens City Hotel","+30 000 000"),
    ("Santorini","Yunanistan","€","EUR",36.3932,25.4615,180,["deniz","romantik","balayi","lux"],"Santorini balayı, deniz ve gün batımı rotası isteyenlere uygundur.","Oia → Fira → Kaldera","Uçak/feribot bağlantısı gerekebilir.","Gün batımı • Deniz • Fotoğraf","Santorini Sunset Hotel","+30 000 001"),
    ("Dubai","BAE","$","USD",25.2048,55.2708,230,["lux","sehir","eglence","premium"],"Dubai lüks, alışveriş ve modern şehir tatili isteyenler için uygundur.","Burj Khalifa → Dubai Mall → Marina","Uçakla ulaşım önerilir.","Alışveriş • Çöl safari • Marina • Lüks otel","Dubai Premium Hotel","+971 000 000"),
    ("Maldivler","Maldivler","$","USD",3.2028,73.2207,380,["deniz","balayi","romantik","lux","resort"],"Maldivler lüks, balayı ve tropik deniz tatili isteyenler için uygundur.","Water Villa → Mercan Resifi → Gün Batımı Sahili","Uçak + ada transferi gerekebilir.","Şnorkel • Resort • Plaj • Gün batımı","Maldives Water Villa Resort","+960 000 000"),
    ("Bali","Endonezya","$","USD",-8.3405,115.0920,130,["deniz","doga","kultur","dinlenmek"],"Bali tropik doğa, deniz ve kültür deneyimi isteyenler için uygundur.","Ubud → Uluwatu → Kuta","Uçakla ulaşım önerilir.","Tapınak gezisi • Plaj • Doğa • Fotoğraf","Bali Tropical Stay","+62 000 000"),
    ("Phuket","Tayland","$","USD",7.8804,98.3923,120,["deniz","eglence","doga"],"Phuket deniz, eğlence ve tropik tatil isteyenler için uygundur.","Patong → Phi Phi → Big Buddha","Uçakla ulaşım önerilir.","Ada turu • Plaj • Şnorkel","Phuket Beach Resort","+66 000 000"),
    ("Tokyo","Japonya","$","USD",35.6762,139.6503,175,["sehir","kultur","teknoloji"],"Tokyo teknoloji, kültür ve şehir deneyimi isteyenler için uygundur.","Shibuya → Asakusa → Tokyo Tower","Uçakla ulaşım önerilir.","Şehir turu • Teknoloji • Kültür","Tokyo City Hotel","+81 000 000"),
    ("Seul","Güney Kore","$","USD",37.5665,126.9780,145,["sehir","kultur","eglence"],"Seul modern şehir ve kültür tatili isteyenlere uygundur.","Gyeongbokgung → Myeongdong → N Seoul Tower","Uçakla ulaşım önerilir.","Alışveriş • Saray • Şehir manzarası","Seoul Stay Hotel","+82 000 000"),
    ("New York","ABD","$","USD",40.7128,-74.0060,230,["sehir","eglence","kultur"],"New York büyük şehir, eğlence ve kültür isteyenler için uygundur.","Times Square → Central Park → Brooklyn Bridge","Uçakla ulaşım önerilir.","Şehir turu • Müze • Alışveriş","New York Central Hotel","+1 000 000"),
    ("Lizbon","Portekiz","€","EUR",38.7223,-9.1393,125,["sehir","deniz","kultur"],"Lizbon ekonomik Avrupa şehir ve deniz havası isteyenlere uygundur.","Belem → Alfama → Tram 28","Uçakla ulaşım önerilir.","Kafe • Tarihi sokak • Manzara","Lisbon Boutique Hotel","+351 000 000"),
]

for ad, ulke, para, kod, lat, lon, gunluk, etiketler, aciklama, rota, yol, aktiviteler, otel, tel in YURTDISI:
    destinasyon_ekle(ad, "yurtdisi", para, kod, lat, lon, gunluk, etiketler, aciklama, rota, yol, aktiviteler, otel, tel, "Yurt Dışı", ulke)


# Dış veri dosyası varsa onu da sessizce ekle. Böylece destinasyon_verileri.py varsa çalışır, yoksa app.py tek başına da çalışır.
try:
    from destinasyon_verileri import DESTINASYONLAR as DIS_DEST, OTEL_VERILERI as DIS_OTEL, GEZILECEK_YERLER as DIS_GEZI, GUNLUK_ROTALAR as DIS_ROTA
    DESTINASYONLAR.update(DIS_DEST)
    OTEL_VERILERI.update(DIS_OTEL)
    GEZILECEK_YERLER.update(DIS_GEZI)
    GUNLUK_ROTALAR.update(DIS_ROTA)
except Exception:
    pass

try:
    from tatil_data import OTELLER
except Exception:
    OTELLER = {"turkiye": [], "yurtdisi": []}


# -----------------------------------------------------
# 2) Canlı Veri Fonksiyonları
# -----------------------------------------------------

def canli_hava_getir(yer):
    yer = yer_duzelt(yer)
    bilgi = DESTINASYONLAR.get(yer)

    if not bilgi:
        return "🌤️ Hava bilgisi bulunamadı"

    lat = bilgi.get("lat")
    lon = bilgi.get("lon")

    if lat is None or lon is None:
        return "🌤️ Bu destinasyon için koordinat bilgisi yok"

    kodlar = {
        0: "☀️ Açık", 1: "🌤️ Genelde açık", 2: "⛅ Parçalı bulutlu", 3: "☁️ Kapalı",
        45: "🌫️ Sisli", 48: "🌫️ Kırağılı sis", 51: "🌦️ Hafif çisenti", 53: "🌦️ Çisenti",
        55: "🌧️ Yoğun çisenti", 61: "🌧️ Hafif yağmur", 63: "🌧️ Yağmur", 65: "🌧️ Kuvvetli yağmur",
        71: "🌨️ Hafif kar", 73: "🌨️ Kar", 75: "❄️ Yoğun kar", 80: "🌦️ Hafif sağanak",
        81: "🌧️ Sağanak", 82: "⛈️ Kuvvetli sağanak", 95: "⛈️ Gök gürültülü"
    }

    try:
        url = (
            "https://api.open-meteo.com/v1/forecast"
            f"?latitude={lat}"
            f"&longitude={lon}"
            "&current=temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m"
            "&daily=sunrise,sunset,temperature_2m_max,temperature_2m_min"
            "&timezone=auto"
        )
        cevap = requests.get(url, timeout=6)
        veri = cevap.json()

        anlik = veri.get("current", {})
        daily = veri.get("daily", {})

        durum = kodlar.get(anlik.get("weather_code"), "🌤️ Hava durumu")
        nem = anlik.get("relative_humidity_2m", "—")
        sicaklik = anlik.get("temperature_2m", "—")
        ruzgar = anlik.get("wind_speed_10m", "—")

        max_sicaklik = daily.get("temperature_2m_max", ["—"])[0]
        min_sicaklik = daily.get("temperature_2m_min", ["—"])[0]
        gun_dogumu = daily.get("sunrise", ["—"])[0]
        gun_batimi = daily.get("sunset", ["—"])[0]

        if "T" in str(gun_dogumu):
            gun_dogumu = str(gun_dogumu).split("T")[1]
        if "T" in str(gun_batimi):
            gun_batimi = str(gun_batimi).split("T")[1]

        return (
            f"{durum} • {sicaklik}°C • Nem %{nem} • "
            f"Rüzgar {ruzgar} km/s • "
            f"Günlük {min_sicaklik}°C / {max_sicaklik}°C • "
            f"Gün doğumu {gun_dogumu} • Gün batımı {gun_batimi}"
        )

    except Exception as e:
        return "🌤️ Canlı hava bilgisi şu an alınamadı"


def canli_doviz_getir():
    varsayilan = {
        "EUR_TRY": 45.0,
        "USD_TRY": 40.0,
        "GBP_TRY": 52.0,
        "metin": "💱 Döviz bilgisi alınamadı, tahmini kur kullanıldı."
    }

    try:
        url = "https://api.frankfurter.dev/v2/rates?base=EUR&quotes=TRY,USD,GBP"
        cevap = requests.get(url, timeout=6)
        veri = cevap.json()
        rates = veri.get("rates", {})

        eur_try = float(rates.get("TRY"))
        usd_per_eur = float(rates.get("USD"))
        gbp_per_eur = float(rates.get("GBP"))

        usd_try = eur_try / usd_per_eur
        gbp_try = eur_try / gbp_per_eur

        return {
            "EUR_TRY": eur_try,
            "USD_TRY": usd_try,
            "GBP_TRY": gbp_try,
            "metin": f"💱 Canlı döviz: 1€ ≈ ₺{eur_try:.2f} • 1$ ≈ ₺{usd_try:.2f} • 1£ ≈ ₺{gbp_try:.2f}"
        }
    except Exception:
        return varsayilan


def para_tl_karsilik(para_kodu, toplam):
    doviz = canli_doviz_getir()
    if para_kodu == "EUR":
        return int(toplam * doviz["EUR_TRY"]), doviz["metin"]
    if para_kodu == "USD":
        return int(toplam * doviz["USD_TRY"]), doviz["metin"]
    if para_kodu == "GBP":
        return int(toplam * doviz["GBP_TRY"]), doviz["metin"]
    return int(toplam), doviz["metin"]


# -----------------------------------------------------
# 3) Seçim ve Bütçe
# -----------------------------------------------------

def yer_duzelt(yer):
    """Kullanıcının yazdığı veya linkten gelen yer adını veri setindeki gerçek anahtara çevirir."""
    if not yer:
        return "Kaş" if "Kaş" in DESTINASYONLAR else next(iter(DESTINASYONLAR))

    anahtar = tr_key(yer)
    eslesmeler = {tr_key(ad): ad for ad in DESTINASYONLAR.keys()}

    # Sık kullanılan kısa/yanlış yazımlar
    ek = {
        "kas": "Kaş",
        "ayder": "Ayder Yaylası",
        "ayder yaylasi": "Ayder Yaylası",
        "uzungol": "Uzungöl",
        "kapadokya": "Kapadokya",
        "nevsehir": "Nevşehir",
        "maldivler": "Maldivler",
        "istanbul": "İstanbul",
        "izmir": "İzmir",
        "cesme": "Çeşme",
        "alacati": "Alaçatı",
        "sanliurfa": "Şanlıurfa",
        "mugla": "Muğla",
        "dunya": "Dubai",
        "yurtdisi": "Dubai"
    }

    if anahtar in ek and ek[anahtar] in DESTINASYONLAR:
        return ek[anahtar]

    if anahtar in eslesmeler:
        return eslesmeler[anahtar]

    # Birebir yoksa parçalı arama
    for k, ad in eslesmeler.items():
        if anahtar in k or k in anahtar:
            return ad

    return yer

def konum_key_getir(deger):
    """turkiye / yurtdisi gibi farklı yazımları tek tipe indirir."""
    t = tr_key(deger)
    if any(x in t for x in ["yurt", "dunya", "dunya", "avrupa", "global", "dıs", "dis"]):
        return "yurtdisi"
    if any(x in t for x in ["turkiye", "turki", "tr", "yurt ici", "yurtici", "yerli"]):
        return "turkiye"
    return t or "turkiye"


def destinasyon_konum_key(bilgi):
    return konum_key_getir(bilgi.get("konum", "turkiye"))


def kategori_key_getir(deger):
    """Formdan gelen tatil türünü net kategoriye çevirir."""
    t = tr_key(deger)
    if any(x in t for x in ["doga", "yayla", "orman", "gol", "göl", "kamp", "bungalov", "sakin"]):
        return "doga"
    if any(x in t for x in ["deniz", "plaj", "yaz", "sahil", "koy", "tekne"]):
        return "deniz"
    if any(x in t for x in ["kultur", "tarih", "muze", "müze", "antik"]):
        return "kultur"
    if any(x in t for x in ["balayi", "romantik", "romance"]):
        return "balayi"
    if any(x in t for x in ["lux", "luks", "premium", "resort", "villa"]):
        return "luks"
    if any(x in t for x in ["eglence", "gece", "club", "festival"]):
        return "eglence"
    if any(x in t for x in ["sehir", "city", "alisveris", "alışveriş"]):
        return "sehir"
    if any(x in t for x in ["kis", "kar", "kayak"]):
        return "kis"
    if any(x in t for x in ["termal", "spa"]):
        return "termal"
    return t or "deniz"


def form_get_coklu(form, *isimler, varsayilan=""):
    """Aynı alan farklı HTML isimleriyle geldiyse hepsini güvenli okur."""
    for isim in isimler:
        deger = form.get(isim)
        if deger not in [None, ""]:
            return deger
    return varsayilan

def konaklama_carpani_getir(konaklama):
    return {
        "standart": 1.00,
        "otel": 1.00,
        "apart": 0.82,
        "hostel": 0.65,
        "premium": 1.30,
        "bungalov": 1.15,
        "villa": 1.45,
        "resort": 1.50
    }.get(konaklama, 1.00)


def ulasim_yazisi_getir(ulasim):
    return {
        "ucak": "✈️ Uçak",
        "arac": "🚗 Özel Araç",
        "otobus": "🚌 Otobüs",
        "tren": "🚆 Tren"
    }.get(ulasim, "✈️ Uçak")


def konaklama_yazisi_getir(konaklama):
    return {
        "standart": "🏨 Standart Otel",
        "otel": "🏨 Otel",
        "apart": "🏠 Apart",
        "hostel": "🛏️ Hostel",
        "premium": "✨ Premium Otel",
        "bungalov": "🌿 Bungalov",
        "villa": "🏡 Villa",
        "resort": "🌴 Resort"
    }.get(konaklama, "🏨 Otel")


def butce_limitleri_getir(para):
    if para == "€":
        return {
            "cok_ekonomik": {"min": 0, "max": 500, "yazi": "€0 - €500"},
            "ekonomik": {"min": 500, "max": 900, "yazi": "€500 - €900"},
            "orta": {"min": 900, "max": 1500, "yazi": "€900 - €1.500"},
            "orta_yuksek": {"min": 1500, "max": 2500, "yazi": "€1.500 - €2.500"},
            "premium": {"min": 2500, "max": 5000, "yazi": "€2.500 - €5.000"},
            "lux": {"min": 5000, "max": 999999, "yazi": "€5.000+"},
            "500 - 1000": {"min": 500, "max": 1000, "yazi": "€500 - €1.000"},
            "1000 - 2500": {"min": 1000, "max": 2500, "yazi": "€1.000 - €2.500"},
            "2500 - 5000": {"min": 2500, "max": 5000, "yazi": "€2.500 - €5.000"},
            "5000 - 10000": {"min": 5000, "max": 10000, "yazi": "€5.000 - €10.000"},
            "10000+": {"min": 10000, "max": 999999, "yazi": "€10.000+"}
        }

    if para in ["$", "£"]:
        return {
            "cok_ekonomik": {"min": 0, "max": 900, "yazi": f"{para}0 - {para}900"},
            "ekonomik": {"min": 900, "max": 1500, "yazi": f"{para}900 - {para}1.500"},
            "orta": {"min": 1500, "max": 3000, "yazi": f"{para}1.500 - {para}3.000"},
            "orta_yuksek": {"min": 3000, "max": 5000, "yazi": f"{para}3.000 - {para}5.000"},
            "premium": {"min": 5000, "max": 8000, "yazi": f"{para}5.000 - {para}8.000"},
            "lux": {"min": 8000, "max": 999999, "yazi": f"{para}8.000+"},
            "500 - 1000": {"min": 500, "max": 1000, "yazi": f"{para}500 - {para}1.000"},
            "1000 - 2500": {"min": 1000, "max": 2500, "yazi": f"{para}1.000 - {para}2.500"},
            "2500 - 5000": {"min": 2500, "max": 5000, "yazi": f"{para}2.500 - {para}5.000"},
            "5000 - 10000": {"min": 5000, "max": 10000, "yazi": f"{para}5.000 - {para}10.000"},
            "10000+": {"min": 10000, "max": 999999, "yazi": f"{para}10.000+"}
        }

    return {
        "cok_ekonomik": {"min": 0, "max": 10000, "yazi": "₺0 - ₺10.000"},
        "ekonomik": {"min": 10000, "max": 20000, "yazi": "₺10.000 - ₺20.000"},
        "orta": {"min": 20000, "max": 35000, "yazi": "₺20.000 - ₺35.000"},
        "orta_yuksek": {"min": 35000, "max": 50000, "yazi": "₺35.000 - ₺50.000"},
        "premium": {"min": 50000, "max": 75000, "yazi": "₺50.000 - ₺75.000"},
        "lux": {"min": 75000, "max": 9999999, "yazi": "₺75.000+"},
        "10.000 - 25.000": {"min": 10000, "max": 25000, "yazi": "₺10.000 - ₺25.000"},
        "25.000 - 50.000": {"min": 25000, "max": 50000, "yazi": "₺25.000 - ₺50.000"},
        "50.000 - 80.000": {"min": 50000, "max": 80000, "yazi": "₺50.000 - ₺80.000"},
        "80.000 - 150.000": {"min": 80000, "max": 150000, "yazi": "₺80.000 - ₺150.000"},
        "150.000+": {"min": 150000, "max": 9999999, "yazi": "₺150.000+"}
    }


def butce_analizi_yap(toplam, para, butce):
    limitler = butce_limitleri_getir(para)
    secilen = limitler.get(butce, list(limitler.values())[2])

    if toplam <= secilen["max"]:
        return "✅ Uygun", "Seçtiğin bütçe aralığı bu plan için uygun görünüyor.", secilen["yazi"]
    if toplam <= secilen["max"] * 1.20:
        return "⚠️ Sınıra Yakın", "Bu plan bütçene yakın. Gün sayısı veya konaklama tercihi azaltılırsa daha rahat olur.", secilen["yazi"]
    return "❌ Bütçeyi Aşıyor", "Bu plan seçtiğin bütçeyi aşıyor. Daha ekonomik konaklama, daha az gün veya farklı rota önerilir.", secilen["yazi"]


def gercekci_butce_hesapla(bilgi, kisi, gun, ulasim, konaklama):
    para = bilgi.get("para", "₺")
    gunluk = int(bilgi.get("gunluk", 2500))
    konum = bilgi.get("konum", "turkiye")

    gece = max(gun - 1, 1)
    oda_sayisi = max((kisi + 1) // 2, 1)
    konaklama_carpani = konaklama_carpani_getir(konaklama)

    konaklama_toplam = int(gunluk * 0.48 * gece * oda_sayisi * konaklama_carpani)
    yeme_icme_toplam = int(gunluk * 0.23 * gun * kisi)
    aktivite_toplam = int(gunluk * 0.16 * gun * kisi)

    if konum == "yurtdisi":
        ulasim_katsayi = {"ucak": 2.40, "otobus": 1.20, "arac": 1.70, "tren": 1.40}.get(ulasim, 2.20)
    else:
        ulasim_katsayi = {"ucak": 1.20, "otobus": 0.45, "arac": 0.70, "tren": 0.55}.get(ulasim, 0.60)

    ulasim_kisi_basi = int(gunluk * ulasim_katsayi)
    ulasim_toplam = ulasim_kisi_basi * kisi

    ara_toplam = konaklama_toplam + yeme_icme_toplam + aktivite_toplam + ulasim_toplam
    ekstra_pay = int(ara_toplam * 0.10)

    toplam = ara_toplam + ekstra_pay
    kisi_basi = int(toplam / max(kisi, 1))
    gunluk_kisi_basi = int(kisi_basi / max(gun, 1))

    return {
        "konaklama": para_format(konaklama_toplam, para),
        "ulasim": para_format(ulasim_toplam, para),
        "yeme_icme": para_format(yeme_icme_toplam, para),
        "aktivite": para_format(aktivite_toplam, para),
        "ekstra_pay": para_format(ekstra_pay, para),
        "toplam": para_format(toplam, para),
        "kisi_basi": para_format(kisi_basi, para),
        "gunluk_kisi_basi": para_format(gunluk_kisi_basi, para),
        "toplam_sayi": toplam,
        "kisi_basi_sayi": kisi_basi,
        "gunluk_kisi_basi_sayi": gunluk_kisi_basi
    }


def otel_filtrele(yer, konaklama, konum):
    tum_oteller = OTEL_VERILERI.get(yer)
    if not tum_oteller:
        tum_oteller = OTELLER.get("turkiye" if konum == "turkiye" else "yurtdisi", [])

    if not tum_oteller:
        bilgi = DESTINASYONLAR.get(yer, DESTINASYONLAR["Kaş"])
        tum_oteller = [{
            "isim": bilgi["otel"]["isim"],
            "tip": "Önerilen Otel",
            "paket": "Kahvaltı Dahil",
            "fiyat": f"{para_format(int(bilgi['gunluk']*1.0), bilgi['para'])} - {para_format(int(bilgi['gunluk']*2.0), bilgi['para'])} / gece",
            "puan": "4.6",
            "foto": "https://images.unsplash.com/photo-1566073771259-6a8506099945",
            "link": f"https://www.google.com/maps/search/{yer}+otel"
        }]

    filtreli = []
    for otel in tum_oteller:
        tip = otel.get("tip", "").lower()
        if konaklama in ["standart", "otel"]:
            filtreli.append(otel)
        elif konaklama == "premium" and any(k in tip for k in ["premium", "lüks", "butik", "mağara", "şehir"]):
            filtreli.append(otel)
        elif konaklama == "bungalov" and any(k in tip for k in ["bungalov", "dağ", "yayla", "doğa"]):
            filtreli.append(otel)
        elif konaklama == "resort" and any(k in tip for k in ["resort", "villa", "su villası"]):
            filtreli.append(otel)
        elif konaklama == "villa" and any(k in tip for k in ["villa", "resort", "su villası"]):
            filtreli.append(otel)
        elif konaklama == "apart" and any(k in tip for k in ["apart", "otel", "butik"]):
            filtreli.append(otel)
        elif konaklama == "hostel" and any(k in tip for k in ["hostel", "şehir", "otel"]):
            filtreli.append(otel)

    return filtreli if filtreli else tum_oteller


def yurtdisi_uyarisi_getir(yer):
    bilgi = DESTINASYONLAR.get(yer, {})
    if bilgi.get("konum") != "yurtdisi":
        return None

    ulke = bilgi.get("ulke", "Yurt dışı")
    para = bilgi.get("para", "$")

    return {
        "baslik": "🛂 Yurt Dışı Uyarısı",
        "metin": f"{yer} ({ulke}) için pasaport gereklidir. Vize koşulları ülkeye göre değişebilir. Para birimi {para} olarak değerlendirilmiştir."
    }


def akilli_yer_sec(*args, **kwargs):
    """
    Tatil önerisinin ana karar motoru.
    - Form alan adları farklı olsa bile çalışır.
    - Türkiye/yurt dışı ayrımını doğru yapar.
    - Doğa seçilince deniz rotasına düşmez.
    - Deniz/kültür/lüks/balayı gibi kategorilerde daha beklenen sonuç verir.
    """
    if len(args) == 1 and hasattr(args[0], "get"):
        form = args[0]
        tatil_konumu = form_get_coklu(form, "konum", "tatil_konumu", "tatilKonumu", "bolge", varsayilan="turkiye")
        tatil_turu = form_get_coklu(form, "tatil", "tatil_turu", "tatil_tipi", "tur", "kategori", varsayilan="deniz")
        ruh_hali = form_get_coklu(form, "ruh_hali", "ruh", "mod", varsayilan="")
        konaklama = form_get_coklu(form, "konaklama", "otel_tipi", varsayilan="")
        pasaport = form_get_coklu(form, "pasaport", varsayilan="")
        vize = form_get_coklu(form, "vize", varsayilan="")
        butce = form_get_coklu(form, "butce", "bütçe", varsayilan="")
    else:
        tatil_konumu = args[0] if len(args) > 0 else kwargs.get("konum", "turkiye")
        tatil_turu = args[1] if len(args) > 1 else kwargs.get("tatil", "deniz")
        ruh_hali = args[2] if len(args) > 2 else kwargs.get("ruh_hali", "")
        konaklama = args[3] if len(args) > 3 else kwargs.get("konaklama", "")
        pasaport = args[4] if len(args) > 4 else kwargs.get("pasaport", "")
        vize = args[5] if len(args) > 5 else kwargs.get("vize", "")
        butce = args[6] if len(args) > 6 else kwargs.get("butce", "")

    istenen_konum = konum_key_getir(tatil_konumu)
    kategori = kategori_key_getir(tatil_turu)
    ruh_key = kategori_key_getir(ruh_hali) if ruh_hali else ""
    butce_key = tr_key(butce)
    konaklama_key = tr_key(konaklama)
    pasaport_key = tr_key(pasaport)
    vize_key = tr_key(vize)

    # Yurt dışı istenmiş ama pasaport/vize yoksa sistemi güvenli şekilde Türkiye içine çevir.
    yurtdisi_engelli = False
    if istenen_konum == "yurtdisi" and (
        pasaport_key in ["yok", "hayir", "hayır", "no"] or
        vize_key in ["yok", "hayir", "hayır", "no"]
    ):
        yurtdisi_engelli = True
        istenen_konum = "turkiye"

    oncelik = {
        ("turkiye", "deniz"): ["Kaş", "Bodrum", "Fethiye", "Çeşme", "Marmaris", "Datça", "Alaçatı", "Cunda", "Amasra"],
        ("turkiye", "doga"): ["Ayder Yaylası", "Uzungöl", "Sapanca", "Abant", "Rize", "Trabzon", "Bolu", "Artvin"],
        ("turkiye", "kultur"): ["Mardin", "Kapadokya", "İstanbul", "Şanlıurfa", "Ankara", "Eskişehir"],
        ("turkiye", "balayi"): ["Kapadokya", "Bodrum", "Kaş", "Alaçatı", "Cunda"],
        ("turkiye", "luks"): ["Bodrum", "Kalkan", "Çeşme", "Alaçatı", "Antalya"],
        ("turkiye", "eglence"): ["Bodrum", "Marmaris", "Çeşme", "İstanbul", "Antalya"],
        ("turkiye", "sehir"): ["İstanbul", "İzmir", "Ankara", "Eskişehir"],
        ("turkiye", "kis"): ["Bolu", "Erzurum", "Kars", "Bursa", "Kayseri"],
        ("turkiye", "termal"): ["Afyonkarahisar", "Yalova", "Kütahya", "Denizli"],

        ("yurtdisi", "deniz"): ["Maldivler", "Bali", "Phuket", "Santorini", "Barselona", "Lizbon"],
        ("yurtdisi", "doga"): ["Bali", "Phuket", "Maldivler"],
        ("yurtdisi", "kultur"): ["Roma", "Paris", "Prag", "Viyana", "Atina", "Londra"],
        ("yurtdisi", "balayi"): ["Maldivler", "Paris", "Santorini", "Venedik", "Bali"],
        ("yurtdisi", "luks"): ["Dubai", "Maldivler", "Paris", "Londra", "Santorini"],
        ("yurtdisi", "eglence"): ["Dubai", "Amsterdam", "Barselona", "New York"],
        ("yurtdisi", "sehir"): ["Paris", "Roma", "Amsterdam", "Dubai", "Londra", "Tokyo"],
    }

    def mevcut_mu(ad, hedef_konum):
        gercek = yer_duzelt(ad)
        if gercek not in DESTINASYONLAR:
            return None
        if destinasyon_konum_key(DESTINASYONLAR[gercek]) == hedef_konum:
            return gercek
        return None

    # 1) Beklenen öncelikli rota
    for aday in oncelik.get((istenen_konum, kategori), []):
        bulunan = mevcut_mu(aday, istenen_konum)
        if bulunan:
            return bulunan

    # 2) Etiket + bütçe + ruh hali puanlama
    en_iyi = None
    en_puan = -10**9

    for ad, bilgi in DESTINASYONLAR.items():
        if destinasyon_konum_key(bilgi) != istenen_konum:
            continue

        etiketler = [kategori_key_getir(e) for e in bilgi.get("etiketler", [])]
        ham_etiketler = [tr_key(e) for e in bilgi.get("etiketler", [])]
        gunluk = int(bilgi.get("gunluk", 2500))

        puan = 0

        if kategori in etiketler or kategori in ham_etiketler:
            puan += 100

        # Kategoriye yakın ek anlamlar
        if kategori == "doga" and any(e in ham_etiketler for e in ["yayla", "bungalov", "kamp", "sakin"]):
            puan += 35
        if kategori == "deniz" and any(e in ham_etiketler for e in ["sahil", "yaz", "tekne"]):
            puan += 35
        if kategori == "kultur" and any(e in ham_etiketler for e in ["tarih", "sehir"]):
            puan += 30
        if kategori == "luks" and any(e in ham_etiketler for e in ["premium", "resort", "lux"]):
            puan += 35

        if ruh_key and (ruh_key in etiketler or ruh_key in ham_etiketler):
            puan += 15

        if konaklama_key and konaklama_key in " ".join(ham_etiketler):
            puan += 8

        # Bütçe uyumu
        if butce_key in ["cok ekonomik", "cok_ekonomik", "dusuk", "düşük", "ekonomik"]:
            puan += max(0, 30 - gunluk // 200)
        elif butce_key in ["orta", "25.000 - 50.000", "1000 - 2500"]:
            if gunluk <= 5000:
                puan += 20
        elif butce_key in ["premium", "lux", "luks", "lüks", "yuksek", "yüksek"]:
            if gunluk >= 4000:
                puan += 20

        # Çok genel il kayıtlarının özel destinasyonların önüne geçmesini azalt
        if ad in ["Muğla", "Antalya", "İzmir", "Rize", "Trabzon", "Bolu", "Nevşehir"]:
            puan -= 5

        if puan > en_puan:
            en_puan = puan
            en_iyi = ad

    return en_iyi or ("Kaş" if "Kaş" in DESTINASYONLAR else next(iter(DESTINASYONLAR)))

def benzer_oneriler_getir(yer, adet=3):
    """Ana rota ile aynı ülke/kategori grubundan daha doğru alternatifler üretir."""
    yer = yer_duzelt(yer)
    if yer not in DESTINASYONLAR:
        yer = "Kaş" if "Kaş" in DESTINASYONLAR else next(iter(DESTINASYONLAR))

    ana = DESTINASYONLAR[yer]
    ana_konum = destinasyon_konum_key(ana)
    ana_etiketler_ham = [tr_key(e) for e in ana.get("etiketler", [])]
    ana_etiketler = set([kategori_key_getir(e) for e in ana.get("etiketler", [])] + ana_etiketler_ham)

    def ana_kategori_bul():
        # Balayı etiketi varsa romantik alternatifler öne gelsin.
        if "balayi" in ana_etiketler or "balayı" in ana_etiketler:
            return "balayi"
        # Lüks/premium rotalarda premium alternatifler gelsin.
        if "luks" in ana_etiketler or "lux" in ana_etiketler or "premium" in ana_etiketler or "resort" in ana_etiketler:
            return "luks"
        for k in ["deniz", "doga", "kultur", "eglence", "sehir", "kis", "termal"]:
            if k in ana_etiketler:
                return k
        return "sehir"

    kategori = ana_kategori_bul()

    alternatif_oncelik = {
        ("turkiye", "deniz"): ["Bodrum", "Fethiye", "Çeşme", "Marmaris", "Datça", "Alaçatı", "Cunda", "Amasra"],
        ("turkiye", "doga"): ["Sapanca", "Uzungöl", "Abant", "Rize", "Trabzon", "Bolu", "Artvin"],
        ("turkiye", "kultur"): ["Kapadokya", "İstanbul", "Şanlıurfa", "Ankara", "Eskişehir", "Amasya"],
        ("turkiye", "balayi"): ["Bodrum", "Alaçatı", "Cunda", "Kaş", "Kalkan"],
        ("turkiye", "luks"): ["Çeşme", "Alaçatı", "Kalkan", "Antalya", "Bodrum"],
        ("turkiye", "eglence"): ["Marmaris", "Çeşme", "İstanbul", "Antalya", "Bodrum"],
        ("turkiye", "sehir"): ["İstanbul", "İzmir", "Ankara", "Eskişehir"],

        ("yurtdisi", "deniz"): ["Bali", "Phuket", "Santorini", "Barselona", "Lizbon", "Maldivler"],
        ("yurtdisi", "doga"): ["Bali", "Phuket", "Maldivler"],
        ("yurtdisi", "kultur"): ["Paris", "Roma", "Prag", "Viyana", "Atina", "Londra"],
        ("yurtdisi", "balayi"): ["Paris", "Santorini", "Venedik", "Bali", "Maldivler"],
        ("yurtdisi", "luks"): ["Maldivler", "Paris", "Londra", "Santorini", "Dubai"],
        ("yurtdisi", "eglence"): ["Amsterdam", "Barselona", "New York", "Dubai"],
        ("yurtdisi", "sehir"): ["Paris", "Roma", "Amsterdam", "Londra", "Tokyo", "Dubai"],
    }

    sonuc = []
    kullanilan = {yer}

    def ekle(ad):
        gercek = yer_duzelt(ad)
        if gercek in DESTINASYONLAR and gercek not in kullanilan:
            b = DESTINASYONLAR[gercek]
            if destinasyon_konum_key(b) == ana_konum:
                sonuc.append({
                    "yer": gercek,
                    "fiyat": para_format(int(b.get("gunluk", 0) * 3), b.get("para", "₺")),
                    "ulasim": "✈️ / 🚗 Alternatif rota"
                })
                kullanilan.add(gercek)

    for ad in alternatif_oncelik.get((ana_konum, kategori), []):
        if len(sonuc) >= adet:
            break
        ekle(ad)

    # Öncelik listesi yetmezse puanlama ile tamamla
    if len(sonuc) < adet:
        adaylar = []
        for ad, bilgi in DESTINASYONLAR.items():
            if ad in kullanilan:
                continue
            if destinasyon_konum_key(bilgi) != ana_konum:
                continue

            etiketler = set([kategori_key_getir(e) for e in bilgi.get("etiketler", [])] + [tr_key(e) for e in bilgi.get("etiketler", [])])
            ortak = len(ana_etiketler.intersection(etiketler))

            for kritik in ["deniz", "doga", "kultur", "balayi", "luks", "eglence", "sehir", "kis", "termal"]:
                if kritik in ana_etiketler and kritik in etiketler:
                    ortak += 5

            genel_ceza = 1 if ad in ["Muğla", "Antalya", "İzmir", "Rize", "Trabzon", "Bolu", "Nevşehir"] else 0
            fiyat = int(bilgi.get("gunluk", 0))
            adaylar.append((ortak, -genel_ceza, -abs(int(ana.get("gunluk", 0)) - fiyat), ad))

        adaylar.sort(reverse=True)
        for _, _, _, ad in adaylar:
            if len(sonuc) >= adet:
                break
            ekle(ad)

    while len(sonuc) < adet:
        sonuc.append({"yer": "Alternatif hazırlanıyor", "fiyat": "—", "ulasim": "—"})

    return sonuc

def sonuc_verisi_hazirla(yer, kisi, gun, ulasim, konaklama, butce, kaynak="destinasyon", ekstra_not=""):
    yer = yer_duzelt(yer)
    bilgi = DESTINASYONLAR.get(yer, DESTINASYONLAR["Kaş"])
    para = bilgi.get("para", "₺")
    para_kodu = bilgi.get("kod", "TRY")
    konum = bilgi.get("konum", "turkiye")

    butce_detay = gercekci_butce_hesapla(bilgi, kisi, gun, ulasim, konaklama)
    toplam = butce_detay["toplam_sayi"]

    toplam_tl, doviz_metin = para_tl_karsilik(para_kodu, toplam)
    butce_durumu, butce_aciklama, butce_yazi = butce_analizi_yap(toplam, para, butce)

    hava = canli_hava_getir(yer)
    ulasim_yazisi = ulasim_yazisi_getir(ulasim)
    konaklama_yazisi = konaklama_yazisi_getir(konaklama)
    oteller = otel_filtrele(yer, konaklama, konum)
    yurtdisi_uyarisi = yurtdisi_uyarisi_getir(yer)
    alternatifler = benzer_oneriler_getir(yer, 3)

    if para_kodu == "TRY":
        tl_metni = f"TL karşılığı: {para_format(toplam_tl, '₺')}"
    else:
        tl_metni = f"Yaklaşık TL karşılığı: {para_format(toplam_tl, '₺')}"

    neden_onerildi = (
        f"Bu plan; {kisi} kişi, {gun} gün, {ulasim_yazisi} ulaşım tercihi, "
        f"{konaklama_yazisi} konaklama seçimi ve {butce_yazi} bütçe aralığına göre oluşturuldu. "
        f"{yer}; {bilgi['aciklama']}"
    )

    if kaynak == "akilli_form":
        neden_onerildi = "Akıllı formdaki tercihlerine göre seçildi. " + neden_onerildi
    elif kaynak == "foto":
        neden_onerildi = "Fotoğraf/atmosfer seçimine göre rota önerildi. " + neden_onerildi

    ai_yorum = f"""
🌍 Destinasyon:
{yer}

🌤️ Canlı Hava Durumu:
{hava}

💱 Canlı Döviz Bilgisi:
{doviz_metin}

👥 Tatil Planı:
{kisi} kişi • {gun} gün

🚗 Seçilen Ulaşım:
{ulasim_yazisi}

🏨 Seçilen Konaklama:
{konaklama_yazisi}

💰 Bütçe Aralığı:
{butce_yazi}

📊 Bütçe Uygunluğu:
{butce_durumu}
{butce_aciklama}

📍 Önerilen Rota:
{bilgi['rota']}

🏨 Otel:
{bilgi['otel']['isim']}

📞 İletişim:
{bilgi['otel']['telefon']}

🚗 Tahmini Yol:
{bilgi['yol']}

💰 Bütçe Detayı:
Konaklama: {butce_detay['konaklama']}
Ulaşım: {butce_detay['ulasim']}
Yeme-İçme: {butce_detay['yeme_icme']}
Aktivite: {butce_detay['aktivite']}
Ekstra Pay: {butce_detay['ekstra_pay']}

💵 Toplam Tahmini Ücret:
{butce_detay['toplam']}

👤 Kişi Başı:
{butce_detay['kisi_basi']}

📅 Günlük Kişi Başı:
{butce_detay['gunluk_kisi_basi']}

{tl_metni}

✨ Aktivite Önerileri:
{bilgi['aktiviteler']}

📝 Ek Not:
{ekstra_not if ekstra_not else 'Ek not girilmedi.'}
"""

    return {
        "butce_detay": butce_detay,
        "kisi_basi": butce_detay["kisi_basi"],
        "gunluk_kisi_basi": butce_detay["gunluk_kisi_basi"],
        "toplam_fiyat": butce_detay["toplam"],
        "sonuc": yer,
        "ai_yorum": ai_yorum,
        "hava": hava,
        "doviz_metin": doviz_metin,
        "tl_metni": tl_metni,
        "butce_durumu": butce_durumu,
        "butce_aciklama": butce_aciklama,
        "oteller": oteller,
        "gezilecek_yerler": GEZILECEK_YERLER.get(yer, []),
        "gunluk_rotalar": GUNLUK_ROTALAR.get(yer, []),
        "neden_onerildi": neden_onerildi,
        "yurtdisi_uyarisi": yurtdisi_uyarisi,
        "kisi": kisi,
        "gun": gun,
        "ulasim_secimi": ulasim_yazisi,
        "konaklama_secimi": konaklama_yazisi,
        "butce_secimi": butce_yazi,
        "oneri1": {"yer": yer, "fiyat": butce_detay["toplam"], "ulasim": ulasim_yazisi},
        "oneri2": alternatifler[0],
        "oneri3": alternatifler[1],
        "alternatifler": alternatifler,
        "tum_destinasyon_sayisi": len(DESTINASYONLAR)
    }


# -----------------------------------------------------
# 4) Route'lar
# -----------------------------------------------------

@app.route("/")
def home():
    return safe_render("index.html", destinasyonlar=DESTINASYONLAR)


@app.route("/destinasyonlar")
def destinasyonlar():
    sirali = sorted(DESTINASYONLAR.items(), key=lambda x: (x[1].get("konum", ""), x[0]))
    try:
        return render_template("destinasyonlar.html", destinasyonlar=sirali)
    except TemplateNotFound:
        kartlar = ""
        for ad, b in sirali:
            kartlar += f"""
            <div class="card">
                <h2>{ad}</h2>
                <p>{b.get('aciklama','')}</p>
                <p><b>{b.get('konum','')}</b> • Günlük tahmin: {para_format(b.get('gunluk',0), b.get('para','₺'))}</p>
                <a class="btn" href="/hizli-plan?yer={ad}">Planla</a>
            </div>
            """
        return render_template_string(f"""
        <!DOCTYPE html><html lang="tr"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
        <title>Destinasyonlar | DiPol</title>
        <style>
        *{{box-sizing:border-box;font-family:Arial}}body{{margin:0;background:#06142b;color:white}}.page{{padding:30px 6%}}
        .hero{{text-align:center;margin:30px auto;max-width:900px}}.hero h1{{font-size:44px;background:linear-gradient(90deg,#00d4ff,#9b5cff);-webkit-background-clip:text;color:transparent}}
        .grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:18px}}.card{{background:rgba(255,255,255,.10);border:1px solid rgba(255,255,255,.16);border-radius:24px;padding:22px}}
        .btn{{display:block;text-align:center;padding:13px;border-radius:15px;background:linear-gradient(90deg,#8b5cff,#00d4ff);color:white;text-decoration:none;font-weight:bold}}
        a{{color:white}}@media(max-width:900px){{.grid{{grid-template-columns:1fr}}.hero h1{{font-size:32px}}}}
        </style></head><body><div class="page">
        <p><a href="/">← Ana Sayfa</a> • <a href="/tatil-formu">Akıllı Form</a></p>
        <div class="hero"><h1>DiPol Destinasyonları</h1><p>Türkiye 81 il + popüler yurt dışı rotaları. Toplam {len(DESTINASYONLAR)} destinasyon.</p></div>
        <div class="grid">{kartlar}</div></div></body></html>
        """)


@app.route("/oteller")
def oteller():
    return safe_render("oteller.html", oteller=OTEL_VERILERI)


@app.route("/ucuslar")
def ucuslar():
    return safe_render("ucuslar.html", destinasyonlar=DESTINASYONLAR)


@app.route("/rehber")
def rehber():
    return safe_render("rehber.html")


@app.route("/hakkimizda")
def hakkimizda():
    return safe_render("hakkimizda.html")


@app.route("/giris")
def giris():
    return safe_render("giris.html")


@app.route("/favoriler")
def favoriler():
    return safe_render("favoriler.html")


@app.route("/tatil-formu")
def tatil_formu():
    return safe_render("tatil_formu.html", destinasyonlar=DESTINASYONLAR)


@app.route("/tatil-sonuc", methods=["POST"])
def tatil_sonuc():
    # Form alanları farklı isimlerle gelse bile doğru oku.
    konum = form_get_coklu(request.form, "konum", "tatil_konumu", "tatilKonumu", "bolge", varsayilan="turkiye")
    tatil = form_get_coklu(request.form, "tatil", "tatil_turu", "tatil_tipi", "tur", "kategori", varsayilan="deniz")
    ruh_hali = form_get_coklu(request.form, "ruh_hali", "ruh", "mod", varsayilan="dinlenmek")
    konaklama = form_get_coklu(request.form, "konaklama", "otel_tipi", varsayilan="otel")
    pasaport = form_get_coklu(request.form, "pasaport", varsayilan="yok")
    vize = form_get_coklu(request.form, "vize", varsayilan="farketmez")

    kisi = guvenli_int(form_get_coklu(request.form, "kisi", "kisi_sayisi", "kişi", varsayilan=1), 1, 1, 10)
    gun = guvenli_int(form_get_coklu(request.form, "gun", "gun_sayisi", "gün", varsayilan=3), 3, 1, 30)
    ulasim = form_get_coklu(request.form, "ulasim", "ulaşım", varsayilan="ucak")
    butce = form_get_coklu(request.form, "butce", "bütçe", varsayilan="orta")
    not_metni = form_get_coklu(request.form, "not", "not_metni", "ek_not", varsayilan="")

    # "sehir" kullanıcının bulunduğu/çıkış şehri olabilir.
    # Bu yüzden sadece açıkça "yer/destinasyon/hedef_yer" gelirse direkt rota kabul edilir.
    direkt_yer = form_get_coklu(request.form, "yer", "destinasyon", "hedef_yer", varsayilan="")
    if direkt_yer and yer_duzelt(direkt_yer) in DESTINASYONLAR:
        yer = yer_duzelt(direkt_yer)
    else:
        yer = akilli_yer_sec(konum, tatil, ruh_hali, konaklama, pasaport, vize, butce)

    veri = sonuc_verisi_hazirla(
        yer=yer,
        kisi=kisi,
        gun=gun,
        ulasim=ulasim,
        konaklama=konaklama,
        butce=butce,
        kaynak="akilli_form",
        ekstra_not=not_metni
    )

    try:
        plan_ekle(
            yer=veri.get("sonuc", ""),
            toplam_ucret=veri.get("butce_detay", {}).get("toplam", ""),
            kisi_basi=veri.get("butce_detay", {}).get("kisi_basi", ""),
            gunluk_kisi_basi=veri.get("butce_detay", {}).get("gunluk_kisi_basi", ""),
            ulasim=veri.get("ulasim_secimi", ""),
            konaklama=veri.get("konaklama_secimi", ""),
            kisi=veri.get("kisi", 1),
            gun=veri.get("gun", 1),
            butce_durumu=veri.get("butce_durumu", "")
        )
    except Exception as e:
        print("Plan veritabanına kaydedilemedi:", e)

    return safe_render("sonuc.html", **veri)


@app.route("/tahmin", methods=["POST"])
def tahmin():
    return tatil_sonuc()


@app.route("/hizli-plan")
def hizli_plan():
    yer = yer_duzelt(request.args.get("yer", "Kaş"))
    bilgi = DESTINASYONLAR.get(yer, DESTINASYONLAR["Kaş"])
    konum = request.args.get("konum", bilgi["konum"])
    return safe_render("plan_form.html", yer=yer, konum=konum, bilgi=bilgi)


@app.route("/hizli-sonuc", methods=["POST"])
def hizli_sonuc():
    yer = yer_duzelt(request.form.get("yer", "Kaş"))
    kisi = guvenli_int(request.form.get("kisi"), 2, 1, 10)
    gun = guvenli_int(request.form.get("gun"), 3, 1, 30)
    ulasim = request.form.get("ulasim", "ucak")
    konaklama = request.form.get("konaklama", "standart")
    butce = request.form.get("butce", "orta")

    veri = sonuc_verisi_hazirla(
        yer=yer,
        kisi=kisi,
        gun=gun,
        ulasim=ulasim,
        konaklama=konaklama,
        butce=butce,
        kaynak="destinasyon"
    )

    return safe_render("sonuc.html", **veri)


@app.route("/sonuc")
def sonuc():
    veri = sonuc_verisi_hazirla("Kaş", 2, 3, "ucak", "standart", "orta", "demo")
    return safe_render("sonuc.html", **veri)


# -----------------------------------------------------
# 5) Fotoğraftan Konum / Atmosfer Demo Sistemi
# -----------------------------------------------------

FOTO_FORM_HTML = """
<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Fotoğraftan Yer Bul | DiPol</title>
<style>
*{margin:0;padding:0;box-sizing:border-box;font-family:Arial,sans-serif}
body{
    min-height:100vh;color:white;
    background:radial-gradient(circle at top left,rgba(0,212,255,.22),transparent 35%),
    radial-gradient(circle at bottom right,rgba(155,92,255,.24),transparent 35%),
    linear-gradient(rgba(3,8,25,.84),rgba(3,8,25,.98)),url("/static/bg.jpg");
    background-size:cover;background-position:center;background-attachment:fixed;
}
.page{padding:28px 6%}
.navbar{min-height:82px;display:flex;align-items:center;justify-content:space-between;padding:0 28px;border-radius:26px;background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.14);backdrop-filter:blur(20px)}
.logo{font-size:32px;font-weight:900;background:linear-gradient(90deg,#00d4ff,#9b5cff,#ff69d6);-webkit-background-clip:text;color:transparent}
.menu{display:flex;gap:20px;flex-wrap:wrap}.menu a,.login{color:white;text-decoration:none;font-weight:bold}.login{padding:12px 22px;border-radius:18px;border:1px solid rgba(255,255,255,.20)}
.wrap{min-height:calc(100vh - 120px);display:flex;align-items:center;justify-content:center;padding:45px 0}
.card{width:100%;max-width:860px;padding:44px;border-radius:36px;background:rgba(255,255,255,.10);border:1px solid rgba(255,255,255,.16);backdrop-filter:blur(22px);box-shadow:0 28px 90px rgba(0,0,0,.42);text-align:center}
.badge{display:inline-block;padding:10px 18px;border-radius:999px;background:rgba(0,212,255,.12);border:1px solid rgba(0,212,255,.25);margin-bottom:18px;font-weight:bold}
h1{font-size:48px;margin-bottom:16px;background:linear-gradient(90deg,#00d4ff,#9b5cff,#ff69d6);-webkit-background-clip:text;color:transparent}
.desc{line-height:1.8;opacity:.92;font-size:18px;max-width:720px;margin:0 auto 28px}
.info{padding:20px;border-radius:22px;background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.14);line-height:1.8;text-align:left;margin-bottom:24px}
.upload{border:2px dashed rgba(255,255,255,.30);border-radius:28px;padding:34px;background:rgba(0,0,0,.22)}
input{width:100%;padding:16px;margin-top:18px;border-radius:18px;border:1px solid rgba(255,255,255,.18);font-size:16px;background:white;color:#111}
.file-note{margin-top:14px;font-size:15px;opacity:.95}
.btn{width:100%;margin-top:26px;padding:17px;border:none;border-radius:20px;color:white;font-size:18px;font-weight:bold;cursor:pointer;background:linear-gradient(90deg,#8b5cff,#00d4ff)}
.back{display:inline-block;color:white;margin-top:22px;text-decoration:none;opacity:.85}
@media(max-width:900px){.menu{display:none}.card{padding:30px 22px}h1{font-size:34px}}
</style>
</head>
<body>
<div class="page">
<div class="navbar">
    <div class="logo">🌍 DiPol</div>
    <div class="menu">
        <a href="/">Keşfet</a>
        <a href="/tatil-formu">Akıllı Form</a>
        <a href="/destinasyonlar">Destinasyonlar</a>
        <a href="/favoriler">⭐ Favorilerim</a>
        <a href="/rehber">Rehber</a>
    </div>
    <a href="/giris" class="login">Giriş Yap</a>
</div>

<div class="wrap">
<div class="card">
<div class="badge">📍 Fotoğraftan Yer Bulma Modülü</div>
<h1>Fotoğraftaki Yer Neresi?</h1>
<p class="desc">
Peri Bacaları, Eyfel Kulesi, Kız Kulesi, Galata Kulesi, tarihi yapı veya doğal manzara fotoğrafı yükle.
Sistem sadece yer tespiti yapar.
</p>
<div class="info">
<strong>Bu bölüm tatil önerisi değildir.</strong><br>
Otel, bütçe, rota veya günlük plan vermez. Sadece fotoğraftaki yerin neresi olabileceğini söyler.<br><br>
<strong>Desteklenen dosya türleri:</strong> JPG, JPEG, PNG, WEBP<br>
<strong>Maksimum dosya boyutu:</strong> 5 MB
</div>

<form action="/foto-sonuc" method="POST" enctype="multipart/form-data">
    <div class="upload">
        <h2>☁ Fotoğraf Yükle</h2>
        <p style="opacity:.85;margin-top:8px;">Ekran görüntüsü yerine gerçek yer/anıt/manzara fotoğrafı seç.</p>
        <input id="fotografInput" type="file" name="fotograf" accept=".jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp" required>
        <div id="dosyaBilgi" class="file-note">Henüz dosya seçilmedi.</div>
    </div>
    <button class="btn" type="submit">📍 Fotoğraftaki Yeri Bul</button>
</form>
<a class="back" href="/">← Ana sayfaya dön</a>
</div>
</div>
</div>
<script>
const input = document.getElementById("fotografInput");
const bilgi = document.getElementById("dosyaBilgi");
input.addEventListener("change", function(){
    if(!this.files || !this.files[0]){ bilgi.innerHTML = "Henüz dosya seçilmedi."; return; }
    const file = this.files[0];
    const mb = file.size / (1024 * 1024);
    if(mb > 5){
        bilgi.innerHTML = "❌ Seçilen dosya: " + mb.toFixed(2) + " MB. Maksimum 5 MB olmalı.";
        bilgi.style.color = "#ff9b9b";
    }else{
        bilgi.innerHTML = "✅ Seçilen dosya: " + mb.toFixed(2) + " MB / 5 MB";
        bilgi.style.color = "#b7ffcf";
    }
});
</script>
</body>
</html>
"""


@app.route("/foto-konum")
def foto_konum():
    return render_template_string(FOTO_FORM_HTML)



def gemini_fotograftan_yer_bul(image_bytes, mime_type):
    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        return {
            "success": False,
            "place": "Gemini API anahtar? bulunamad?",
            "city": "",
            "country": "",
            "confidence": "0",
            "explanation": "GEMINI_API_KEY .env dosyas?nda bulunamad?.",
            "is_screenshot": False
        }

    try:
        client = genai.Client(api_key=api_key)

        prompt = """
Sen bir foto?raftan yer bulma sistemisin.
G?revin tatil ?nermek de?il, sadece foto?raftaki yerin neresi olabilece?ini bulmak.

Kurallar:
- E?er g?rsel ekran g?r?nt?s?, web sitesi, uygulama ekran?, sohbet ekran? veya bilgisayar ekran? ise yer tahmini yapma.
- E?er foto?rafta bilinen bir an?t, yap?, ?ehir, do?al olu?um veya turistik yer varsa yer ad?, ?ehir ve ?lke s?yle.
- Emin de?ilsen rastgele yer uydurma, Net bulunamad? de.
- Sonucu sadece JSON olarak ver.

JSON format?:
{
  "success": true,
  "place": "Yer ad? veya Net bulunamad?",
  "city": "?ehir",
  "country": "?lke",
  "confidence": "0-100",
  "explanation": "K?sa a??klama",
  "is_screenshot": false
}
"""

        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[
                prompt,
                types.Part.from_bytes(
                    data=image_bytes,
                    mime_type=mime_type
                )
            ]
        )

        text = response.text.strip()
        text = text.replace("```json", "").replace("```", "").strip()
        veri = json.loads(text)

        return {
            "success": bool(veri.get("success")),
            "place": veri.get("place", "Net bulunamad?"),
            "city": veri.get("city", ""),
            "country": veri.get("country", ""),
            "confidence": str(veri.get("confidence", "0")),
            "explanation": veri.get("explanation", "A??klama al?namad?."),
            "is_screenshot": bool(veri.get("is_screenshot"))
        }

    except Exception as e:
        return {
            "success": False,
            "place": "Gemini analizi yap?lamad?",
            "city": "",
            "country": "",
            "confidence": "0",
            "explanation": f"Gemini g?rsel analiz s?ras?nda hata olu?tu: {str(e)}",
            "is_screenshot": False
        }


@app.route("/foto-sonuc", methods=["POST"])
def foto_sonuc():
    dosya = request.files.get("fotograf")

    izinli_uzantilar = ["jpg", "jpeg", "png", "webp"]
    max_boyut_mb = 5

    def sonuc_sayfasi(baslik, mesaj, tahmin=None, sehir=None, ulke=None, guven=None, aciklama=None, durum="info", boyut=None):
        renk = "#00d4ff"
        if durum == "hata":
            renk = "#ff6b8a"
        elif durum == "basari":
            renk = "#7CFFB2"

        konum = ""
        if sehir or ulke:
            konum = f"<div class='sub'>{sehir} {ulke}</div>"

        tahmin_html = ""
        if tahmin:
            tahmin_html = f"""
            <div class="result">
                <div class="small">Tahmini yer</div>
                <h2>{tahmin}</h2>
                {konum}
                <div class="sub">G?ven oran?: %{guven or '0'}</div>
            </div>
            """

        aciklama_html = ""
        if aciklama:
            aciklama_html = f"<div class='box'><b>A??klama:</b><br>{aciklama}</div>"

        boyut_html = ""
        if boyut is not None:
            boyut_html = f"<div class='box'><b>Dosya boyutu:</b><br>{boyut:.2f} MB / 5 MB</div>"

        return render_template_string(f"""
<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Foto?raf Yer Sonucu | DiPol</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box;font-family:Arial,sans-serif}}
body{{
    min-height:100vh;
    color:white;
    background:
    radial-gradient(circle at top left,rgba(0,212,255,.20),transparent 35%),
    radial-gradient(circle at bottom right,rgba(155,92,255,.25),transparent 35%),
    linear-gradient(rgba(3,8,25,.88),rgba(3,8,25,.98)),
    url("/static/bg.jpg");
    background-size:cover;
    background-position:center;
    display:flex;
    align-items:center;
    justify-content:center;
    padding:30px;
}}
.card{{
    width:100%;
    max-width:780px;
    padding:42px;
    border-radius:34px;
    background:rgba(255,255,255,.10);
    border:1px solid rgba(255,255,255,.16);
    backdrop-filter:blur(22px);
    box-shadow:0 28px 90px rgba(0,0,0,.42);
    text-align:center;
}}
h1{{font-size:42px;margin-bottom:16px;color:{renk}}}
p{{line-height:1.8;opacity:.92;font-size:18px;margin-bottom:18px}}
.result{{
    margin:28px 0;
    padding:30px;
    border-radius:30px;
    background:rgba(0,212,255,.12);
    border:1px solid rgba(0,212,255,.25);
}}
.result h2{{
    font-size:44px;
    margin:10px 0;
    background:linear-gradient(90deg,#00d4ff,#9b5cff,#ff69d6);
    -webkit-background-clip:text;
    color:transparent;
}}
.small{{opacity:.8;font-weight:bold}}
.sub{{opacity:.9;font-weight:bold;margin-top:8px}}
.box{{
    margin-top:15px;
    padding:18px;
    border-radius:20px;
    background:rgba(255,255,255,.08);
    border:1px solid rgba(255,255,255,.12);
    line-height:1.7;
    text-align:left;
}}
.warning{{
    margin-top:18px;
    padding:18px;
    border-radius:20px;
    background:rgba(255,193,7,.12);
    border:1px solid rgba(255,193,7,.25);
    line-height:1.7;
    text-align:left;
}}
a{{
    display:inline-block;
    margin-top:24px;
    margin-right:8px;
    padding:14px 22px;
    border-radius:18px;
    color:white;
    text-decoration:none;
    font-weight:bold;
    background:linear-gradient(90deg,#8b5cff,#00d4ff);
}}
@media(max-width:700px){{
    .card{{padding:30px 22px}}
    h1{{font-size:32px}}
    .result h2{{font-size:32px}}
}}
</style>
</head>
<body>
<div class="card">
    <h1>{baslik}</h1>
    <p>{mesaj}</p>
    {tahmin_html}
    {aciklama_html}
    {boyut_html}
    <div class="warning">
        <b>Not:</b> Bu mod?l tatil ?nerisi olu?turmaz. Otel, b?t?e, rota veya g?nl?k plan vermez.
        Sadece foto?raftaki yerin neresi olabilece?ini bulmaya ?al???r.
    </div>
    <a href="/foto-konum">Yeni foto?raf y?kle</a>
    <a href="/">Ana sayfa</a>
</div>
</body>
</html>
        """)

    if not dosya or dosya.filename == "":
        return sonuc_sayfasi("?? Foto?raf se?ilmedi", "Yer bulma i?lemi i?in bir foto?raf y?klemelisin.", durum="hata")

    filename = secure_filename(dosya.filename)
    uzanti = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if uzanti not in izinli_uzantilar:
        return sonuc_sayfasi("? Desteklenmeyen dosya", "Sadece JPG, JPEG, PNG veya WEBP foto?raf y?kleyebilirsin.", durum="hata")

    dosya.stream.seek(0, os.SEEK_END)
    boyut_mb = dosya.stream.tell() / (1024 * 1024)
    dosya.stream.seek(0)

    if boyut_mb > max_boyut_mb:
        return sonuc_sayfasi("?? Dosya ?ok b?y?k", f"Y?kledi?in dosya {boyut_mb:.2f} MB. Maksimum 5 MB olmal?.", durum="hata", boyut=boyut_mb)

    image_bytes = dosya.read()

    mime_map = {
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "webp": "image/webp"
    }
    mime_type = mime_map.get(uzanti, "image/jpeg")

    analiz = gemini_fotograftan_yer_bul(image_bytes, mime_type)

    if analiz.get("is_screenshot"):
        return sonuc_sayfasi(
            "? Yer tespiti yap?lamad?",
            "Y?klenen g?rsel ekran g?r?nt?s? veya uygulama/site ekran? gibi g?r?n?yor. Bu y?zden yer tahmini yap?lmad?.",
            tahmin="Ekran g?r?nt?s? alg?land?",
            guven=analiz.get("confidence", "0"),
            aciklama=analiz.get("explanation"),
            durum="hata",
            boyut=boyut_mb
        )

    if not analiz.get("success"):
        return sonuc_sayfasi(
            "? Yer net bulunamad?",
            "Foto?raftaki yer g?venli ?ekilde belirlenemedi.",
            tahmin=analiz.get("place", "Net bulunamad?"),
            sehir=analiz.get("city", ""),
            ulke=analiz.get("country", ""),
            guven=analiz.get("confidence", "0"),
            aciklama=analiz.get("explanation"),
            durum="hata",
            boyut=boyut_mb
        )

    return sonuc_sayfasi(
        "?? Foto?raf Yeri Bulundu",
        "Y?klenen foto?raf Gemini g?rsel analiz sistemiyle incelendi.",
        tahmin=analiz.get("place"),
        sehir=analiz.get("city"),
        ulke=analiz.get("country"),
        guven=analiz.get("confidence"),
        aciklama=analiz.get("explanation"),
        durum="basari",
        boyut=boyut_mb
    )


# -----------------------------------------------------
# 6) Hata Sayfaları
# -----------------------------------------------------

@app.errorhandler(404)
def not_found(e):
    return render_template_string("""
    <div style="min-height:100vh;display:flex;align-items:center;justify-content:center;background:#06142b;color:white;font-family:Arial;text-align:center;padding:30px;">
        <div>
            <h1 style="font-size:56px;">404</h1>
            <h2>Sayfa bulunamadı</h2>
            <p>Aradığın sayfa taşınmış ya da henüz hazırlanıyor olabilir.</p><br>
            <a href="/" style="color:white;background:linear-gradient(90deg,#8b5cff,#00d4ff);padding:14px 22px;border-radius:16px;text-decoration:none;font-weight:bold;">Ana Sayfaya Dön</a>
        </div>
    </div>
    """), 404


@app.errorhandler(500)
def server_error(e):
    return render_template_string("""
    <div style="min-height:100vh;display:flex;align-items:center;justify-content:center;background:#06142b;color:white;font-family:Arial;text-align:center;padding:30px;">
        <div>
            <h1 style="font-size:46px;">⚠️ Sistem Hatası</h1>
            <p>Bir hata oluştu. Form değerleri veya eksik template dosyaları kontrol edilmelidir.</p><br>
            <a href="/" style="color:white;background:linear-gradient(90deg,#8b5cff,#00d4ff);padding:14px 22px;border-radius:16px;text-decoration:none;font-weight:bold;">Ana Sayfaya Dön</a>
        </div>
    </div>
    """), 500

@app.route("/favori-kaydet", methods=["POST"])
def favori_kaydet():
    try:
        veri = request.get_json() or {}

        yer = veri.get("yer", "")
        fiyat = veri.get("fiyat", "")
        ulasim = veri.get("ulasim", "")
        konaklama = veri.get("konaklama", "")
        kisi = veri.get("kisi", 1)
        gun = veri.get("gun", 1)

        if not yer:
            return {"success": False, "message": "Yer bilgisi eksik."}

        favori_ekle(
            yer=yer,
            fiyat=fiyat,
            ulasim=ulasim,
            konaklama=konaklama,
            kisi=kisi,
            gun=gun
        )

        return {"success": True, "message": "Favori veritabanına kaydedildi."}

    except Exception as e:
        return {"success": False, "message": str(e)}


@app.route("/api/favoriler")
def api_favoriler():
    favoriler = favorileri_getir()

    liste = []
    for f in favoriler:
        liste.append({
            "id": f["id"],
            "yer": f["yer"],
            "fiyat": f["fiyat"],
            "ulasim": f["ulasim"],
            "konaklama": f["konaklama"],
            "kisi": f["kisi"],
            "gun": f["gun"],
            "tarih": f["tarih"]
        })

    return {"success": True, "favoriler": liste}


@app.route("/favorileri-temizle-db", methods=["POST"])
def favorileri_temizle_db():
    favorileri_temizle()
    return {"success": True, "message": "Veritabanındaki favoriler temizlendi."}


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0")
