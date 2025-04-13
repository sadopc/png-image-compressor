# PNG Image Compressor

Bu proje, PNG dosyalarının boyutunu kalite kaybı olmadan küçültmeye yarayan bir araçtır. Hem grafik arayüz (GUI) hem de komut satırı (CLI) desteği sunar.

## Özellikler
- PNG dosyalarını optimize ederek boyutlarını küçültür  
- Aynı anda birden fazla dosyayı işleyebilir  
- Basit ve kullanıcı dostu grafik arayüz  
- Komut satırından da kullanılabilir  
- Sürükle-bırak desteği

## Kurulum

pip install pillow pyqt6


## Kullanım

### Grafik Arayüz:

python compression.py


### Komut Satırı:

python compression.py input_folder_or_files -o output_folder -l 6


- `-o`: Çıktı klasörü belirtir  
- `-l`: Sıkıştırma seviyesi (1–9)  
- `-r`: Klasörleri alt klasörlerle birlikte tarar

## Gereksinimler
- Python 3
- Pillow
- PyQt6
