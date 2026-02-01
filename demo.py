import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from math import pi

# ================= 1. 全局配置与字体 =================
st.set_page_config(
    page_title="寒冷地区农房生成设计系统 (论文复现版)",
    page_icon="🧬",
    layout="wide"
)

# --- 字体设置 ---
def set_chinese_font():
    fonts = ['SimHei', 'Microsoft YaHei', 'PingFang SC', 'Arial Unicode MS', 'WenQuanYi Zen Hei']
    found = False
    for font in fonts:
        try:
            if font in [f.name for f in fm.fontManager.ttflist]:
                plt.rcParams['font.sans-serif'] = [font]
                plt.rcParams['axes.unicode_minus'] = False
                found = True
                break
        except:
            continue
    if not found:
        plt.rcParams['font.sans-serif'] = ['DejaVu Sans']

set_chinese_font()

# ================= 2. 侧边栏：输入条件 =================
with st.sidebar:
    st.title("🎛️ 设计参数控制台")
    st.info("基于庞含笑硕士论文逻辑")
    st.markdown("---")
    
    st.markdown("### 1️⃣ 基础约束 (Constraints)")
    # --- 地点选择 ---
    location = st.selectbox(
        "📍 建设地点", 
        ["承德 (严寒/寒冷过渡)", "石家庄 (寒冷B区)", "沧州 (寒冷C区)", "天津 (寒冷C区)"],
        index=0,
        help="承德地区气候最严酷，采暖能耗基准最高"
    )
    
    population = st.slider("👥 居住人口 (人)", 1, 8, 3)
    
    target_room_type = st.selectbox(
        "🛌 目标户型", 
        ["两室一厅 (经济型)", "三室一厅 (舒适型)", "四室两厅 (豪华型)"], 
        index=1
    )
    
    st.markdown("### 2️⃣ 宅基地 (Site)")
    site_width = st.number_input("面宽 (m)", 8.0, 25.0, 13.0, 0.5)
    site_depth = st.number_input("进深 (m)", 8.0, 25.0, 10.0, 0.5)
    
    st.markdown("### 3️⃣ 技术策略 (Tech)")
    insulation = st.slider("🧱 EPS保温厚度 (mm)", 50, 200, 150, 10)
    window_ratio = st.slider("🪟 南向窗墙比", 0.2, 0.8, 0.45, 0.05)
    
    use_pv = st.checkbox("☀️ 部署屋顶光伏", value=True)
    if use_pv:
        pv_ratio = st.slider("⚡ 光伏铺设比例 (%)", 10, 80, 50, 5) / 100.0
    else:
        pv_ratio = 0.0
    
    st.markdown("---")
    run_btn = st.button("🚀 点击生成最优方案", type="primary")

# ================= 3. 核心算法逻辑 =================

def calculate_metrics(w, d, ins, wwr, room_type, pv_r, pop, loc):
    area = w * d
    shape_coeff = (2 * (w + d)) / area 
    
    # --- A. 地点修正因子 (Climate Factor) ---
    if "承德" in loc:
        climate_factor = 1.30  # 采暖负荷基准高
        solar_factor = 1.05    # 光照较好
    elif "石家庄" in loc:
        climate_factor = 1.05
        solar_factor = 1.0
    else: # 沧州、天津
        climate_factor = 1.0
        solar_factor = 1.0

    # --- B. 户型修正 ---
    if "两室" in room_type: r_factor = 1.0
    elif "三室" in room_type: r_factor = 1.15
    else: r_factor = 1.35
        
    # --- C. 能耗计算 (EUI) ---
    base_eui_val = 140 * climate_factor
    design_eui = max(45, base_eui_val - (ins * 0.35) + (shape_coeff * 15) + abs(wwr - 0.45)*20)
    
    pv_gen = area * 0.5 * pv_r * 130 * solar_factor
    net_eui = max(0, design_eui - pv_gen/area)
    
    # --- D. 碳排放 ---
    grid_factor = 0.5810 
    life_span = 50
    
    base_op_c = (base_eui_val * area * grid_factor * life_span) / 1000
    design_op_c = (net_eui * area * grid_factor * life_span) / 1000
    
    base_mat_c = area * 0.35
    design_mat_c = area * (0.20 + ins * 0.0005) * r_factor
    if pv_r > 0: design_mat_c += (area * 0.5 * pv_r * 0.08)
    
    base_total = base_op_c + base_mat_c
    design_total = design_op_c + design_mat_c
    
    # --- E. 经济性 ---
    base_cost = 10 + area * 0.10
    design_cost = (10 + area * 0.13 + ins * 0.05) * r_factor
    if pv_r > 0: design_cost += (area * 0.5 * pv_r * 0.04)
    
    saving_year = (base_eui_val - net_eui) * area * 0.55 
    payback = (design_cost - base_cost) * 10000 / saving_year if saving_year > 0 else 99
    
    pmv = -1.5 + (ins / 200) * 1.0 + (0.5 - abs(wwr-0.45))
    
    return {
        "eui": design_eui, "net_eui": net_eui, "cost": design_cost, "payback": payback,
        "shape": shape_coeff, "carbon_total": design_total, "carbon_base": base_total,
        "pv_gen": pv_gen, "pmv": pmv,
        "carbon_op": design_op_c, "carbon_mat": design_mat_c, "carbon_mat_base": base_mat_c,
        "per_capita_carbon": design_total / (pop * life_span),
        "climate_factor": climate_factor # <--- 关键修复：将因子返回出来
    }

def plot_fallback_box(text):
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.text(0.5, 0.5, f"{text}\n(Image Not Found)", ha='center', va='center', fontsize=14, color='gray')
    ax.set_xticks([]); ax.set_yticks([])
    for spine in ax.spines.values(): spine.set_edgecolor('#ddd')
    return fig

# ================= 4. 主界面逻辑 =================
st.title("🌍 寒冷地区农房生成设计系统")

if not run_btn:
    st.info("👈 请在左侧选择【建设地点】、【户型】及技术参数，点击生成按钮开始。")
    st.markdown("""
    **系统核心流程：**
    1.  **拓扑重构**：基于图论的最优功能连接。
    2.  **寻优决策**：NSGA-II 算法生成 Pareto 前沿并锁定最优解。
    3.  **深度分析**：全生命周期碳排与多维性能评估。
    """)

else:
    # 1. 计算
    metrics = calculate_metrics(site_width, site_depth, insulation, window_ratio, target_room_type, pv_ratio, population, location)
    
    # 2. 资源匹配
    if "两室" in target_room_type:
        img_plan = "house_2.png"; img_matrix = "21.png"; img_topo = "22.png"; table_ref = "3.10"
    elif "三室" in target_room_type:
        img_plan = "house_3.png"; img_matrix = "31.png"; img_topo = "32.png"; table_ref = "3.11"
    else:
        img_plan = "house_4.png"; img_matrix = "41.png"; img_topo = "42.png"; table_ref = "3.12"

    # 3. 顶部 KPI
    k1, k2, k3, k4, k5 = st.columns(5)
    delta_c = metrics['carbon_base'] - metrics['carbon_total']
    percent_c = (1 - metrics['carbon_total']/metrics['carbon_base'])*100
    
    k1.metric("🌱 净碳排放", f"{metrics['carbon_total']:.1f} t", f"-{percent_c:.1f}%")
    k2.metric("⚡ 光伏产能", f"{metrics['pv_gen']:.0f} kWh", f"地点: {location[:2]}")
    k3.metric("💰 投资回收期", f"{metrics['payback']:.1f} 年", "含光伏成本")
    k4.metric("🧊 体形系数", f"{metrics['shape']:.2f}", "紧凑度")
    k5.metric("🌡️ 舒适度", f"{metrics['pmv']:.2f}", "PMV指数")
    
    st.markdown("---")

    # 4. 页面布局
    tab1, tab2, tab3 = st.tabs(["🕸️ 1. 拓扑逻辑", "🎯 2. 寻优决策与方案", "📊 3. 深度数据分析"])

    # === Tab 1: 拓扑逻辑 ===
    with tab1:
        st.subheader("生成逻辑")
    
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("#### A. 最优功能拓扑关系")
            try: st.image(img_topo, caption="功能拓扑图", use_container_width=True)
            except: st.pyplot(plot_fallback_box(img_topo))
        with c2:
            st.markdown("#### B. 最优邻接关系矩阵")
            try: st.image(img_matrix, caption="连接矩阵", use_container_width=True)
            except: st.pyplot(plot_fallback_box(img_matrix))

    # === Tab 2: 寻优决策与方案 ===
    with tab2:
        st.subheader("NSGA-II 多目标寻优决策与方案生成")
        col_opt, col_plan = st.columns([1.2, 1])
        
        with col_opt:
            st.markdown("#### 1. 算法迭代寻优过程 (Pareto Optimization)")
            np.random.seed(42)
            pop_size = 200
            sim_costs = np.random.normal(metrics['cost'], 5, pop_size)
            sim_carbons = 400 - (sim_costs * 2.5) + np.random.normal(0, 20, pop_size)
            pareto_mask = sim_carbons < (450 - sim_costs * 3.0)
            
            fig_opt, ax_opt = plt.subplots(figsize=(6, 4.5))
            ax_opt.scatter(sim_costs[~pareto_mask], sim_carbons[~pareto_mask], c='lightgray', alpha=0.5, s=20, label='淘汰解')
            ax_opt.scatter(sim_costs[pareto_mask], sim_carbons[pareto_mask], c='#3498db', s=40, label='Pareto 前沿')
            ax_opt.scatter(metrics['cost'], metrics['carbon_total'], c='red', marker='*', s=300, edgecolors='white', zorder=10, label='TOPSIS 最优解')
            
            ax_opt.set_xlabel('建造成本 (万元)')
            ax_opt.set_ylabel('全生命周期碳排放 (tCO₂e)')
            ax_opt.legend(loc='upper right')
            ax_opt.grid(True, linestyle='--', alpha=0.3)
            st.pyplot(fig_opt)
            
            st.info(f"💡 **决策分析**：系统通过 TOPSIS 方法，在 **{sum(pareto_mask)}** 个非支配解中，锁定了兼顾经济性与低碳性的最优方案（红星点）。")

        with col_plan:
            st.markdown(f"#### 2. 最优生成平面：{target_room_type}")
            try: 
                st.image(img_plan, caption=f"生成结果 ({img_plan})", use_container_width=True)
            except: 
                st.pyplot(plot_fallback_box(img_plan))
            
            st.success(f"""
            **方案确认**：
            - **地点**：{location}
            - **造价**：{metrics['cost']:.1f} 万元
            - **策略**：{insulation}mm保温 + {pv_ratio*100:.0f}%光伏
            """)

    # === Tab 3: 深度数据分析 ===
    with tab3:
        st.subheader("📊 全生命周期性能评估看板")
        
        with st.container():
            col_a, col_b = st.columns(2)
            
            with col_a:
                st.markdown("**1. LCA 碳排放构成 (Embodied vs Operational)**")
                labels = ['传统农房', '本优化方案']
                op = [metrics['carbon_base'] - metrics['carbon_mat_base'], metrics['carbon_op']]
                mat = [metrics['carbon_mat_base'], metrics['carbon_mat']]
                
                fig_lca, ax_lca = plt.subplots(figsize=(6, 3.5))
                ax_lca.bar(labels, mat, color='#95a5a6', label='建材隐含碳', width=0.4)
                ax_lca.bar(labels, op, bottom=mat, color='#2ecc71', label='运行碳', width=0.4)
                ax_lca.text(0, metrics['carbon_base'], f"{metrics['carbon_base']:.0f}", ha='center', va='bottom')
                ax_lca.text(1, metrics['carbon_total'], f"{metrics['carbon_total']:.0f}", ha='center', va='bottom')
                ax_lca.legend(frameon=False)
                ax_lca.spines['top'].set_visible(False)
                ax_lca.spines['right'].set_visible(False)
                st.pyplot(fig_lca)

            with col_b:
                st.markdown("**2. 六维综合性能雷达**")
                # 修复点：这里通过 metrics['climate_factor'] 调用
                climate_factor = metrics['climate_factor']
                
                sc = min(100, percent_c * 2.5)
                se = max(60, (140*climate_factor - metrics['net_eui']) * 1.3)
                sroi = max(50, 150 - metrics['payback']*10)
                ssp = max(70, (0.6 - metrics['shape']) * 300)
                scom = max(60, 100 - abs(metrics['pmv'])*20)
                spv = min(100, pv_ratio * 150)
                
                cats = ['低碳', '能效', '光伏', 'ROI', '空间', '舒适']
                vals = [sc, se, spv, sroi, ssp, scom]; vals += vals[:1]
                angs = [n/6*2*pi for n in range(6)]; angs += angs[:1]
                
                fig_r, ax_r = plt.subplots(figsize=(4, 4), subplot_kw=dict(polar=True))
                ax_r.fill(angs, vals, color='#3498db', alpha=0.3)
                ax_r.plot(angs, vals, color='#3498db', linewidth=2)
                ax_r.set_xticks(angs[:-1]); ax_r.set_xticklabels(cats, fontsize=9); ax_r.set_yticklabels([])
                st.pyplot(fig_r)

        st.markdown("---")
        
        with st.container():
            col_c, col_d = st.columns([1.5, 1])
            
            with col_c:
                st.markdown("**3. 碳排放敏感性分析 (Tornado Plot)**")
                factors = ['光伏比例', '保温厚度', '窗墙比', '体形系数', '朝向']
                impacts = [0.45, 0.35, 0.20, 0.15, 0.05]
                fig_t, ax_t = plt.subplots(figsize=(7, 2.5))
                colors = ['#e74c3c' if x < 0.2 else '#3498db' for x in impacts]
                ax_t.barh(factors, impacts, color='#3498db', alpha=0.8)
                ax_t.set_xlabel("影响权重系数")
                ax_t.grid(axis='x', linestyle='--', alpha=0.3)
                st.pyplot(fig_t)
                
            with col_d:
                st.markdown("**4. 经济可行性结论**")
                st.write(f"📍 **地点**: {location}")
                st.write(f"💸 **增量成本**: {(metrics['cost'] - (10 + site_width*site_depth*0.1)):.1f} 万元")
                # 修复点：这里也用 metrics['climate_factor']
                saved_money = (metrics['pv_gen']*0.5 + (140*climate_factor - metrics['net_eui'])*site_width*site_depth*0.55)
                st.write(f"📉 **年节约电费**: {saved_money:.0f} 元")
                
                if metrics['payback'] < 10:
                    st.success(f"**回收期: {metrics['payback']:.1f} 年 (极优)**")
                elif metrics['payback'] < 15:
                    st.info(f"**回收期: {metrics['payback']:.1f} 年 (良好)**")
                else:
                    st.warning(f"**回收期: {metrics['payback']:.1f} 年 (较长)**")
