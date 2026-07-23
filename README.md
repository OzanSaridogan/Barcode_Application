# Barkod Uygulaması

Fiyat girip tek tıkla doğru Code 128 barkodu basan basit masaüstü uygulaması.
Kasadaki hazır POS bu barkodu okuyup fiyatı otomatik alır; kasiyerin hesap
makinesiyle toplamasına gerek kalmaz.

## Barkodun kuralı

Ekran görüntülerinizden ve gerçek etiket tasarımından çözülen kural:

```
barkod verisi = ÖNEK + kuruş (5 haneye sıfırla tamamlanmış)
```

- Önek: `81275000` (8 hane, sabit)
- Fiyat kuruşa çevrilir: 190 TL → 19000, 37,50 TL → 3750
- Kuruş 5 haneye tamamlanır: 3750 → `03750`
- Sonuç: `81275000` + `03750` = `8127500003750`

Gerçek tasarımınızdaki `ANGEL 190 TL` etiketinde barkod `8127500019000` yazıyordu;
kural bunu ve diğer örnekleri birebir üretiyor:

| Fiyat | Kuruş (5 hane) | Üretilen barkod | Kaynak |
|------:|:--------------:|-----------------|--------|
| 190 TL | 19000 | `8127500019000` | tasarım |
| 260 TL | 26000 | `8127500026000` | örnek |
| 37,50 TL | 03750 | `8127500003750` | örnek |
| 30 TL | 03000 | `8127500003000` | örnek |
| 100 TL | 10000 | `8127500010000` | ilk örnek |

> Not: Daha önce verdiğiniz "260/190" örneklerinde yanlışlıkla fazladan bir sıfır
> vardı (14 hane). Gerçek tasarımdaki barkod 13 hane olduğu için doğru önek
> `81275000` olarak belirlendi.

Barkod tipi **Code 128**, yazıcı **203 DPI**. Etiket **30 × 15 mm** (240 × 120 nokta).
Konumlar ZebraDesigner'daki gerçek değerlerden birebir alındı: barkod yatayda ortalı
(çapa üst-orta, X 15 mm = tam orta), metin sola hizalı (X 4,57 mm, Y 11,84 mm).

> Tasarımda ayrı bir çerçeve öğesi yoktur; gördüğünüz yuvarlak dikdörtgen etiketin
> fiziksel kesim şeklidir. Bu yüzden çerçeve **basılmaz** (`[cerceve] etkin = hayir`).
> Gerçek etiketlerinizde basılı bir çerçeve varsa `evet` yapın.

## 3'lü sıra basımı (önemli)

Yazıcınızın medyası **bir sırada 3 etiket yan yana**dır (Etiket Özellikleri: yatay
sayım 3, sütun arası 3 mm, sol boşluk 2 mm; toplam şerit 98 mm). Uygulama bunu
hesaba katar: her baskıda tüm sırayı (98 mm = 784 nokta) tek seferde üretir ve her
etiketi kendi fiziksel konumuna yerleştirir (16 / 280 / 544 nokta).

"Adet" kaç **etiket** basılacağını belirtir; etiketler soldan sağa, sıra sıra
dizilir (yazıcının "yatay - sol yukarıdan başla" sırasıyla aynı):

| Adet | Basılan sıra | Sonuç |
|-----:|:------------:|-------|
| 1 | 1 sıra | 1 etiket (sağdaki 2 sütun boş) |
| 3 | 1 sıra | 3 etiket (sıra tam dolu) |
| 5 | 2 sıra | 5 etiket (son sırada 1 sütun boş) |
| 6 | 2 sıra | 6 etiket |

Bu düzen değerleri `config.ini` içindeki `[yerlesim]` bölümündedir; medyanız
değişirse (örn. 2'li sıra) oradan ayarlanır.

---

## 1. Çalıştırma (geliştirme bilgisayarında)

Python 3.9+ kurulu olmalı (Windows'ta python.org'dan kurarken
"Add Python to PATH" kutusunu işaretleyin; tkinter hazır gelir).

```
pip install -r requirements.txt
python barkod.py
```

`config.ini` dosyası `barkod.py` ile **aynı klasörde** olmalıdır.

İlk açılışta `[yazici] baglanti = dosya` ayarı olduğu için hiçbir yazıcı
gerekmez: "YAZDIR" veya "ZPL Kaydet" dediğinizde etiket `cikti/etiket.zpl`
dosyasına yazılır. Böylece yazıcısız bilgisayarda geliştirip test edebilirsiniz.

## 2. Etiketi gözle test etme (yazıcı olmadan)

1. Uygulamada bir fiyat girip "ZPL Kaydet"e basın.
2. `cikti/etiket.zpl` dosyasını Not Defteri ile açın, içeriği kopyalayın.
3. Tarayıcıda **labelary.com/viewer.html** adresine gidin, yapıştırın.
4. Etiketin baskıda tam olarak nasıl görüneceğini görürsünüz.

Etiket boyutu / konum beğenmezseniz `config.ini` içindeki `[etiket]` ve
`[fiyat_yazisi]` değerlerini değiştirip tekrar bakın. (mm × 8 = nokta.)

## 3. Dükkândaki bilgisayara kurulum

Sadece `config.ini` içindeki `[yazici]` bölümünü değiştirin:

**Ağ yazıcısı (IP'si varsa):**
```
baglanti = ag
ag_ip = 192.168.1.50     ; yazıcının IP adresi
ag_port = 9100
```

**USB yazıcı (Windows'ta yüklü):**
```
baglanti = windows
windows_yazici_adi = ZDesigner GK420t   ; Aygıtlar ve Yazıcılar'daki tam ad
```
Bu mod için ek olarak: `pip install pywin32`

## 4. Tek dosya .exe yapma (personel için)

Personelin Python kurmasına gerek kalmadan çift tıkla açması için:

```
pip install pyinstaller
pyinstaller --onefile --windowed --add-data "config.ini;." barkod.py
```

`dist/barkod.exe` oluşur. Bu exe'yi ve `config.ini`'yi aynı klasöre koyup
dükkândaki bilgisayara kopyalayın. (macOS/Linux'ta `--add-data "config.ini:."`
şeklinde iki nokta kullanılır.)

---

## Ayarların tamamı

Tüm ayarlar `config.ini` içindedir ve Not Defteri ile değiştirilebilir;
koda dokunmaya gerek yoktur. Öne çıkanlar:

- `[barkod] onek` — barkod öneki (şu an `81275000`)
- `[barkod] carpan` — 100 (fiyatı kuruşa çevirir)
- `[barkod] kurus_hane` — 5 (kuruşu 5 haneye sıfırla tamamlar)
- `[cerceve] etkin` — dış yuvarlak çerçeve bassın mı
- `[buyuk_yazi] etkin` — altta büyük "ÜRÜNADI FİYAT TL" yazısı bassın mı
- `[buyuk_yazi] font_yukseklik` — büyük yazının boyutu (nokta)

## Uygulamada ürün adı

Etiketin altındaki büyük yazı `ÜRÜNADI FİYAT TL` biçimindedir (örn. `ANGEL 190 TL`).
Ürün adını uygulamadaki "Urun adi" kutusuna yazarsınız; **barkodun içine girmez**,
yalnızca etiketin üzerinde görünür. Ad kutusunu boş bırakırsanız yazı sadece
`FİYAT TL` olur.

## Önemli not — öneki bir kez doğrulayın

`81275000` öneki, tasarımınızdaki gerçek barkod (`8127500019000` = 190 TL) ile
doğrulandı ve amacınız yalnızca fiyat olduğu için sabit kabul edildi. Eğer ileride
önekin bir kısmının **ürüne göre değiştiğini** fark ederseniz (yani barkod ürünü de
tanıtıyorsa), o kısım bir "ürün kodu"dur; söyleyin, uygulamaya barkoda giren ayrı
bir ürün kodu alanı ekleyelim.