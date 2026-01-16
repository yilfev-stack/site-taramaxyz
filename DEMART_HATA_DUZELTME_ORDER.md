# DEMART.COM.TR WEB SİTESİ HATA DÜZELTME TALİMATLARI
# Bu dosyayı site üreten agent'a verin

## ÖNCELİK: YÜKSEK - Bu hatalar profesyonelliği zedeliyor

---

## HATA 1: CANONICAL URL HATASI (SEO Kritik)

**Sorun:** İngilizce sayfa `/en/` canonical URL olarak Türkçe ana sayfayı gösteriyor.

**Konum:** `/app/frontend/src/` içindeki EN sayfası (muhtemelen layout veya head component)

**Düzeltme:**
```
EN sayfasının <head> bölümünde:
YANLIŞ: <link rel="canonical" href="https://demart.com.tr/" />
DOĞRU: <link rel="canonical" href="https://demart.com.tr/en/" />
```

**Önem:** Google bu sayfayı yanlış indexleyecek, SEO'ya zarar verir.

---

## HATA 2-5: ALAKASIZ STOK FOTOĞRAFLAR (Profesyonellik Kritik)

### HATA 2: project-support.jpg
**Mevcut:** İnşaat sahası, demir donatı işçileri
**Sorun:** Vana kilitleri şirketinin "Proje Desteği" sayfasında alakasız
**Konum:** `/images/services/project-support.jpg` veya frontend'de bu görseli kullanan component
**Düzeltme:** 
- Endüstriyel vana kurulumu yapan mühendis görseli kullan
- Veya Sofis marka vana kilidi ürün görseli
- Örnek arama: "industrial valve installation engineer", "valve interlock system"

### HATA 3: operations.jpg  
**Mevcut:** Masada robot/elektronik çizimleri, kumpas
**Sorun:** "Operasyon ve Bakım" sayfası için alakasız - vana ile ilgisi yok
**Konum:** `/images/services/operations.jpg`
**Düzeltme:**
- Vana bakımı yapan teknisyen görseli
- Endüstriyel tesiste vana operasyonu görseli
- Örnek arama: "valve maintenance technician", "industrial valve operation"

### HATA 4: regulations.jpg
**Mevcut:** Havadan çekilmiş kamyon/tır parkı
**Sorun:** "Yönetmelikler ve Standartlar" sayfası için tamamen alakasız
**Konum:** `/images/services/regulations.jpg`
**Düzeltme:**
- Endüstriyel güvenlik standartları görseli
- Sertifika/belge görseli
- Vana güvenlik sistemi görseli
- Örnek arama: "industrial safety compliance", "valve safety standards certification"

### HATA 5: energy-transition.jpg
**Mevcut:** Rüzgar türbinleri (gün batımı)
**Sorun:** "Enerji Dönüşümü" başlığı olsa da sayfa vana çözümlerinden bahsediyor
**Konum:** `/images/services/energy-transition.jpg`
**Düzeltme:**
- Enerji santralinde vana sistemleri görseli
- LNG/hidrojen tesisinde vana görseli
- Örnek arama: "energy plant valve systems", "LNG facility valve"

---

## UYGULAMA TALİMATLARI

1. **Görsel Değişikliği İçin:**
   - `vision_expert_agent` kullanarak yeni görseller bul
   - Her görsel için şu formatı kullan:
   ```
   PROBLEM_STATEMENT: Vana kilitleri ve bakım şirketi için [sayfa adı] görseli
   SEARCH_KEYWORDS: [yukarıdaki önerilen arama terimleri]
   COUNT: 2-3
   ```

2. **Canonical Düzeltmesi İçin:**
   - EN sayfasının head bölümünü bul
   - canonical URL'yi `/en/` olarak güncelle

3. **Test:**
   - Değişikliklerden sonra her sayfayı kontrol et
   - Görsellerin sayfa içeriğiyle uyumlu olduğundan emin ol

---

## ÖNCELİK SIRASI
1. regulations.jpg - En alakasız (kamyon parkı?!)
2. project-support.jpg - İnşaat sahası alakasız
3. operations.jpg - Robot çizimleri alakasız
4. Canonical URL hatası - SEO için önemli
5. energy-transition.jpg - Kısmen alakalı ama geliştirilebilir

---

**NOT:** Bu hatalar AI görsel analizi ile tespit edildi. Ziyaretçiler bilinçaltında bu uyumsuzluğu fark eder ve güven kaybı yaşar. Profesyonel bir şirket imajı için düzeltilmesi şart.
