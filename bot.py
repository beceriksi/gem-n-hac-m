import requests
import os
import time
import pandas as pd

# Ayarlar
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
MEMORY_FILE = "sent_coins.txt"

def send_tg(msg):
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage?chat_id={CHAT_ID}&text={msg}&parse_mode=Markdown"
        requests.get(url, timeout=10)
    except: pass

def get_indicators(df):
    """EMA ve MACD hesaplar"""
    try:
        df['close'] = df['close'].astype(float)
        df['vol'] = df['vol'].astype(float)
        
        # EMA 20
        ema20 = df['close'].ewm(span=20, adjust=False).mean()
        # MACD (12, 26, 9)
        exp1 = df['close'].ewm(span=12, adjust=False).mean()
        exp2 = df['close'].ewm(span=26, adjust=False).mean()
        macd = exp1 - exp2
        signal = macd.ewm(span=9, adjust=False).mean()
        
        return {
            'is_above_ema': df['close'].iloc[-1] > ema20.iloc[-1],
            'is_macd_plus': macd.iloc[-1] > signal.iloc[-1],
            'last_vol': df['vol'].iloc[-2],
            'avg_vol': df['vol'].iloc[-6:-2].mean()
        }
    except:
        return None

def analyze_coin(symbol):
    try:
        # 1. SAATLİK VERİ
        r1h = requests.get(f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval=1h&limit=50", timeout=10)
        res1h = r1h.json()
        
        # Hata kontrolü: Eğer liste değilse (hata mesajı gelmişse) çık
        if not isinstance(res1h, list): return False, 0
        
        df1h = pd.DataFrame(res1h, columns=['time', 'open', 'high', 'low', 'close', 'vol', 'close_time', 'q_vol', 'trades', 'tbb', 'tbq', 'ignore'])
        ind1h = get_indicators(df1h)
        
        # 2. 4 SAATLİK VERİ
        r4h = requests.get(f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval=4h&limit=50", timeout=10)
        res4h = r4h.json()
        
        if not isinstance(res4h, list): return False, 0
        
        df4h = pd.DataFrame(res4h, columns=['time', 'open', 'high', 'low', 'close', 'vol', 'close_time', 'q_vol', 'trades', 'tbb', 'tbq', 'ignore'])
        ind4h = get_indicators(df4h)

        if not ind1h or not ind4h: return False, 0

        # ŞARTLAR: %40 hacim artışı + 4S Trend Onayı
        volume_spike = ind1h['last_vol'] > (ind1h['avg_vol'] * 1.40)
        trend_ok = ind4h['is_above_ema'] and ind4h['is_macd_plus']
        
        if volume_spike and trend_ok:
            spike_pct = int(((ind1h['last_vol'] / ind1h['avg_vol']) - 1) * 100)
            return True, spike_pct
        return False, 0
    except:
        return False, 0

def scan():
    try:
        # Ana borsa verisini çek
        r = requests.get("https://api.binance.com/api/v3/ticker/24hr", timeout=10)
        tickers = r.json()
        
        if not isinstance(tickers, list): 
            print("Binance'den beklenen liste verisi gelmedi.")
            return

        # Hafıza oku
        sent_today = []
        if os.path.exists(MEMORY_FILE):
            with open(MEMORY_FILE, "r") as f:
                sent_today = f.read().splitlines()

        for coin in tickers:
            # Güvenlik: coin bir dict mi kontrol et
            if not isinstance(coin, dict): continue
            
            symbol = coin.get('symbol', '')
            if not symbol.endswith('USDT'): continue
            
            q_vol = float(coin.get('quoteVolume', 0))
            if q_vol < 5000000: continue

            # Hafıza kontrolü
            if any(line.startswith(symbol) and (time.time() - float(line.split(":")[1]) < 3600) for line in sent_today):
                continue

            valid, spike = analyze_coin(symbol)
            if valid:
                msg = (f"🌟 *4H TREND ONAYLI HACİM PATLAMASI*\n\n"
                       f"🪙 *Coin:* {symbol.replace('USDT', '')}\n"
                       f"📊 *1s Hacim Artışı:* %{spike}\n"
                       f"📈 *Fiyat:* {coin.get('lastPrice')} USDT\n"
                       f"🛡 *4H Trend:* Pozitif (EMA20 + MACD)\n\n"
                       f"🔗 [Binance Grafiği](https://www.binance.com/en/trade/{symbol.replace('USDT', '_USDT')})")
                
                send_tg(msg)
                with open(MEMORY_FILE, "a") as f:
                    f.write(f"{symbol}:{time.time()}\n")
                    
    except Exception as e:
        print(f"Genel Hata: {e}")

if __name__ == "__main__":
    scan()
