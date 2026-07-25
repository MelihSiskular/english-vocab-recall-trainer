# Vocab Recall Trainer

Kişisel olarak ingilizce çalışırken tuttuğum CSV dosyasındaki İngilizce kelimeleri ezberlemek yerine **aktif olarak hatırlamaya** yardımcı olan terminal tabanlı bir Python uygulaması.

Uygulama kelimenin İngilizce sözlükteki anlamını gösterir ve kullanıcıdan doğru İngilizce kelimeyi yazmasını ister. Doğru cevaplanan kelimeler mevcut çalışmada tekrar sorulmaz. Yanlış cevaplanan kelimeler ise birkaç soru sonra yeniden karşıya çıkarılır. Her cevap uzun vadeli gelişim analizi için SQLite veritabanında saklanır.

## Projenin amacı

Bu proje, İngilizce öğrenen Türk kullanıcıların kişisel kelime listeleriyle düzenli çalışma yapabilmesini ve zaman içindeki ilerlemelerini ölçebilmesini amaçlar.

Yalnızca doğru ve yanlış cevap sayısını tutmak yerine şu sorulara da cevap üretir:

- Hangi kelimelerde daha çok hata yapıyorum?
- Kelimeleri başka kelimelerle mi karıştırıyorum?
- Yazım hatası mı yapıyorum, yoksa kelimeyi tamamen mi hatırlayamıyorum?
- İlk denemede doğru cevaplama oranım artıyor mu?
- Kaç yeni kelime öğrendim?
- Hangi kelimeler öğrenme aşamasında?
- Hangi kelimeleri artık istikrarlı biçimde biliyorum?


## Kurulum

Projeyi klonladıktan sonra proje klasörüne girin:

```bash
git clone <repository-url>
cd vocab-recall-trainer
```

Sanal ortam oluşturun ve etkinleştirin:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Windows PowerShell kullanıyorsanız:

```powershell
.venv\Scripts\Activate.ps1
```

Projeyi geliştirme bağımlılıklarıyla birlikte kurun:

```bash
python -m pip install -e ".[dev]"
```

## Hızlı başlangıç

Kendi CSV dosyanızı `data/input/en.csv` konumuna ekleyin ve aşağıdaki komutları çalıştırın:

```bash
vocab-trainer import data/input/en.csv
vocab-trainer audit
vocab-trainer quiz --mode all --limit 20
```

Çalışma sonrasında istatistikleri görüntülemek için:

```bash
vocab-trainer stats
```

En çok zorlanılan kelimeleri görmek için:

```bash
vocab-trainer hardest --limit 15
```

Tamamlanan çalışma oturumlarını listelemek için:

```bash
vocab-trainer sessions
```

Tüm cevap geçmişini analiz için CSV dosyasına aktarmak için:

```bash
vocab-trainer export
```

## CSV dosya formatı

Uygulamanın beklediği temel sütun yapısı aşağıdaki gibidir:

```text
İngilizce Kelime;Anlamı-1;Cümle-1;Anlamı-2;Cümle-2;Anlamı-3;Cümle-3
```

Örnek:

```text
İngilizce Kelime;Anlamı-1;Cümle-1;Anlamı-2;Cümle-2;Anlamı-3;Cümle-3
Appeal;An urgent request for something important - Çağrı;They made an appeal for help.;;;;
Grant;To give someone allow to have something that they have asked for - Onaylamak;The university granted her a scholarship.;;;;
```

Depoda örnek olarak kendş kullandığım `data/input/en.csv` dosyası bulunuyor.


## CSV içe aktarma davranışı

İçe aktarma işlemi tekrar çalıştırılabilir şekilde tasarlanmıştır.

Aynı CSV dosyası yeniden içe aktarıldığında:

- Kelimelerin anlamları ve örnek cümleleri güncellenir.
- Önceki çalışma geçmişi silinmez.
- Kelimenin öğrenme seviyesi korunur.
- Aynı kelime gereksiz şekilde yeniden oluşturulmaz.

## Çalışma modları

### Yeni kelimeler

Henüz tamamlanmış bir çalışmada görülmemiş kelimeleri sorar:

```bash
vocab-trainer quiz --mode new --limit 20
```

### Öğrenme aşamasındaki kelimeler

Daha önce çalışılmış ancak henüz istikrarlı biçimde bilinmeyen kelimeleri sorar:

```bash
vocab-trainer quiz --mode learning --limit 20
```

### Bilinen kelimeler

Tekrar edilmesi gereken bilinen kelimelerle çalışma başlatır:

```bash
vocab-trainer quiz --mode known --limit 20
```

### Tüm kelimeler

Tüm aktif kelimeler arasından çalışma oluşturur:

```bash
vocab-trainer quiz --mode all
```

## Çalışma sırasında kullanılabilecek komutlar

```text
:hint   Örnek cümleyi ipucu olarak gösterir.
:q      Çalışmayı sonlandırır.
```

İpucu gösterilirken hedef kelime cümle içinde gizlenir.

Örnek:

```text
Anlam 1: Bir şeyi resmî olarak vermek veya izin vermek

Kelime: :hint
İpucu: The university _______ her a scholarship.
```

## Tekrar sistemi

Bir kelime doğru cevaplandığında mevcut çalışma içinde yeniden sorulmaz.

Yanlış cevaplanan kelime ise hemen tekrar gösterilmez. Birkaç farklı sorudan sonra çalışma kuyruğuna yeniden eklenir. Böylece kullanıcı cevabı kısa süreli hafızadan kopyalamak yerine yeniden hatırlamak zorunda kalır.

Çalışma, seçilen bütün kelimeler en az bir kez doğru cevaplanınca tamamlanır.

## Hata sınıflandırması

Uygulama cevapları aşağıdaki hata türlerinden biriyle kaydedebilir:

| Hata türü | Açıklama |
|---|---|
| `spelling_error` | Kelime biliniyor ancak yazım hatası yapılmış. |
| `recall_failure` | Kelime hatırlanamamış. |
| `confused_with_other_word` | Listedeki başka bir kelimeyle karıştırılmış. |
| `partial_answer` | Kelime veya ifade eksik yazılmış. |
| `semantic_confusion` | Anlam olarak yakın başka bir kelime yazılmış. |
| `meaning_misinterpreted` | Gösterilen Türkçe anlam yanlış yorumlanmış. |
| `other` | Diğer hata sebepleri. |

Bazı hatalar metin benzerliği ve mevcut kelime listesi kullanılarak otomatik belirlenir. Sistem güvenilir bir karar veremezse kullanıcıdan hata sebebini seçmesini ister.

## Kelime öğrenme seviyeleri

Bir kelime tek bir doğru cevapla öğrenilmiş kabul edilmez.

| Durum | Açıklama |
|---|---|
| `new` | Kelime henüz tamamlanmış bir çalışmada görülmedi. |
| `learning` | Kelime çalışıldı ancak hatırlama performansı henüz kararlı değil. |
| `known` | Kelime son iki tamamlanmış çalışmada ilk denemede ve ipucusuz doğru cevaplandı. |
| `mastered` | Kelime son dört çalışmada ilk denemede ve ipucusuz doğru cevaplandı; çalışmalar en az yedi güne yayıldı. |

Seviye hesaplama kurallarının teknik ayrıntıları [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) dosyasında bulunur.

## Kaydedilen veriler

Her cevap SQLite veritabanına ayrı bir kayıt olarak eklenir.

Kaydedilen başlıca alanlar:

- Sorulan kelime
- Gösterilen anlamlar
- Kullanıcının cevabı
- Doğru veya yanlış sonucu
- Deneme numarası
- Cevap süresi
- İpucu kullanımı
- Metin benzerlik oranı
- Hata türü
- Karıştırılan diğer kelime
- Çalışma kimliği
- Cevap tarihi

Bu yapı, ileride pandas, matplotlib, Streamlit veya makine öğrenmesi tabanlı analizler geliştirmeye uygundur.

## İstatistikler

Aşağıdaki komut genel öğrenme durumunu gösterir:

```bash
vocab-trainer stats
```

Raporlanabilecek ölçümler:

- Toplam kelime sayısı
- Yeni kelime sayısı
- Öğrenme aşamasındaki kelimeler
- Bilinen kelimeler
- Ustalaşılan kelimeler
- Tamamlanan çalışma sayısı
- Genel doğruluk oranı
- İlk denemede doğruluk oranı
- Ortalama cevap süresi
- Son yedi günde öğrenilen yeni kelimeler
- Hata türlerinin dağılımı

## Verileri dışa aktarma

Tüm deneme geçmişini CSV olarak dışa aktarmak için:

```bash
vocab-trainer export
```

Varsayılan çıktı konumu:

```text
data/exports/attempts.csv
```

Bu dosya daha sonra veri analizi ve görselleştirme çalışmalarında kullanılabilir.

