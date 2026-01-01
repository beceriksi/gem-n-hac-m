import requests
import os
import time
import pandas as pd

# ... (send_tg ve get_indicators kısımları aynı kalıyor, sadece RSI ekliyoruz)

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
        
        # RSI (14)
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        return {
            'is_above_ema': df['close'].iloc[-1] > ema20.iloc[-1],
            'is_macd_plus': macd.iloc[-1] > signal.iloc[-1],
            'last_vol': df['vol'].iloc[-2],
            'avg_vol': df['vol'].iloc[-6:-2].mean(),
            'rsi': rsi.iloc[-1],
            'price_change': ((df['close'].iloc[-1] / df['close'].iloc[-2]) - 1) * 100,
            'current_price': df['close'].iloc[-1]
        }
    except: return None

# analyze_okx fonksiyonunda mesaj kısmını şöyle güncelleyelim:
# (Diğer kısımlar yukarıdakiyle aynı kalacak şekilde düzenle)

# ... (analiz kodları içinde)
            rsi_val = result['rsi']
            rsi_msg = "💎 Sağlıklı" if rsi_val < 70 else "⚠️ Şişmiş (Dikkat!)"
            
            msg = (f"🚀 *HACİM ANALİZİ: {symbol.replace('-USDT', '')}*\n\n"
                   f"📊 *Hacim Artışı:* %{result['spike_pct']}\n"
                   f"📈 *Fiyat Değişimi (1s):* %{result['price_change']:.2f}\n"
                   f"🌡 *RSI (Şişkinlik):* {rsi_val:.1f} {rsi_msg}\n"
                   f"🕒 *4H Trend:* {result['trend_msg']}\n\n"
                   f"💡 *Tavsiye:* RSI 70 üzeriyse tepeden girmeyin, düzeltme bekleyin.")
