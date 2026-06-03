import sqlite3
from datetime import datetime

DB_NAME = "dipol_travel.db"


def baglanti_al():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def veritabani_olustur():
    conn = baglanti_al()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS favoriler (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        yer TEXT NOT NULL,
        fiyat TEXT,
        ulasim TEXT,
        konaklama TEXT,
        kisi INTEGER,
        gun INTEGER,
        tarih TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS planlar (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        yer TEXT NOT NULL,
        toplam_ucret TEXT,
        kisi_basi TEXT,
        gunluk_kisi_basi TEXT,
        ulasim TEXT,
        konaklama TEXT,
        kisi INTEGER,
        gun INTEGER,
        butce_durumu TEXT,
        tarih TEXT
    )
    """)

    conn.commit()
    conn.close()


def favori_ekle(yer, fiyat="", ulasim="", konaklama="", kisi=1, gun=1):
    conn = baglanti_al()
    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO favoriler (yer, fiyat, ulasim, konaklama, kisi, gun, tarih)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        yer,
        fiyat,
        ulasim,
        konaklama,
        kisi,
        gun,
        datetime.now().strftime("%d.%m.%Y %H:%M")
    ))

    conn.commit()
    conn.close()


def favorileri_getir():
    conn = baglanti_al()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM favoriler ORDER BY id DESC")
    favoriler = cursor.fetchall()

    conn.close()
    return favoriler


def favorileri_temizle():
    conn = baglanti_al()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM favoriler")

    conn.commit()
    conn.close()


def plan_ekle(yer, toplam_ucret="", kisi_basi="", gunluk_kisi_basi="", ulasim="", konaklama="", kisi=1, gun=1, butce_durumu=""):
    conn = baglanti_al()
    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO planlar (
        yer, toplam_ucret, kisi_basi, gunluk_kisi_basi,
        ulasim, konaklama, kisi, gun, butce_durumu, tarih
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        yer,
        toplam_ucret,
        kisi_basi,
        gunluk_kisi_basi,
        ulasim,
        konaklama,
        kisi,
        gun,
        butce_durumu,
        datetime.now().strftime("%d.%m.%Y %H:%M")
    ))

    conn.commit()
    conn.close()


def planlari_getir():
    conn = baglanti_al()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM planlar ORDER BY id DESC")
    planlar = cursor.fetchall()

    conn.close()
    return planlar