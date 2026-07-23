# -*- coding: utf-8 -*-
"""
BARKOD UYGULAMASI
-----------------
Fiyat girin -> dogru Code 128 barkod uretilir -> onizlenir -> yazdirilir.

Barkod kurali (ornek etiketlerden cozuldu):
    barkod verisi = ONEK + (fiyat x 100)   # fiyat kurusa cevrilir
    ornek: 37,50 TL -> 3750 -> "812750000" + "3750" = "8127500003750"

Ayarlar config.ini dosyasindadir. Kod degistirmeye gerek yoktur.
"""

import os
import sys
import socket
import configparser
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation

import tkinter as tk
from tkinter import ttk, messagebox

# Onizleme icin (opsiyonel). Yoksa uygulama yine calisir, sadece resim yerine
# barkod verisi metni gosterilir.
try:
    from barcode import Code128
    from barcode.writer import ImageWriter
    from PIL import Image, ImageTk, ImageDraw, ImageFont
    import io
    ONIZLEME_VAR = True
except Exception:
    ONIZLEME_VAR = False


# ----------------------------------------------------------------------
# Ayarlarin okunmasi
# ----------------------------------------------------------------------
def uygulama_dizini():
    """PyInstaller ile .exe yapildiginda da dogru klasoru bulur."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


BASE_DIR = uygulama_dizini()
CONFIG_YOLU = os.path.join(BASE_DIR, "config.ini")


def ayarlari_yukle():
    cfg = configparser.ConfigParser()
    if not os.path.exists(CONFIG_YOLU):
        raise FileNotFoundError(
            f"Ayar dosyasi bulunamadi:\n{CONFIG_YOLU}\n\n"
            "config.ini dosyasi barkod.py ile ayni klasorde olmalidir."
        )
    cfg.read(CONFIG_YOLU, encoding="utf-8")
    return cfg


# ----------------------------------------------------------------------
# Cekirdek mantik: fiyat -> barkod verisi -> ZPL
# ----------------------------------------------------------------------
def fiyat_to_kurus(fiyat_metni, carpan):
    """
    '37,50', '37.5', '37,50 TL' gibi girisleri kurus tam sayisina cevirir.
    Turkce virgul (,) ve nokta (.) ondalik ayiraci desteklenir.
    """
    s = str(fiyat_metni).strip()
    s = s.replace("\u20ba", "").replace("TL", "").replace("tl", "").replace(" ", "")
    if s == "":
        raise ValueError("Fiyat bos olamaz.")
    # Hem "1.234,56" hem "1234.56" hem "37,5" durumlarini normalize et
    if s.count(",") == 1 and s.count(".") >= 1:
        s = s.replace(".", "").replace(",", ".")   # 1.234,56 -> 1234.56
    else:
        s = s.replace(",", ".")                     # 37,5 -> 37.5
    try:
        d = Decimal(s)
    except InvalidOperation:
        raise ValueError(f"Gecersiz fiyat: {fiyat_metni}")
    if d < 0:
        raise ValueError("Fiyat negatif olamaz.")
    kurus = int((d * Decimal(carpan)).quantize(Decimal(1), rounding=ROUND_HALF_UP))
    return kurus


def barkod_verisi_uret(fiyat_metni, onek, carpan, kurus_hane=5):
    """barkod = onek + kurus (en az `kurus_hane` haneye sifirla tamamlanmis).
    Ornek: onek=81275000, 37,5 TL -> 3750 -> '03750' -> '8127500003750'."""
    kurus = fiyat_to_kurus(fiyat_metni, carpan)
    return onek + str(kurus).zfill(kurus_hane)


def fiyat_kisa(fiyat_metni, carpan):
    """Buyuk yazi icin fiyati kisa gosterir: 190,00->'190'  37,50->'37,5'  8,05->'8,05'."""
    kurus = fiyat_to_kurus(fiyat_metni, carpan)
    lira = Decimal(kurus) / Decimal(carpan)
    s = f"{lira:.2f}"
    if "." in s:
        s = s.rstrip("0").rstrip(".")   # 190.00->190 , 37.50->37.5
    return s.replace(".", ",")


def buyuk_yazi_uret(urun_adi, fiyat_metni, carpan, son_ek):
    """Etiketin altindaki buyuk yazi: 'ANGEL 190 TL'."""
    fiyat = fiyat_kisa(fiyat_metni, carpan)
    return f"ANGEL {fiyat} {son_ek.strip()}".strip()


def _acik(bolum, anahtar):
    return bolum is not None and bolum.get(anahtar, "hayir").strip().lower() in (
        "evet", "yes", "true", "1")


def _etiket_alanlari(veri, buyuk_yazi, ox, cfg):
    """Tek bir etiketin ZPL alanlarini, yatay x-ofseti `ox` ile uretir.
    (^XA/^XZ/^PW/^LL disinda, sadece o etiketin icerigi.)"""
    b = cfg["barkod"]
    e = cfg["etiket"]
    c = cfg["cerceve"] if cfg.has_section("cerceve") else None
    t = cfg["buyuk_yazi"] if cfg.has_section("buyuk_yazi") else None
    bk = cfg["barcode_konum"] if cfg.has_section("barcode_konum") else None

    modul = b.getint("modul_genislik")
    yuk = b.getint("yukseklik")
    altyazi = "N"
    lw = e.getint("etiket_genislik")
    ll = e.getint("etiket_uzunluk")
    by = e.getint("barkod_y")
    barcode_x = bk.getint("barcode_x", fallback=0) if bk else 0
    barcode_y = bk.getint("barcode_y", fallback=0) if bk else 0
    barcode_genislik = bk.getint("barcode_genislik", fallback=lw) if bk else lw
    barcode_yukseklik = bk.getint("barcode_yukseklik", fallback=yuk) if bk else yuk

    left_margin = barcode_x if barcode_x > 0 else max(0, (lw - barcode_genislik) // 2)
    top_margin = barcode_y if barcode_y > 0 else max(0, (ll - barcode_yukseklik) // 2)

    S = []
    # Yuvarlak koseli cerceve (yalnizca aciksa)
    if _acik(c, "etkin"):
        m = c.getint("bosluk")
        th = c.getint("kalinlik")
        rnd = c.getint("yuvarlaklik")
        S += [f"^FO{ox + m},{m}", f"^GB{lw - 2*m},{ll - 2*m},{th},B,{rnd}^FS"]

    # Barkod — konum ve boyut config.ini'den okunur, etiketin ortasina yerleştirilir
    text_width = min(t.getint("genislik", fallback=lw), max(1, barcode_genislik)) if t else max(1, barcode_genislik)
    offset = max(0, (barcode_genislik - text_width) // 2)
    bx = ox + left_margin + offset
    S += [f"^BY{modul}", f"^FO{bx},{top_margin}", f"^FB{barcode_genislik},1,0,C,0",
          f"^BCN,{barcode_yukseklik},{altyazi},N,N", f"^FD{veri}^FS"]

    # Buyuk yazi (ANGEL + fiyat + TL) — barkodun altina, daha geniş bir boslukla ve biraz daha buyuk font ile
    if _acik(t, "etkin"):
        ty = t.getint("y", fallback=95)
        fh = max(20, int(t.getint("font_yukseklik") * 0.9))
        jj = "C"
        tx = ox + max(0, (lw - text_width) // 2)
        S += [f"^FO{tx},{ty}", f"^A0N,{fh},{fh}", f"^FB{text_width},1,0,{jj},0",
              f"^FD{buyuk_yazi}^FS"]
    return S


def yerlesim_bilgisi(cfg):
    """3'lu sira duzeni: (sayim, etiket_genislik, sol_bosluk, gap, ofsetler, web_genislik)."""
    e = cfg["etiket"]
    y = cfg["yerlesim"] if cfg.has_section("yerlesim") else None
    lw = e.getint("etiket_genislik")
    sayim = y.getint("yatay_sayim", fallback=1) if y else 1
    sol = y.getint("sol_bosluk", fallback=0) if y else 0
    gap = y.getint("yatay_bosluk", fallback=0) if y else 0
    ofsetler = [sol + i * (lw + gap) for i in range(sayim)]
    web = sol + sayim * lw + (sayim - 1) * gap
    return sayim, lw, sol, gap, ofsetler, web


def zpl_uret(veri, buyuk_yazi, cfg, adet=1):
    """`adet` kadar etiketi, yazicinin 3'lu sira duzenine gore uretir.
    Etiketler soldan saga, sira sira dizilir (Islem sirasi: yatay-sol yukardan)."""
    sayim, lw, sol, gap, ofsetler, web = yerlesim_bilgisi(cfg)
    ll = cfg["etiket"].getint("etiket_uzunluk")

    bloklar = []
    kalan = max(1, int(adet))
    while kalan > 0:
        n = min(sayim, kalan)                 # bu sirada kac sutun dolacak
        S = ["^XA", f"^PW{web}", f"^LL{ll}", "^CI28"]
        for i in range(n):
            S += _etiket_alanlari(veri, buyuk_yazi, ofsetler[i], cfg)
        S.append("^XZ")
        bloklar.append("\n".join(S))
        kalan -= n
    return "\n".join(bloklar)


# ----------------------------------------------------------------------
# Yazdirma / cikti
# ----------------------------------------------------------------------
def zpl_gonder(zpl, cfg, adet=1):
    """
    Ayardaki baglanti turune gore ZPL'i gonderir.
    (Adet, ZPL zaten uretilirken 3'lu sira duzenine gore islenmistir;
     burada yalnizca durum mesajinda kullanilir.)
    Doner: kullaniciya gosterilecek durum mesaji.
    """
    y = cfg["yazici"]
    baglanti = y.get("baglanti").strip().lower()

    if baglanti == "dosya":
        klasor = os.path.join(BASE_DIR, y.get("cikti_klasoru").strip())
        os.makedirs(klasor, exist_ok=True)
        yol = os.path.join(klasor, "etiket.zpl")
        with open(yol, "w", encoding="utf-8") as fp:
            fp.write(zpl)
        return f"ZPL dosyaya kaydedildi:\n{yol}"

    if baglanti == "ag":
        ip = y.get("ag_ip").strip()
        port = y.getint("ag_port")
        with socket.create_connection((ip, port), timeout=5) as s:
            s.sendall(zpl.encode("utf-8"))
        return f"{adet} adet etiket yaziciya gonderildi ({ip}:{port})."

    if baglanti == "windows":
        try:
            import win32print
        except Exception:
            raise RuntimeError(
                "Windows yaziciya baski icin 'pywin32' gerekli.\n"
                "Kurulum: pip install pywin32"
            )
        adi = y.get("windows_yazici_adi").strip()
        h = win32print.OpenPrinter(adi)
        try:
            win32print.StartDocPrinter(h, 1, ("Barkod", None, "RAW"))
            win32print.StartPagePrinter(h)
            win32print.WritePrinter(h, zpl.encode("utf-8"))
            win32print.EndPagePrinter(h)
            win32print.EndDocPrinter(h)
        finally:
            win32print.ClosePrinter(h)
        return f"{adet} adet etiket '{adi}' yazicisina gonderildi."

    raise ValueError(f"Bilinmeyen baglanti turu: {baglanti}")


# ----------------------------------------------------------------------
# Arayuz
# ----------------------------------------------------------------------
class Uygulama(tk.Tk):
    def __init__(self, cfg):
        super().__init__()
        self.cfg = cfg
        self.onek = cfg["barkod"].get("onek").strip()
        self.carpan = cfg["barkod"].getint("carpan")
        self.kurus_hane = cfg["barkod"].getint("kurus_hane", fallback=5)
        if cfg.has_section("buyuk_yazi"):
            self.son_ek = cfg["buyuk_yazi"].get("son_ek", "TL").strip()
        else:
            self.son_ek = cfg["fiyat_yazisi"].get("son_ek", "TL").strip()

        self.title("Barkod Uygulamasi")
        self.geometry("470x620")
        self.resizable(False, False)
        self._preview_img = None

        self._arayuz_kur()
        self.fiyat_giris.focus_set()

    def _arayuz_kur(self):
        pad = {"padx": 16, "pady": 6}

        baslik = ttk.Label(self, text="Fiyat Barkodu Olustur",
                           font=("Segoe UI", 15, "bold"))
        baslik.pack(anchor="w", padx=16, pady=(14, 2))

        ttk.Label(self, text=f"Onek: {self.onek}   |   Fiyat x {self.carpan} (kurus)",
                 foreground="#666").pack(anchor="w", padx=16)

        # Fiyat ve Adet yan yana
        cerceve = ttk.Frame(self)
        cerceve.pack(fill="x", **pad)

        fiyat_kutu = ttk.Frame(cerceve)
        fiyat_kutu.pack(side="left")
        ttk.Label(fiyat_kutu, text="Fiyat (TL)",
                 font=("Segoe UI", 11)).pack(anchor="w")
        self.fiyat_giris = ttk.Entry(fiyat_kutu, font=("Segoe UI", 22), width=10)
        self.fiyat_giris.pack()
        self.fiyat_giris.bind("<KeyRelease>", lambda e: self.onizle())
        self.fiyat_giris.bind("<Return>", lambda e: self.yazdir())

        adet_kutu = ttk.Frame(cerceve)
        adet_kutu.pack(side="left", padx=(20, 0))
        ttk.Label(adet_kutu, text="Adet",
                 font=("Segoe UI", 11)).pack(anchor="w")
        self.adet = tk.StringVar(value="1")
        self.adet_giris = ttk.Spinbox(adet_kutu, from_=1, to=999, width=5,
                                     font=("Segoe UI", 22),
                                     textvariable=self.adet)
        self.adet_giris.pack()
        self.adet_giris.bind("<Return>", lambda e: self.yazdir())

        # Uretilen veri
        self.veri_lbl = ttk.Label(self, text="Barkod verisi: —",
                                  font=("Consolas", 11), foreground="#0a5")
        self.veri_lbl.pack(anchor="w", padx=16, pady=(10, 0))

        ttk.Label(self, text="Yazici bir sirada 3 etiket yan yana basar; "
                            "adet kadar etiket soldan saga dizilir.",
                 foreground="#888", font=("Segoe UI", 9)).pack(anchor="w", padx=16)

        # Onizleme alani (tek etiketin gorunumu)
        self.onizleme = tk.Label(self, bd=1, relief="solid", bg="white",
                                height=8, text="Fiyat girin",
                                fg="#999", font=("Segoe UI", 11))
        self.onizleme.pack(fill="x", padx=16, pady=8, ipady=10)

        if not ONIZLEME_VAR:
            ttk.Label(self, foreground="#a60",
                     text="(Resimli onizleme icin: pip install python-barcode Pillow)"
                     ).pack(anchor="w", padx=16)

        # Butonlar
        btnf = ttk.Frame(self)
        btnf.pack(fill="x", padx=16, pady=12)
        self.yazdir_btn = tk.Button(btnf, text="YAZDIR", font=("Segoe UI", 13, "bold"),
                                   bg="#1c7", fg="white", height=2,
                                   command=self.yazdir)
        self.yazdir_btn.pack(side="left", expand=True, fill="x", padx=(0, 6))
        tk.Button(btnf, text="ZPL Kaydet", height=2,
                 command=self.zpl_kaydet).pack(side="left", padx=(6, 0))

        # Durum cubugu
        self.durum = tk.StringVar(value=f"Hazir  ·  baglanti: {self.cfg['yazici'].get('baglanti')}")
        ttk.Label(self, textvariable=self.durum, relief="sunken",
                 anchor="w", foreground="#333").pack(side="bottom", fill="x")

    # -- islevler ------------------------------------------------------
    def _veri_ve_gorunum(self):
        fiyat = self.fiyat_giris.get()
        veri = barkod_verisi_uret(fiyat, self.onek, self.carpan, self.kurus_hane)
        buyuk = buyuk_yazi_uret(None, fiyat, self.carpan, self.son_ek)
        return veri, buyuk

    def onizle(self):
        try:
            veri, buyuk = self._veri_ve_gorunum()
        except Exception:
            self.veri_lbl.config(text="Barkod verisi: —")
            self.onizleme.config(image="", text="Gecerli bir fiyat girin", fg="#999")
            self._preview_img = None
            return

        self.veri_lbl.config(text=f"Barkod verisi: {veri}")

        if ONIZLEME_VAR:
            try:
                im = self._mock_etiket(veri, buyuk)
                self._preview_img = ImageTk.PhotoImage(im)
                self.onizleme.config(image=self._preview_img, text="")
            except Exception as ex:
                self.onizleme.config(image="", text=f"Onizleme hatasi: {ex}", fg="#c00")
                self._preview_img = None
        else:
            self.onizleme.config(text=f"{buyuk}\n{veri}", fg="#111",
                                font=("Consolas", 13))

    def _mock_etiket(self, veri, buyuk):
        """Basilacak etiketin gercek oranli (config'e dayali) yaklasik gorunumu."""
        e = self.cfg["etiket"]
        pw = e.getint("etiket_genislik")
        ll = e.getint("etiket_uzunluk")
        by = e.getint("barkod_y")

        olcek = 380 / pw                      # onizlemeyi ~380px genislige olcekle
        W = int(pw * olcek)
        H = int(ll * olcek)
        im = Image.new("RGB", (W, H), "white")
        d = ImageDraw.Draw(im)
        # Etiketin fiziksel kenari (ince gri) — basilan cizgi degil, sadece sinir
        d.rounded_rectangle([1, 1, W - 2, H - 2], radius=int(8 * olcek),
                            outline="#cccccc", width=1)

        # Cerceve (yalnizca config'de aciksa basilir)
        if self.cfg.has_section("cerceve") and \
           self.cfg["cerceve"].get("etkin", "hayir").strip().lower() in ("evet", "yes", "true", "1"):
            m = int(self.cfg["cerceve"].getint("bosluk") * olcek)
            d.rounded_rectangle([m, m, W - m, H - m], radius=int(8 * olcek),
                                outline="black", width=2)

        # Barkod — yatayda ortali, ustte
        bc = Code128(veri, writer=ImageWriter())
        bbuf = io.BytesIO()
        bc.write(bbuf, options={"module_height": 7.5, "font_size": 8,
                                "quiet_zone": 1, "write_text": True})
        bbuf.seek(0)
        bim = Image.open(bbuf)
        maxw = int(pw * 0.75 * olcek)
        bim.thumbnail((maxw, int(H * 0.6)))
        im.paste(bim, ((W - bim.width) // 2, int(by * olcek)))

        # Buyuk yazi — config'deki konum ve hizalama
        t = self.cfg["buyuk_yazi"]
        tx = int(t.getint("x", fallback=37) * olcek)
        ty = int(t.getint("y", fallback=95) * olcek)
        fh = max(10, int(t.getint("font_yukseklik") * olcek))
        try:
            font = ImageFont.truetype("arialbd.ttf", fh)
        except Exception:
            try:
                font = ImageFont.truetype("DejaVuSans-Bold.ttf", fh)
            except Exception:
                font = ImageFont.load_default()
        hiz = t.get("hizalama", "sol").strip().lower()
        if hiz in ("orta", "sag"):
            tb = d.textbbox((0, 0), buyuk, font=font)
            tw = tb[2] - tb[0]
            if hiz == "orta":
                tx = (W - tw) // 2
            else:
                tx = W - int(6 * olcek) - tw
        d.text((tx, ty), buyuk, fill="black", font=font)
        return im

    def _hazir_zpl(self, adet=1):
        veri, buyuk = self._veri_ve_gorunum()
        return zpl_uret(veri, buyuk, self.cfg, adet)

    def _adet_al(self):
        """Adet kutusunu dogrular. Bos/0/gecersiz ise ValueError firlatir."""
        ham = self.adet.get().strip()
        if ham == "":
            raise ValueError("Adet bos olamaz. En az 1 girin.")
        try:
            n = int(ham)
        except ValueError:
            raise ValueError(f"Gecersiz adet: {ham}. Sadece sayi girin.")
        if n < 1:
            raise ValueError("Adet en az 1 olmalidir.")
        if n > 999:
            raise ValueError("Adet en fazla 999 olabilir.")
        return n

    def yazdir(self):
        try:
            adet = self._adet_al()
            zpl = self._hazir_zpl(adet)
        except Exception as ex:
            messagebox.showwarning("Giris hatasi", str(ex))
            return
        try:
            mesaj = zpl_gonder(zpl, self.cfg, adet)
            self.durum.set(mesaj.replace("\n", "  "))
            if self.cfg["yazici"].get("baglanti").strip().lower() == "dosya":
                messagebox.showinfo("Tamam", mesaj)
            # Basari: adet varsayilan 1'e donsun
            self.adet.set("1")
        except Exception as ex:
            messagebox.showerror("Yazdirma hatasi", str(ex))
            self.durum.set(f"HATA: {ex}")

    def zpl_kaydet(self):
        try:
            adet = self._adet_al()
            zpl = self._hazir_zpl(adet)
        except Exception as ex:
            messagebox.showwarning("Giris hatasi", str(ex))
            return
        klasor = os.path.join(BASE_DIR, self.cfg["yazici"].get("cikti_klasoru").strip())
        os.makedirs(klasor, exist_ok=True)
        yol = os.path.join(klasor, "etiket.zpl")
        with open(yol, "w", encoding="utf-8") as fp:
            fp.write(zpl)
        messagebox.showinfo("Kaydedildi",
                           f"ZPL kaydedildi:\n{yol}\n\n"
                           "labelary.com/viewer.html adresine yapistirip test edin.\n"
                           "Etiket boyutu: 98 mm genislik (3'lu sira), 15 mm yukseklik,\n"
                           "8 dpmm (203 dpi).")


def main():
    try:
        cfg = ayarlari_yukle()
    except Exception as ex:
        root = tk.Tk(); root.withdraw()
        messagebox.showerror("Ayar hatasi", str(ex))
        return
    app = Uygulama(cfg)
    app.mainloop()


if __name__ == "__main__":
    main()