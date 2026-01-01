import requests
import os
import time

# Ayarlar
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
MEMORY_FILE = "sent_coins.txt"

def send_tg(msg):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage?chat_id={CHAT_ID}&text={msg}&parse_mode=Markdown"
    requests.get(url)

def check_volume_surge(symbol, interval='1h'):
    # Son 6 mumu çek (Mevcut mumu değil, bitmiş mumları analiz etmek için)
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit=6"
    try:
        data = requests.get(url).json()
        if len(data) < 6: return False, 0
        
        # Son 5 tam mumu al (indeks 5 hacimdir)
        volumes = [float(candle[5]) for candle in data[:-1]] 
        current_closed_vol = volumes[-1] # En son kapanan saatlik hacim
        avg_vol = sum(volumes[:-1]) / len(volumes[:-1]) # Önceki 4 saatin ortalaması
        
        if current_closed_vol > avg_vol * 1.50: # %50 artış (Daha sert süzgeç)
            return True, int(((current_closed_vol / avg_vol) - 1) * 100)
        return False, 0
    except:
        return False, 0

def scan():
    # 24s hacmi 5M$ üstü olanları çek (Barajı biraz yükselttik ki gereksizler gelmesin)
    url = "https://api.binance.com/api/v3/ticker/24hr"
    try:
        tickers = requests.get(url).json()
        
        # Hafıza dosyasını oku
        sent_today = []
        if os.path.exists(MEMORY_FILE):
            with open(MEMORY_FILE, "r") as f:
                sent_today = f.read().splitlines()

        for coin in tickers:
            symbol = coin['symbol']
            if not symbol.endswith('USDT'): continue
            
            # Hacim 5M$ altındaysa bakma bile
            if float(coin['quoteVolume']) < 5000000: continue

            # Hafıza kontrolü (Aynı coini saatte 1 kez at)
            is_recent = False
            for line in sent_today:
                if line.startswith(symbol):
                    if time.time() - float(line.split(":")[1]) < 3600:
                        is_recent = True; break
            if is_recent: continue

            # 1 Saatlik Sert Hacim Kontrolü
            surge, percent = check_volume_surge(symbol, '1h')
            
            if surge:
                msg = (f"🚨 *GÜÇLÜ HACİM MOMENTUMU*\n\n"
                       f"🪙 *Coin:* {symbol.replace('USDT', '')}\n"
                       f"📊 *Saatlik Artış:* %{percent}\n"
                       f"💰 *24s Hacim:* {float(coin['quoteVolume']):,.0f} USDT\n"
                       f"📈 *Fiyat Değişimi:* %{coin['priceChangePercent']}\n\n"
                       f"🔗 [Binance Grafiği](https://www.binance.com/en/trade/{symbol.replace('USDT', '_USDT')})")
                
                send_tg(msg)
                
                # Hafızaya ekle
                with open(MEMORY_FILE, "a") as f:
                    f.write(f"{symbol}:{time.time()}\n")
                    
    except Exception as e:
        print(f"Hata: {e}")

if __name__ == "__main__":
    scan()
