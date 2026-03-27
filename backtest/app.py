"""
backtest/app.py
Streamlit 回測分析介面
執行：streamlit run backtest/app.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np
from datetime import date, timedelta

from backtest.engine import run_in_sample_out_sample, is_etf
from backtest.batch import run_batch, WATCHLIST
from strategies.ma_cross import MACrossStrategy
from strategies.ma_kline import MAKlineStrategy
from strategies.double_pattern import DoublePatternStrategy


# ── 頁面設定 ────────────────────────────────────────────
st.set_page_config(
    page_title='台股回測分析',
    page_icon='📈',
    layout='wide'
)

st.title('📈 台股回測分析系統')
st.caption('含樣本內/樣本外驗證、手續費、滑價、基準對照')

# ── 側邊欄：參數設定 ────────────────────────────────────
with st.sidebar:
    st.header('⚙️ 回測設定')

    stock_id = st.text_input('股票代號', value='2330', help='例：2330 台積電、0050 元大台灣50')
    cash     = st.number_input('初始資金（元）', value=200000, step=10000, min_value=50000)

    st.subheader('📅 日期區間')
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input('開始日期', value=date(2020, 1, 1))
    with col2:
        end_date   = st.date_input('結束日期',  value=date.today())

    split_date = st.date_input(
        '樣本切割點',
        value=date(2023, 1, 1),
        help='此日期之前為訓練集（In-Sample），之後為測試集（Out-of-Sample）'
    )

    st.subheader('🔧 策略選擇')
    strategy_name = st.radio(
        '策略',
        ['均線交叉', '均線趨勢 + K線確認', 'W底/M頭 + 均線過濾（建議）'],
        index=2,
        help='W底/M頭策略訊號最嚴格，交易次數少但每次進場都有充分根據'
    )

    short_period = st.slider('短均線週期', 3, 30, 5)
    long_period  = st.slider('長均線週期', 10, 120, 20)

    body_ratio  = None
    lookback    = None
    tolerance   = None

    if strategy_name == '均線趨勢 + K線確認':
        body_ratio = st.slider(
            'K線實體佔比門檻',
            min_value=0.3, max_value=0.9, value=0.6, step=0.05,
            help='實體（收-開）佔整根K棒（最高-最低）的比例，越高代表越強勢才進場'
        )
    elif strategy_name == 'W底/M頭 + 均線過濾（建議）':
        lookback  = st.slider('回看K棒數', 20, 60, 40,
                              help='往回找幾根K棒來辨識W底/M頭，越大訊號越少但越可靠')
        tolerance = st.slider('兩底/兩頂相近容忍度', 0.02, 0.10, 0.05, step=0.01,
                              help='兩個底（或頂）的價差在此比例以內才算有效型態')

    st.subheader('💸 交易成本')
    st.info(
        '**買入手續費：** 0.1425% × 2.8折 = 0.04%\n\n'
        '**賣出手續費：** 0.04% + 證交稅 0.3% = 0.34%\n\n'
        '**滑價：** 0.1%（模擬無法用理想價格成交）'
    )

    run_btn   = st.button('🚀 開始回測', type='primary', use_container_width=True)
    batch_btn = st.button('📊 批次回測（全自選股）', use_container_width=True)


# ── 輔助函數 ────────────────────────────────────────────
def score_card(label, value, suffix='', delta=None, help_text=None):
    st.metric(label=label, value=f'{value}{suffix}', delta=delta, help=help_text)


def reliability_score(result: dict) -> tuple[int, list]:
    """計算回測可信度分數（0-100）"""
    score  = 100
    issues = []

    if result['total_trades'] < 30:
        score -= 30
        issues.append(f'⚠️ 交易筆數太少（{result["total_trades"]} 筆），建議 30 筆以上才有統計意義')
    elif result['total_trades'] < 100:
        score -= 10
        issues.append(f'💡 交易筆數尚可（{result["total_trades"]} 筆），100 筆以上更可信')

    if result['max_drawdown'] > 30:
        score -= 20
        issues.append(f'⚠️ 最大回撤過高（{result["max_drawdown"]}%），實際交易時心理壓力大')

    if result['return_pct'] > result['bh_return'] * 2 and result['total_trades'] < 50:
        score -= 20
        issues.append('⚠️ 報酬率遠高於基準但交易次數少，可能是過擬合')

    if result['sharpe'] < 0:
        score -= 15
        issues.append('⚠️ Sharpe < 0：承擔的風險沒有得到對應報酬')
    elif result['sharpe'] < 0.5:
        score -= 5
        issues.append('💡 Sharpe 偏低（< 0.5），風險調整後報酬不理想')

    if not issues:
        issues.append('✅ 沒有明顯問題')

    return max(0, score), issues


def compare_reliability(in_r, out_r) -> tuple[int, list]:
    """樣本內外一致性分析"""
    score  = 100
    issues = []

    ret_diff = abs(in_r['return_pct'] - out_r['return_pct'])
    if ret_diff > 20:
        score -= 30
        issues.append(f'🚨 樣本內外報酬差距過大（{ret_diff:.1f}%），策略可能過擬合')
    elif ret_diff > 10:
        score -= 15
        issues.append(f'⚠️ 樣本內外報酬有差距（{ret_diff:.1f}%），需留意')

    if in_r['return_pct'] > 0 and out_r['return_pct'] < 0:
        score -= 30
        issues.append('🚨 樣本外測試虧損！策略在新資料上無效')

    wr_diff = abs(in_r['win_rate'] - out_r['win_rate'])
    if wr_diff > 15:
        score -= 20
        issues.append(f'⚠️ 勝率差距過大（{wr_diff:.1f}%），不穩定')

    if not issues:
        issues.append('✅ 樣本內外表現一致，策略較為穩健')

    return max(0, score), issues


# ── 主要介面 ────────────────────────────────────────────
# ── 批次回測 ────────────────────────────────────────────
if batch_btn:
    if strategy_name == '均線交叉':
        b_cls    = MACrossStrategy
        b_params = {'short_period': short_period, 'long_period': long_period, 'printlog': False}
    elif strategy_name == '均線趨勢 + K線確認':
        b_cls    = MAKlineStrategy
        b_params = {'short_period': short_period, 'long_period': long_period,
                    'body_ratio': body_ratio, 'printlog': False}
    else:
        b_cls    = DoublePatternStrategy
        b_params = {'long_period': long_period, 'lookback': lookback,
                    'tolerance': tolerance, 'printlog': False}

    st.subheader('📊 批次回測 — 全自選股')
    st.caption(f'{start_date} ～ {end_date}　策略：{strategy_name}')

    progress = st.progress(0, text='準備中...')
    status   = st.empty()
    rows     = []

    for i, stock in enumerate(WATCHLIST):
        sid  = stock['id']
        name = stock['name']
        progress.progress((i + 1) / len(WATCHLIST), text=f'回測 {name}({sid})...')
        try:
            from data.fetch import get_price_history
            import os
            token = os.getenv('FINMIND_TOKEN', '') or None
            df_s  = get_price_history(sid, start_date.strftime('%Y-%m-%d'),
                                      end_date.strftime('%Y-%m-%d'), token)
            if len(df_s) < 30:
                continue
            from backtest.engine import run_single
            r = run_single(df_s, b_cls, b_params, cash=cash, stock_id=sid)
            rows.append({
                '代號': sid, '名稱': name,
                '類型': 'ETF' if is_etf(sid) else '個股',
                '策略報酬%': r['return_pct'],
                '買入持有%': r['bh_return'],
                '超額報酬%': round(r['return_pct'] - r['bh_return'], 2),
                'Sharpe': r['sharpe'],
                '最大回撤%': -r['max_drawdown'],
                '交易次數': r['total_trades'],
                '勝率%': r['win_rate'],
            })
        except Exception as e:
            status.warning(f'{name}({sid}) 錯誤: {e}')

    progress.empty()

    if rows:
        import plotly.express as px
        bdf = pd.DataFrame(rows).sort_values('超額報酬%', ascending=False)

        # 顏色標示超額報酬
        def color_excess(val):
            if isinstance(val, float):
                color = '#4CAF50' if val > 0 else '#F44336'
                return f'color: {color}'
            return ''

        st.dataframe(
            bdf.style.map(color_excess, subset=['超額報酬%']),
            use_container_width=True, height=500
        )

        # 長條圖
        fig_b = px.bar(
            bdf, x='名稱', y=['策略報酬%', '買入持有%'],
            barmode='group', title='各股策略 vs 買入持有報酬',
            color_discrete_sequence=['#2196F3', '#FF9800'],
            text_auto='.1f'
        )
        fig_b.update_layout(height=450, xaxis_tickangle=-30)
        st.plotly_chart(fig_b, use_container_width=True)

        # 散佈圖：Sharpe vs 報酬
        fig_s = px.scatter(
            bdf, x='策略報酬%', y='Sharpe', text='名稱',
            color='類型', size='交易次數',
            title='Sharpe Ratio vs 報酬率（泡泡大小=交易次數）',
            color_discrete_map={'個股': '#2196F3', 'ETF': '#FF9800'}
        )
        fig_s.update_traces(textposition='top center')
        fig_s.update_layout(height=450)
        st.plotly_chart(fig_s, use_container_width=True)
    else:
        st.error('所有股票都無法取得資料')

if run_btn:
    if start_date >= split_date or split_date >= end_date:
        st.error('日期設定有誤：開始日期 < 切割點 < 結束日期')
        st.stop()

    if strategy_name == '均線交叉':
        strategy_cls    = MACrossStrategy
        strategy_params = {'short_period': short_period, 'long_period': long_period, 'printlog': False}
    elif strategy_name == '均線趨勢 + K線確認':
        strategy_cls    = MAKlineStrategy
        strategy_params = {'short_period': short_period, 'long_period': long_period,
                           'body_ratio': body_ratio, 'printlog': False}
    else:
        strategy_cls    = DoublePatternStrategy
        strategy_params = {'long_period': long_period, 'lookback': lookback,
                           'tolerance': tolerance, 'printlog': False}

    with st.spinner(f'正在抓取 {stock_id} 資料並執行回測...'):
        try:
            result = run_in_sample_out_sample(
                stock_id        = stock_id,
                start           = start_date.strftime('%Y-%m-%d'),
                split           = split_date.strftime('%Y-%m-%d'),
                end             = end_date.strftime('%Y-%m-%d'),
                strategy_cls    = strategy_cls,
                strategy_params = strategy_params,
                cash            = cash,
            )
        except Exception as e:
            st.error(f'回測錯誤：{e}')
            st.stop()

    in_r   = result['in']
    out_r  = result['out']
    full_r = result['full']

    # ── 白話解讀 ────────────────────────────────────────
    def plain_summary(full_r, in_r, out_r, stock_id):
        """用國中生也看得懂的語言說明回測結果"""
        r = full_r
        c_score, _ = compare_reliability(in_r, out_r)

        # 報酬判斷
        if r['return_pct'] >= r['bh_return']:
            ret_msg = f"這個策略比「買了放著不動」還賺，多賺了 {r['return_pct'] - r['bh_return']:.1f}%。"
        else:
            ret_msg = f"這個策略的報酬（{r['return_pct']}%）沒有比「買了放著不動」（{r['bh_return']}%）好。說白了，直接買不動比較划算。"

        # Sharpe 判斷
        if r['sharpe'] >= 1:
            sharpe_msg = f"Sharpe {r['sharpe']}，代表每承擔 1 單位風險，能賺到超過 1 倍回報。很好。"
        elif r['sharpe'] >= 0.5:
            sharpe_msg = f"Sharpe {r['sharpe']}，還算可以，但不算出色。"
        elif r['sharpe'] >= 0:
            sharpe_msg = f"Sharpe {r['sharpe']}，冒了風險但賺得不多，不理想。"
        else:
            sharpe_msg = f"Sharpe {r['sharpe']} 是負的，意思是這個策略在本段期間不如什麼都不做。"

        # 回撤判斷
        dd = r['max_drawdown']
        if dd < 10:
            dd_msg = f"最大回撤只有 {dd}%，相當穩健，心理壓力小。"
        elif dd < 20:
            dd_msg = f"最大回撤 {dd}%，帳面曾經虧損這麼多，能忍住才能等到後來的獲利。"
        elif dd < 35:
            dd_msg = f"最大回撤 {dd}%，帳面曾跌超過三成，一般人這時候都會忍不住賣掉。"
        else:
            dd_msg = f"最大回撤高達 {dd}%，幾乎等於帳面腰斬。這種壓力很難堅持下去。"

        # 可信度
        if c_score >= 70:
            trust_msg = "訓練期和測試期表現接近，策略比較可信，不是只靠運氣。"
        elif c_score >= 50:
            trust_msg = "訓練期和測試期有些落差，策略穩定性一般，實際操作要小心。"
        else:
            trust_msg = "訓練期和測試期差很多，這個策略可能只是剛好適合過去，不代表未來也有效。"

        # 交易次數
        n = r['total_trades']
        if n < 30:
            n_msg = f"只有 {n} 筆交易，樣本太少，這個結果可能只是運氣，不能當真。"
        else:
            n_msg = f"共 {n} 筆交易，樣本量{'足夠' if n >= 100 else '還可以'}。"

        return f"""
**用大白話說：**

{ret_msg}

{sharpe_msg}

{dd_msg}

{n_msg}

{trust_msg}

**結論：{'這個策略值得進一步研究。' if c_score >= 60 and r['sharpe'] >= 0.5 else '建議調整參數或換個策略，目前結果不夠可信。'}**
"""

    # ── Tab 架構 ────────────────────────────────────────
    tab1, tab2, tab3, tab4 = st.tabs([
        '📊 總覽', '🔬 樣本內/外驗證', '📋 交易明細', '📖 說明'
    ])

    # ════════════════════════════════
    # Tab1：總覽
    # ════════════════════════════════
    with tab1:
        st.subheader(f'📌 {stock_id}  {start_date} ～ {end_date}  全期回測')

        # ── 白話解讀（最上方，最重要）──
        st.info(plain_summary(full_r, in_r, out_r, stock_id))

        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            score, _ = reliability_score(full_r)
            color = '🟢' if score >= 70 else '🟡' if score >= 50 else '🔴'
            st.metric('可信度分數', f'{color} {score}/100',
                      help='70以上：可信　50-70：參考　50以下：不可信')
        with col2:
            delta_str = f'買入持有 {full_r["bh_return"]:+.2f}%'
            score_card('策略報酬', full_r['return_pct'], '%', delta=delta_str,
                       help_text='藍字=跑贏買入持有 紅字=跑輸')
        with col3:
            sharpe = full_r['sharpe']
            sharpe_label = '優秀' if sharpe>=1 else '良好' if sharpe>=0.5 else '偏低' if sharpe>=0 else '差'
            score_card('Sharpe（風險報酬比）', sharpe,
                       help_text=f'現在：{sharpe_label}　>1優秀　0.5~1良好　<0差')
        with col4:
            dd = full_r['max_drawdown']
            dd_label = '穩健' if dd<10 else '可接受' if dd<20 else '偏高' if dd<35 else '危險'
            score_card('最大回撤（最多虧多少）', -dd, '%',
                       help_text=f'現在：{dd_label}　代表帳面曾虧損這麼多，要撐得住才行')
        with col5:
            n = full_r['total_trades']
            n_label = '樣本足夠' if n>=100 else '樣本尚可' if n>=30 else '樣本太少'
            score_card('交易次數', n,
                       help_text=f'現在：{n_label}　30筆以下不可信')

        # 資產曲線
        st.subheader('📈 資產曲線 vs 買入持有')
        eq = full_r['equity_curve']
        price_df = full_r['price_df']
        bh = (price_df['close'] / price_df['close'].iloc[0]) * cash

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=eq.index, y=eq.values,
            name='策略', line=dict(color='#2196F3', width=2)
        ))
        fig.add_trace(go.Scatter(
            x=bh.index, y=bh.values,
            name='買入持有（基準）',
            line=dict(color='#FF9800', width=2, dash='dot')
        ))
        fig.add_vline(x=result['split'], line_dash='dash', line_color='gray')
        fig.add_annotation(
            x=result['split'], y=1, yref='paper',
            text='樣本切割點', showarrow=False,
            xanchor='left', font=dict(color='gray', size=12)
        )
        fig.update_layout(
            height=400, hovermode='x unified',
            legend=dict(orientation='h', yanchor='bottom', y=1.02),
            yaxis_title='資產（元）', xaxis_title=''
        )
        st.plotly_chart(fig, use_container_width=True)

        # 圖表說明
        with st.expander("📖 這張圖怎麼看？"):
            st.markdown("""
- **藍線（策略）**：用這個策略操作，你的帳戶資金變化
- **橘虛線（買入持有）**：假設一開始買了就放著不動，資金變化
- **灰色虛線（切割點）**：左邊是「訓練期」，右邊是「測試期」
- **藍線在橘線上方** → 策略比買入持有賺更多，值得考慮
- **藍線在橘線下方** → 還不如買了放著，這個策略沒有價值
- **藍線大幅波動** → 策略進出頻繁，交易成本高，心理壓力大
""")

        # 可信度問題列表
        _, issues = reliability_score(full_r)
        st.subheader('🔍 回測精準度檢查')
        for i in issues:
            st.write(i)

    # ════════════════════════════════
    # Tab2：樣本內/外驗證
    # ════════════════════════════════
    with tab2:
        st.subheader('🔬 樣本內 vs 樣本外一致性分析')
        st.caption(
            f'**訓練集（In-Sample）：** {start_date} ～ {split_date}　|　'
            f'**測試集（Out-of-Sample）：** {split_date} ～ {end_date}'
        )

        # 一致性分數
        c_score, c_issues = compare_reliability(in_r, out_r)
        color = '🟢' if c_score >= 70 else '🟡' if c_score >= 50 else '🔴'
        st.metric('樣本內外一致性', f'{color} {c_score}/100',
                  help='兩段績效越接近，策略越不容易是過擬合')

        for i in c_issues:
            st.write(i)

        st.divider()

        # 比較表格
        compare_data = {
            '指標': ['報酬率 %', '買入持有 %', 'Sharpe', '最大回撤 %', '交易次數', '勝率 %'],
            '樣本內（訓練）': [
                f'{in_r["return_pct"]:+.2f}%',
                f'{in_r["bh_return"]:+.2f}%',
                f'{in_r["sharpe"]:.3f}',
                f'{in_r["max_drawdown"]:.2f}%',
                in_r['total_trades'],
                f'{in_r["win_rate"]:.1f}%',
            ],
            '樣本外（測試）': [
                f'{out_r["return_pct"]:+.2f}%',
                f'{out_r["bh_return"]:+.2f}%',
                f'{out_r["sharpe"]:.3f}',
                f'{out_r["max_drawdown"]:.2f}%',
                out_r['total_trades'],
                f'{out_r["win_rate"]:.1f}%',
            ],
        }
        # 樣本驗證白話說明
        ret_diff = abs(in_r['return_pct'] - out_r['return_pct'])
        if ret_diff <= 10 and out_r['return_pct'] > 0:
            valid_msg = f"✅ **通過驗證**：訓練期報酬 {in_r['return_pct']}%，測試期 {out_r['return_pct']}%，差距只有 {ret_diff:.1f}%，表現一致，策略可信。"
        elif out_r['return_pct'] < 0:
            valid_msg = f"❌ **未通過**：測試期虧損 {out_r['return_pct']}%，策略在沒見過的資料上失效，不能用。"
        else:
            valid_msg = f"⚠️ **部分通過**：訓練期 {in_r['return_pct']}%，測試期 {out_r['return_pct']}%，差距 {ret_diff:.1f}%，實際操作要保守。"
        st.info(valid_msg)

        with st.expander("📖 樣本內/外驗證是什麼意思？"):
            st.markdown(f"""
把歷史資料分成兩段：
- **訓練期（{start_date} ～ {split_date}）**：用來設計策略，就像讀課本
- **測試期（{split_date} ～ {end_date}）**：策略沒有看過的新資料，就像考試

**判斷標準：**
- 兩段報酬差距 < 10%，且測試期也獲利 → 策略真的有效
- 測試期虧損 → 策略只是「背答案」，換新資料就失效
- 差距 > 20% → 過擬合，不能信
""")

        st.dataframe(pd.DataFrame(compare_data).set_index('指標'),
                     use_container_width=True)

        # 各段資產曲線
        fig2 = go.Figure()
        for label, r, color in [
            ('樣本內策略', in_r, '#2196F3'),
            ('樣本外策略', out_r, '#4CAF50'),
        ]:
            eq  = r['equity_curve']
            bh  = (r['price_df']['close'] / r['price_df']['close'].iloc[0]) * cash
            fig2.add_trace(go.Scatter(x=eq.index, y=eq.values,
                                      name=label, line=dict(color=color, width=2)))
            fig2.add_trace(go.Scatter(x=bh.index, y=bh.values,
                                      name=f'{label[:3]}買入持有',
                                      line=dict(color=color, width=1, dash='dot')))

        fig2.update_layout(height=400, hovermode='x unified',
                           yaxis_title='資產（元）',
                           legend=dict(orientation='h', yanchor='bottom', y=1.02))
        st.plotly_chart(fig2, use_container_width=True)

        # 各期報酬柱狀圖
        bar_df = pd.DataFrame({
            '期間': ['樣本內', '樣本外'],
            '策略報酬': [in_r['return_pct'], out_r['return_pct']],
            '買入持有': [in_r['bh_return'], out_r['bh_return']],
        })
        fig3 = px.bar(bar_df, x='期間', y=['策略報酬', '買入持有'],
                      barmode='group', title='策略 vs 買入持有 報酬比較',
                      color_discrete_sequence=['#2196F3', '#FF9800'])
        fig3.update_layout(height=350, yaxis_title='報酬率 %')
        st.plotly_chart(fig3, use_container_width=True)

    # ════════════════════════════════
    # Tab3：交易明細
    # ════════════════════════════════
    with tab3:
        st.subheader('📋 全期交易明細')

        # 交易統計白話說明
        trades = full_r['trades']
        if trades:
            wins   = sum(1 for t in trades if t['pnl_comm'] > 0)
            losses = len(trades) - wins
            avg_win  = sum(t['pnl_comm'] for t in trades if t['pnl_comm'] > 0) / max(wins,1)
            avg_loss = sum(t['pnl_comm'] for t in trades if t['pnl_comm'] <= 0) / max(losses,1)
            rr = abs(avg_win / avg_loss) if avg_loss != 0 else 0

            st.info(
                f"共 **{len(trades)}** 筆交易，獲利 **{wins}** 筆，虧損 **{losses}** 筆，"
                f"勝率 **{full_r['win_rate']}%**。\n\n"
                f"平均每筆獲利 **{avg_win:.0f} 元**，平均每筆虧損 **{avg_loss:.0f} 元**。\n"
                f"盈虧比 **{rr:.2f}**（{'高於1代表平均每次賺的比虧的多，好事' if rr>=1 else '低於1代表平均每次賺的比虧的少，需要高勝率才能獲利'}）"
            )

            with st.expander("📖 損益分佈圖怎麼看？"):
                st.markdown("""
- **橫軸**：每筆交易賺或虧多少元（正數=賺，負數=虧）
- **縱軸**：這個金額出現幾次
- **紅線（0元）**：左邊是虧損，右邊是獲利
- 理想分佈：柱子集中在紅線右邊，且右邊有幾根很高的柱子（代表偶爾有大賺）
- 危險分佈：左邊有很長的尾巴（代表偶爾有大虧）
""")
        if trades:
            df_trades = pd.DataFrame(trades)
            df_trades['result'] = df_trades['pnl_comm'].apply(
                lambda x: '✅ 獲利' if x > 0 else '❌ 虧損'
            )
            df_trades.columns = ['進場日', '出場日', '損益（稅前）', '損益（含費用）', '結果']

            # 顏色標示
            st.dataframe(
                df_trades.style.map(
                    lambda v: 'color: #4CAF50' if '獲利' in str(v) else
                              'color: #F44336' if '虧損' in str(v) else '',
                    subset=['結果']
                ),
                use_container_width=True,
                height=400
            )

            # 損益分佈
            pnl_list = [t['pnl_comm'] for t in trades]
            fig4 = px.histogram(x=pnl_list, nbins=30,
                                title='損益分佈（每筆交易）',
                                labels={'x': '損益（元）', 'y': '次數'},
                                color_discrete_sequence=['#2196F3'])
            fig4.add_vline(x=0, line_color='red', line_dash='dash')
            fig4.update_layout(height=300)
            st.plotly_chart(fig4, use_container_width=True)
        else:
            st.info('此期間沒有完成的交易')

    # ════════════════════════════════
    # Tab4：說明
    # ════════════════════════════════
    with tab4:
        st.subheader('📖 如何判斷回測是否可信')

        st.markdown("""
### 📐 策略邏輯說明

**均線交叉（基本版）**
- 短均線向上穿越長均線 → 買入
- 短均線向下穿越長均線 → 賣出
- 缺點：只看均線，會有很多假訊號

**均線趨勢 + K線確認**
- 買入：短均 > 長均（上升趨勢）**且** 當天出現強勢陽線
- 賣出：趨勢反轉（死亡交叉）**或** 出現強勢陰線
- 優點：兩個條件同時確認，過濾掉很多假訊號

**W底/M頭 + 均線過濾（建議）**
- 買入：偵測到 W底型態（兩個相近低點，後突破頸線）**且** 收盤在均線之上
- 賣出：偵測到 M頭型態（兩個相近高點，後跌破頸線）**或** 趨勢轉空
- 優點：訊號最嚴格，交易次數少，每次進場都有完整型態根據
- ⚠️ 注意：圖表上「M頭必跌 100%」的說法**不正確**，實際統計勝率約 55~65%

**K線實體佔比**（均線+K線策略）
- 整根K棒 = 最高價 - 最低價；實體 = |收盤 - 開盤|
- 比例越高 = 進場條件越嚴格

---

### 🎯 可信度分數說明

| 分數 | 代表意義 |
|------|---------|
| 🟢 70-100 | 回測設計合理，可以進一步研究這個策略 |
| 🟡 50-69 | 有些問題需要注意，不建議直接實盤 |
| 🔴 0-49 | 嚴重問題，這個回測結果不可信 |

---

### 🔬 樣本內/外驗證的意義

這是最重要的精準度測試：

1. **樣本內（In-Sample）**：用來「設計」策略的期間，就像考試前的練習題
2. **樣本外（Out-of-Sample）**：策略「沒見過」的新資料，就像正式考試

> **黃金法則：** 如果策略在樣本外表現很差，代表它只是「記住」了歷史，不是真的找到規律。

---

### ⚠️ 常見回測陷阱

| 問題 | 說明 | 如何辨識 |
|------|------|---------|
| **過擬合** | 策略只適合歷史數據 | 樣本內外報酬差距 > 20% |
| **未來函數** | 用了「當時還不知道」的資訊 | 下單時間異常精準 |
| **存活者偏差** | 只回測現在還活著的股票 | 本系統使用 FinMind 完整歷史 |
| **交易次數太少** | 30 筆以下沒有統計意義 | 可能是「運氣好」不是策略好 |

---

### 📊 指標解讀

**Sharpe Ratio（夏普值）**
- > 1.0：優秀，冒的風險有充分報酬
- 0.5~1.0：良好
- 0~0.5：風險報酬不對等
- < 0：承擔風險但沒有報酬

**最大回撤（Max Drawdown）**
- 代表從高點到低點最多虧損幾 %
- 超過 20% 時，實際操作很難撐住不停損
- 建議控制在 15% 以內

**買入持有基準**
- 如果策略跑不贏「買了放著不動」，那這個策略沒有價值
- 尤其要看**同期間**的比較

---

### 💡 下一步建議

1. 調整均線週期，找到樣本外也表現不錯的參數
2. 試試其他策略（RSI、布林通道）
3. 加入停損停利機制
4. 多測幾支股票，看策略是否普遍有效
        """)

else:
    st.info('👈 在左側設定參數，點擊「開始回測」')

    st.markdown("""
    ### 使用說明
    1. 輸入**股票代號**（台積電 `2330`、元大台灣50 `0050`）
    2. 設定**日期區間**和**樣本切割點**
    3. 調整**均線週期**
    4. 點擊**開始回測**

    系統會自動：
    - ✅ 套用正確手續費（含證交稅）
    - ✅ 加入滑價模擬
    - ✅ 與買入持有基準對照
    - ✅ 做樣本內/外一致性驗證
    - ✅ 給出可信度評分
    """)
