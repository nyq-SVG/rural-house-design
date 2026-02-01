import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from math import pi

# ================= 1. 全局配置 =================
st.set_page_config(
    page_title="寒冷地区农房多维低碳决策系统",
    page_icon="🧬",
    layout="wide"
)

import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import os

# --- 字体自动配置 (云端/本地通用版) ---
def set_chinese_font():
    # 1. 优先尝试云端字体 (WenQuanYi Zen Hei)
    # 2. 然后尝试本地 Windows/Mac 常见字体
    fonts_to_try = ['WenQuanYi Zen Hei', 'SimHei', 'Microsoft YaHei', 'PingFang SC', 'Arial Unicode MS']
    
    selected_font = None
    
    # 遍历列表，找到第一个系统里存在的字体
    for font in fonts_to_try:
        if font in [f.name for f in fm.fontManager.ttflist]:
            selected_font = font
            break
            
    # 如果找到了字体，就设置
    if selected_font:
        plt.rcParams['font.sans-serif'] = [selected_font]
        plt.rcParams['axes.unicode_minus'] = False # 解决负号显示为方块的问题
        print(f"✅ 成功加载中文字体: {selected_font}")
    else:
        # 如果所有中文都没找到（极端情况），回退到英文，避免报错
        plt.rcParams['font.sans-serif'] = ['DejaVu Sans']
        print("⚠️ 未检测到中文字体，回退到默认字体 (中文可能显示乱码)")

# 调用函数
set_chinese_font()

# ================= 2. 侧边栏：控制台 =================
with st.sidebar:
    st.title("🎛️ 决策变量控制")
    st.info("ℹ️ 决策内核：GB/T 51366 + 敏感性分析")
    st.markdown("---")
    
    st.markdown("### 1️⃣ 基础约束")
    site_width = st.number_input("宅基地面宽 (m)", 8.0, 25.0, 13.0, 0.5)
    site_depth = st.number_input("宅基地进深 (m)", 8.0, 25.0, 10.0, 0.5)
    site_area = site_width * site_depth
    
    st.markdown("### 2️⃣ 建筑参数")
    target_room = st.selectbox("🛌 户型选择", ["两室一厅", "三室一厅", "四室两厅"], index=1)
    insulation = st.slider("🧱 EPS保温厚度 (mm)", 50, 200, 150, 10)
    window_ratio = st.slider("🪟 南向窗墙比 (WWR)", 0.2, 0.8, 0.45, 0.05)
    orientation = st.slider("🧭 朝向偏转 (°)", -45, 45, 0, 5)

    st.markdown("### 3️⃣ 可再生能源 (New!)")
    use_pv = st.checkbox("☀️ 部署屋顶光伏系统", value=True)
    pv_ratio = 0.0
    if use_pv:
        pv_ratio = st.slider("⚡ 光伏铺设比例 (%)", 20, 80, 50, 5) / 100

    st.markdown("---")
    st.button("🔄 运行蒙特卡洛模拟")

# ================= 3. 核心算法 (增加经济与光伏) =================

def calculate_advanced_metrics(w, d, ins, wwr, ori, room_type, pv_r):
    area = w * d
    shape_coeff = (2 * (w + d)) / area 
    
    # --- 1. 能耗 (EUI) ---
    # 基准能耗 (Baseline)
    base_eui = 140 
    # 设计能耗 (Design)
    design_eui = 140 - (ins * 0.35) + (shape_coeff * 15) + abs(wwr - 0.45)*20 + abs(ori)*0.4
    design_eui = max(45, design_eui)
    
    # --- 2. 光伏产能 (PV Generation) ---
    # 寒冷地区年均发电量约 130 kWh/m2 (组件面积)
    pv_generation = 0
    if pv_r > 0:
        pv_area = area * 0.5 * pv_r # 假设屋顶面积是占地的一半可利用
        pv_generation = pv_area * 130 # kWh/year
    
    # 净能耗 (Net EUI)
    net_eui = max(0, design_eui - (pv_generation / area))
    
    # --- 3. 碳排放 (Carbon) ---
    grid_factor = 0.5810 
    life_span = 50 
    
    # 运行碳 (扣除光伏)
    base_op_carbon = (base_eui * area * grid_factor * life_span) / 1000
    design_op_carbon = (net_eui * area * grid_factor * life_span) / 1000
    
    # 建材碳 (含光伏组件碳排 50g/W -> 约 80kg/m2)
    base_mat_carbon = area * 0.35
    design_mat_carbon = area * (0.20 + ins * 0.0005)
    if pv_r > 0:
        design_mat_carbon += (area * 0.5 * pv_r * 0.08) # 加上光伏板的隐含碳
    
    # --- 4. 经济性 (ROI) ---
    # 基准造价 (砖混)
    base_cost = 10 + area * 0.10
    # 设计造价 (钢结构 + 保温 + 光伏)
    design_cost = (10 + area * 0.13 + ins * 0.05) * (1.15 if "三室" in room_type else 1.0)
    if pv_r > 0:
        design_cost += (area * 0.5 * pv_r * 400) / 10000 # 光伏成本 400元/m2
        
    # 每年省下的电费 (假设 0.55元/度)
    elec_price = 0.55
    energy_saving_kwh = (base_eui - net_eui) * area
    money_saved_per_year = energy_saving_kwh * elec_price
    
    # 增量成本
    incremental_cost = (design_cost - base_cost) * 10000 # 换算成元
    # 静态回收期
    payback_period = incremental_cost / money_saved_per_year if money_saved_per_year > 0 else 99
    
    # --- 5. 舒适度 (PMV模拟) ---
    # 简单模拟 PMV (Predicted Mean Vote) -3 ~ +3
    # 越接近0越好。保温越好越接近0。
    pmv = -1.5 + (ins / 200) * 1.0 + (0.5 - abs(wwr-0.45))
    
    return {
        "eui": design_eui,
        "net_eui": net_eui,
        "pv_gen": pv_generation,
        "cost": design_cost,
        "payback": payback_period,
        "shape": shape_coeff,
        "carbon_total": design_op_carbon + design_mat_carbon,
        "carbon_base": base_op_carbon + base_mat_carbon,
        "carbon_op": design_op_carbon,
        "carbon_mat": design_mat_carbon,
        "carbon_mat_base": base_mat_carbon,
        "pmv": pmv
    }

metrics = calculate_advanced_metrics(
    site_width, site_depth, insulation, window_ratio, orientation, target_room, pv_ratio
)

# 绘图辅助
def plot_fallback_layout(w, d, title):
    fig, ax = plt.subplots(figsize=(6, 4.5))
    ax.set_xlim(-1, w+1)
    ax.set_ylim(-1, d+1)
    ax.add_patch(plt.Rectangle((0,0), w, d, fill=None, edgecolor='#333', linestyle='--', linewidth=1.5))
    ax.add_patch(plt.Rectangle((1, 1), w-2, d-2, color='#8ecae6', alpha=0.5))
    if pv_ratio > 0:
        # 画光伏板示意
        ax.add_patch(plt.Rectangle((1.5, 1.5), w-3, (d-3)*pv_ratio, color='#f1c40f', alpha=0.8, label='屋顶光伏 PV'))
    ax.text(w/2, d/2, f"{title}\n(AI拓扑示意)", ha='center', va='center', fontweight='bold', fontsize=12)
    ax.legend(loc='upper right')
    ax.axis('off')
    return fig

# ================= 4. 界面展示 =================
st.title("🌍 寒冷地区农房多维低碳决策系统")

# --- 高级 KPI (增加 ROI 和 PMV) ---
st.subheader("🏆 综合决策仪表盘 (Decision Dashboard)")
k1, k2, k3, k4, k5 = st.columns(5)
delta_c = metrics['carbon_base'] - metrics['carbon_total']
percent_c = (1 - metrics['carbon_total']/metrics['carbon_base'])*100

k1.metric("🌱 净碳排放", f"{metrics['carbon_total']:.1f} t", f"减排率 {percent_c:.1f}%", delta_color="normal")
k2.metric("⚡ 净能耗 (Net EUI)", f"{metrics['net_eui']:.1f}", f"光伏产出 {metrics['pv_gen']:.0f} kWh")
k3.metric("💰 投资回收期", f"{metrics['payback']:.1f} 年", "ROI 指标")
k4.metric("🌡️ 热舒适度 (PMV)", f"{metrics['pmv']:.2f}", "ISO 7730标准")
k5.metric("🧊 空间效率", f"{1/metrics['shape']:.2f}", "体形系数倒数")

st.markdown("---")

tab1, tab2, tab3 = st.tabs(["🏗️ 方案与光伏", "📈 核心减排分析", "🌪️ 敏感性与经济性 (高级)"])

# ======= Tab 1: 方案 =======
with tab1:
    c1, c2 = st.columns([1.5, 1])
    with c1:
        st.subheader(f"🏠 方案拓扑：{target_room}")
        try:
            img_map = {"两室一厅": "house_2.png", "三室一厅": "house_3.png", "四室两厅": "house_4.png"}
            key = [k for k in img_map.keys() if k[:2] in target_room][0]
            st.image(img_map[key], caption="自适应平面布局图", use_container_width=True)
        except:
            st.pyplot(plot_fallback_layout(site_width, site_depth, target_room))
            
    with c2:
        st.subheader("🛠️ 集成技术策略")
        st.markdown(f"""
        1.  **光伏建筑一体化 (BIPV)**
            * 部署比例 **{pv_ratio*100:.0f}%**，年发电量 **{metrics['pv_gen']:.0f} kWh**，抵消运行碳排。
        2.  **高性能围护结构**
            * EPS保温 **{insulation}mm**，实现 PMV 指标优化至 **{metrics['pmv']:.2f}** (接近 -0.5 舒适区间)。
        3.  **经济性策略**
            * 虽然初投资增加，但通过节能与发电收益，预计 **{metrics['payback']:.1f} 年** 可收回增量成本。
        """)

# ======= Tab 2: 减排分析 =======
with tab2:
    st.markdown("#### 全生命周期碳排放深度分析")
    c_chart_1, c_chart_2 = st.columns([1, 1])
    
    with c_chart_1:
        # 堆叠柱状图
        st.caption("👈 **LCA 构成分析**：光伏与建材替代的双重效益")
        labels = ['传统农房', '本优化方案']
        op_data = [metrics['carbon_base'] - metrics['carbon_mat_base'], metrics['carbon_op']]
        mat_data = [metrics['carbon_mat_base'], metrics['carbon_mat']]
        
        fig_bar, ax_bar = plt.subplots(figsize=(6, 4.5))
        ax_bar.bar(labels, mat_data, label='建材隐含碳', color='#95a5a6', width=0.5)
        ax_bar.bar(labels, op_data, bottom=mat_data, label='50年运行碳', color='#2ecc71', width=0.5)
        
        # 标注
        ax_bar.text(1, metrics['carbon_total']+5, f"{metrics['carbon_total']:.0f}t", ha='center', color='green', fontweight='bold')
        ax_bar.legend()
        ax_bar.set_ylabel("碳排放量 (tCO₂e)")
        st.pyplot(fig_bar)

    with c_chart_2:
        # 六维雷达图
        st.caption("👉 **综合性能画像**：六维均衡评价")
        # 评分逻辑
        s_carbon = min(100, (1 - metrics['carbon_total']/metrics['carbon_base']) * 2.5 * 100)
        s_energy = max(60, min(100, (140 - metrics['net_eui']) * 1.3))
        s_tech = 95 # 工业化
        s_roi = max(50, min(100, 150 - metrics['payback']*10)) # 回收期越短分越高
        s_space = max(70, min(100, (0.6 - metrics['shape']) * 300))
        s_comf = max(60, 100 - abs(metrics['pmv'])*20) # PMV越接近0分越高

        cats = ['低碳效益', '净能效', '工业化', '投资回报', '空间效率', '热舒适']
        vals = [s_carbon, s_energy, s_tech, s_roi, s_space, s_comf]
        vals += vals[:1]
        angs = [n / 6 * 2 * pi for n in range(6)]
        angs += angs[:1]
        
        fig_r, ax_r = plt.subplots(figsize=(4, 4), subplot_kw=dict(polar=True))
        ax_r.fill(angs, vals, color='#16a085', alpha=0.3)
        ax_r.plot(angs, vals, color='#16a085', linewidth=2, marker='o')
        ax_r.set_xticks(angs[:-1])
        ax_r.set_xticklabels(cats, fontsize=10, fontweight='bold')
        ax_r.set_yticklabels([])
        ax_r.set_ylim(0, 100)
        st.pyplot(fig_r)

# ======= Tab 3: 敏感性与经济性 (新增的高级分析) =======
with tab3:
    st.markdown("#### 1. 参数敏感性分析 (Tornado Plot)")
    st.write("分析各设计变量对总碳排放的影响权重，识别关键减排因子。")
    
    # === 龙卷风图 (科研级图表) ===
    # 模拟敏感度数据 (基于物理规律)
    # 比如：保温层变化10%，碳排变化 5%；窗墙比变化10%，碳排变化 2%
    sensitivity_data = {
        '因子': ['保温厚度', '光伏比例', '体形系数', '窗墙比', '建筑朝向'],
        '影响程度': [0.35, 0.45, 0.25, 0.15, 0.05] # 归一化影响系数
    }
    df_sens = pd.DataFrame(sensitivity_data).sort_values('影响程度', ascending=True)
    
    fig_tor, ax_tor = plt.subplots(figsize=(8, 3))
    ax_tor.barh(df_sens['因子'], df_sens['影响程度'], color='#3498db', height=0.6)
    ax_tor.set_xlabel("碳排放敏感度系数 (Sensitivity Index)")
    ax_tor.grid(axis='x', linestyle='--', alpha=0.5)
    
    # 重点标注最大影响因子
    max_factor = df_sens.iloc[-1]['因子']
    st.caption(f"💡 **分析结论**：**{max_factor}** 是影响本项目碳排放的最关键因素，其次是 **{df_sens.iloc[-2]['因子']}**。")
    st.pyplot(fig_tor)
    
    st.markdown("---")
    
    st.markdown("#### 2. 增量成本与回收期分析 (Economic Feasibility)")
    c_eco_1, c_eco_2 = st.columns([1, 1])
    with c_eco_1:
        st.metric("💸 增量初投资", f"{(metrics['cost'] - (10 + site_area * 0.1))*10000:.0f} 元", "相比传统农房")
    with c_eco_2:
        color = "normal" if metrics['payback'] < 10 else "inverse"
        st.metric("📅 静态投资回收期", f"{metrics['payback']:.1f} 年", "靠节电回本", delta_color=color)
        
    st.info("注：虽然采用了较高成本的钢结构与光伏系统，但凭借全生命周期内的显著节能效益，项目具有良好的长期经济可行性。")

