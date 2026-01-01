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
    try:
        df['close'] = df['close'].astype(float)
        df['vol'] = df['vol'].astype(float)
        
        # EMA 20
        ema20 = df['close'].ewm(span=20, adjust=False).mean()
        # MACD
        exp1 = df['close'].ewm(span=12, adjust=False).mean()
        exp2 = df['close'].ewm(span=26, adjust=False).mean()
        macd = exp1 - exp2
        signal = macd.ewm(span=9, adjust=False).mean()
        
        return {
            'is_above_ema': df['close'].iloc[-1] > ema20.iloc[-1],
            'is_macd_plus': macd.iloc[-1] > signal.iloc[-1],
            'last_vol': df['vol'].iloc[-2],
            'avg_vol': df['vol'].iloc[-6:-2].mean(),
            'current_price': df['close'].iloc[-1]
        }
    except: return None

def analyze_okx(symbol):
    try:
        # OKX Mum Verisi Çekme (1h ve 4h)
        # bar: 1H, 4H
        url = "https://www.okx.com/api/v5/market/candles"
        
        # 1 Saatlik Analiz
        r1h = requests.get(f"{url}?instId={symbol}&bar=1H&limit=50", timeout=10).json()
        if r1h.get('code') != '0': return False, 0
        df1h = pd.DataFrame(r1h['data'], columns=['ts', 'o', 'h', 'l', 'c', 'vol', 'volCcy', 'volCcyQuote', 'confirm'])
        df1h = df1h.rename(columns={'c': 'close', 'vol': 'vol'})
        ind1h = get_indicators(df1h[::-1]) # OKX verisi ters gelir, düzeltiyoruz

        # 4 Saatlik Analiz
        r4h = requests.get(f"{url}?instId={symbol}&bar=4H&limit=50", timeout=10).json()
        if r4h.get('code') != '0': return False, 0
        df4h = pd.DataFrame(r4h['data'], columns=['ts', 'o', 'h', 'l', 'c', 'vol', 'volCcy', 'volCcyQuote', 'confirm'])
        df4h = df4h.rename(columns={'c': 'close', 'vol': 'vol'})
        ind4h = get_indicators(df4h[::-1])

        if not ind1h or not ind4h: return False, 0

        # KRİTER: 1s Hacim Patlaması (%40) + 4s Pozitif Trend
        volume_spike = ind1h['last_vol'] > (ind1h['avg_vol'] * 1.40)
        trend_ok = ind4h['is_above_ema'] and ind4h['is_macd_plus']
        
        if volume_spike and trend_ok:
            spike_pct = int(((ind1h['last_vol'] / ind1h['avg_vol']) - 1) * 100)
            return True, spike_pct
        return False, 0
    except: return False, 0

def scan():
    try:
        # OKX'te işlem gören USDT çiftlerini çek
        tickers_url = "https://www.okx.com/api/v5/market/tickers?instType=SPOT"
        r = requests.get(tickers_url, timeout=10).json()
        if r.get('code') != '0': return

        # Hafıza oku
        sent_today = []
        if os.path.exists(MEMORY_FILE):
            with open(MEMORY_FILE, "r") as f:
                sent_today = f.read().splitlines()

        for ticker in r['data']:
            symbol = ticker['instId']
            if not symbol.endswith('-USDT'): continue
            
            # 24s Hacim Filtresi (OKX verisi volCcy24h birimindedir, örn: 2M USDT)
            vol_24h = float(ticker.get('volCcy24h', 0))
            if vol_24h < 2000000: continue 

            # Hafıza kontrolü
            if any(line.startswith(symbol) and (time.time() - float(line.split(":")[1]) < 3600) for line in sent_today):
                continue

            valid, spike = analyze_okx(symbol)
            if valid:
                msg = (f"💎 *OKX TREND & HACİM ALARMI*\n\n"
                       f"🪙 *Coin:* {symbol.replace('-USDT', '')}\n"
                       f"📊 *1s Hacim Patlaması:* %{spike}\n"
                       f"🛡 *4H Trend:* Pozitif ✅\n"
                       f"💰 *24s Hacim:* {vol_24h:,.0f} USDT\n\n"
                       f"🔗 [OKX Grafiği](https://www.okx.com/market/chart/spot/{symbol.lower()})")
                
                send_tg(msg)
                with open(MEMORY_FILE, "a") as f:
                    f.write(f"{symbol}:{time.time()}\n")
            
            # API'yi yormamak için kısa bir bekleme
            time.sleep(0.1)
                    
    except Exception as e:
        print(f"Hata: {e}")

if __name__ == "__main__":
    scan()
