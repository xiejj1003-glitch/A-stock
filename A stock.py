import streamlit as st
import akshare as ak
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, time as dt_time

# ==========================================
# 页面配置
# ==========================================
st.set_page_config(
    page_title="A股判官 (T+1版)",
    page_icon="🇨🇳",
    layout="centered"
)

# ==========================================
# 核心逻辑: AkShare 数据获取
# ==========================================
def get_ashare_data(symbol):
    # 自动补全代码：如果你只输了 600519，默认它是个代码
    symbol = str(symbol).strip()
    
    try:
        # 1. 获取实时行情 (Snapshot)
        # 用东财接口，速度快
        df_spot = ak.stock_zh_a_spot_em()
        # 筛选出这只股票
        stock_info = df_spot[df_spot['代码'] == symbol]
        
        if stock_info.empty:
            return None, "找不到代码，请输入6位数字 (如 600519)"
            
        current_price = float(stock_info.iloc[0]['最新价'])
        stock_name = stock_info.iloc[0]['名称']
        high_price = float(stock_info.iloc[0]['最高'])
        low_price = float(stock_info.iloc[0]['最低'])
        change_pct = float(stock_info.iloc[0]['涨跌幅'])

        # 2. 获取分时数据 (用于画图和算 VWAP)
        # period='1' 代表1分钟数据
        df_min = ak.stock_zh_a_hist_min_em(symbol=symbol, period='1', adjust='')
        
        if df_min.empty:
            return None, "分时数据为空 (可能是停牌)"
            
        # 清洗数据
        df_min['Close'] = df_min['收盘'].astype(float)
        df_min['Volume'] = df_min['成交量'].astype(float)
        df_min['Time'] = df_min['时间']
        
        # 计算 VWAP
        v = df_min['Volume'].values
        p = df_min['Close'].values
        df_min['vwap'] = (p * v).cumsum() / v.cumsum()
        
        vwap_price = df_min['vwap'].iloc[-1]
        
        return {
            "name": stock_name,
            "code": symbol,
            "current": current_price,
            "vwap": vwap_price,
            "high": high_price,
            "low": low_price,
            "change": change_pct,
            "history": df_min
        }, None

    except Exception as e:
        return None, f"数据接口报错: {str(e)}"

# ==========================================
# UI 界面
# ==========================================
st.title("🇨🇳 A股判官 (T+1)")
st.caption("警告：A股买入即被锁定，直到次日。VWAP 是你的生命线。")

code = st.text_input("输入6位A股代码 (例如 600519, 300059):", "").strip()

if code:
    with st.spinner(f"正在连接东方财富接口分析 {code}..."):
        data, error = get_ashare_data(code)
        
        if error:
            st.error(f"❌ {error}")
        else:
            # 提取数据
            name = data['name']
            curr = data['current']
            vwap = data['vwap']
            change = data['change']
            df = data['history']
            
            # 计算乖离率
            deviation = (curr - vwap) / vwap * 100
            
            # --- 判决逻辑 (针对 A股 T+1 优化) ---
            verdict = ""
            color = ""
            reason = ""
            
            # 场景 1: 涨停 (Limit Up)
            if change > 9.8 and curr == data['high']: 
                verdict = "🔒 涨停封死 (LOCKED)"
                color = "orange"
                reason = "买不进去了。如果你在里面，恭喜；如果你在外面，别排队了，全是骗散户接盘的。"
            
            # 场景 2: 水下 (Below VWAP)
            elif curr < vwap:
                verdict = "❌ 绝对别买 (NO TOUCH)"
                color = "red"
                reason = "价格在成本线之下。T+1 制度下，你在水下买入就是自杀，今天连止损的机会都没有。"
            
            # 场景 3: 追高 (High Deviation)
            elif deviation > 4.0:
                verdict = "⚠️ 别追高 (TRAP RISK)"
                color = "orange"
                reason = f"乖离率 {deviation:.2f}% 太高。A股下午容易跳水，现在进场容易被套在山顶。"
            
            # 场景 4: 买入 (Buy)
            else:
                verdict = "✅ 低吸/持股 (BUY/HOLD)"
                color = "green"
                reason = "站稳均价线。主力资金控盘。适合在均线附近低吸。"

            # --- 显示 ---
            if color == "red": st.error(f"## {verdict}")
            elif color == "green": st.success(f"## {verdict}")
            else: st.warning(f"## {verdict}")
            
            st.info(f"💡 分析: {name} ({code}) | 涨跌幅: {change}% | {reason}")
            
            col1, col2, col3 = st.columns(3)
            col1.metric("现价", f"¥{curr}", f"{deviation:.2f}% vs 成本")
            col2.metric("机构成本 (VWAP)", f"¥{vwap:.2f}")
            col3.metric("止损参考", f"¥{vwap*0.98:.2f}")
            
            # --- 图表 ---
            st.markdown("### 📊 分时博弈图")
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=df['Time'], y=df['Close'], mode='lines', name='价格', line=dict(color='white', width=2)))
            fig.add_trace(go.Scatter(x=df['Time'], y=df['vwap'], mode='lines', name='均价(VWAP)', line=dict(color='yellow', width=2, dash='dash')))
            fig.update_layout(template="plotly_dark", height=350, margin=dict(l=0,r=0,t=0,b=0), legend=dict(orientation="h", y=1.1))
            st.plotly_chart(fig, use_container_width=True)
            
            st.caption("数据来源: AkShare (东方财富源)")
