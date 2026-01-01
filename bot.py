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
        url = "https://www.okx.com/api/v5/market/candles"
        
        # 1 Saatlik Analiz (Tetikleyici)
        r1h = requests.get(f"{url}?instId={symbol}&bar=1H&limit=50", timeout=10).json()
        if r1h.get('code') != '0': return None
        df1h = pd.DataFrame(r1h['data'], columns=['ts', 'o', 'h', 'l', 'c', 'vol', 'volCcy', 'volCcyQuote', 'confirm'])
        df1h = df1h.rename(columns={'c': 'close', 'vol': 'vol'})
        ind1h = get_indicators(df1h[::-1])

        # 4 Saatlik Analiz (Durum Bilgisi)
        r4h = requests.get(f"{url}?instId={symbol}&bar=4H&limit=50", timeout=10).json()
        if r4h.get('code') != '0': return None
        df4h = pd.DataFrame(r4h['data'], columns=['ts', 'o', 'h', 'l', 'c', 'vol', 'volCcy', 'volCcyQuote', 'confirm'])
        df4h = df4h.rename(columns={'c': 'close', 'vol': 'vol'})
        ind4h = get_indicators(df4h[::-1])

        if not ind1h or not ind4h: return None

        # ŞART: 1 saatlikte %40 hacim artışı (Mesaj atmak için yeterli)
        volume_spike = ind1h['last_vol'] > (ind1h['avg_vol'] * 1.40)
        
        if volume_spike:
            spike_pct = int(((ind1h['last_vol'] / ind1h['avg_vol']) - 1) * 100)
            
            # 4 Saatlik Trend Durumu Belirle
            trend_score = 0
            if ind4h['is_above_ema']: trend_score += 1
            if ind4h['is_macd_plus']: trend_score += 1
            
            trend_status = ""
            if trend_score == 2:
                trend_status = "🟢 GÜÇLÜ OLUMLU (Trend + Momentum)"
            elif trend_score == 1:
                trend_status = "🟡 ZAYIF OLUMLU (Onay Bekleniyor)"
            else:
                trend_status = "🔴 OLUMSUZ (Düşüş Trendi/Tepki Yükselişi)"
                
            return {
                'spike_pct': spike_pct,
                'trend_msg': trend_status,
                'price': ind1h['current_price']
            }
        return None
    except: return None

def scan():
    try:
        tickers_url = "https://www.okx.com/api/v5/market/tickers?instType=SPOT"
        r = requests.get(tickers_url, timeout=10).json()
        if r.get('code') != '0': return

        # Hacme göre sıralayıp ilk 60 coine bakıyoruz (Hız ve Limit için)
        sorted_tickers = sorted(r['data'], key=lambda x: float(x.get('volCcy24h', 0)), reverse=True)[:60]

        sent_today = []
        if os.path.exists(MEMORY_FILE):
            with open(MEMORY_FILE, "r") as f:
                sent_today = f.read().splitlines()

        for ticker in sorted_tickers:
            symbol = ticker['instId']
            if not symbol.endswith('-USDT'): continue
            
            # Hacim kontrolü (2M USDT)
            vol_24h = float(ticker.get('volCcy24h', 0))
            if vol_24h < 2000000: continue 

            # Hafıza kontrolü (1 saat susturma)
            if any(line.startswith(symbol) and (time.time() - float(line.split(":")[1]) < 3600) for line in sent_today):
                continue

            result = analyze_okx(symbol)
            if result:
                msg = (f"🚀 *HACİM PATLAMASI YAKALANDI*\n\n"
                       f"🪙 *Coin:* {symbol.replace('-USDT', '')}\n"
                       f"📊 *1s Hacim Artışı:* %{result['spike_pct']}\n"
                       f"📈 *Fiyat:* {result['price']} USDT\n"
                       f"🕒 *4H Trend Durumu:* \n{result['trend_msg']}\n\n"
                       f"🔗 [OKX Grafiği](https://www.okx.com/market/chart/spot/{symbol.lower()})")
                
                send_tg(msg)
                with open(MEMORY_FILE, "a") as f:
                    f.write(f"{symbol}:{time.time()}\n")
            
            time.sleep(0.1) # Rate limit koruması
                    
    except Exception as e:
        print(f"Hata: {e}")

if __name__ == "__main__":
    scan()
