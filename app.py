import streamlit as st
import tempfile
import os
from backend import VideoProcessor, TemplateProcessor

st.set_page_config(page_title="Editor Viral Pro", page_icon="✂️", layout="wide")
st.markdown("""
<style>
    .stButton button { width: 100%; }
    .stTabs [data-baseweb="tab-list"] { gap: 20px; }
    /* Estilo para destacar o botão de download */
    div[data-testid="stDownloadButton"] button {
        background-color: #00CC00 !important;
        color: white !important;
        font-weight: bold;
        border: 2px solid white;
    }
</style>
""", unsafe_allow_html=True)

st.title("🚀 Estúdio Viral Completo")

tab1, tab2 = st.tabs(["✂️ Cortes com IA", "🎨 Aplicar Template (Vídeo)"])

# --- ABA 1: CORTES ---
with tab1:
    with st.sidebar:
        st.header("⚙️ Configurações")
        api_key = st.text_input("🔑 Gemini API Key", type="password")
        speed = st.slider("Velocidade", 1.0, 2.0, 1.1)

    uploaded_file = st.file_uploader("📂 Vídeo Original", type=["mp4", "mov"], key="cut_up")
    if uploaded_file and api_key:
        tfile = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
        tfile.write(uploaded_file.read())
        
        col1, col2 = st.columns([1,1])
        with col1: st.video(tfile.name)
        with col2:
            instr = st.text_area("Ordens para a IA:", placeholder="Ex: Cortes engraçados")
            if st.button("🚀 PROCESSAR CORTES", type="primary"):
                proc = VideoProcessor(api_key)
                with st.status("🤖 IA trabalhando...") as status:
                    cortes = proc.upload_and_analyze(tfile.name, instr)
                    if cortes:
                        status.update(label="✅ Cortes encontrados!", state="complete")
                        st.success(f"{len(cortes)} clipes.")
                        finals = proc.process_cuts(tfile.name, cortes, speed)
                        st.balloons()
                        for f in finals:
                            with open(f, "rb") as file:
                                st.download_button(f"⬇️ Baixar {os.path.basename(f)}", file, file_name=os.path.basename(f))
                    else:
                        status.update(label="❌ Erro na análise", state="error")

# --- ABA 2: TEMPLATE ANIMADO ---
with tab2:
    st.markdown("### 🎨 Template de Vídeo (Overlay)")
    st.info("O Template agora pode ser um vídeo! Ele será repetido (loop) para cobrir o vídeo principal.")

    c1, c2 = st.columns(2)
    with c1: v_file = st.file_uploader("1. Vídeo do Corte", type=["mp4","mov"], key="t_vid")
    with c2: 
        # Aceita formatos de vídeo transparentes (MOV, WEBM) ou MP4
        t_file = st.file_uploader("2. Template Animado (MOV/WEBM/MP4)", type=["mov","webm","mp4"], key="t_tpl")

    if "y_pos" not in st.session_state: st.session_state.y_pos = 0

    if v_file and t_file:
        tv = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
        tv.write(v_file.read())
        
        # Detecta extensão do template para salvar corretamente
        ext = t_file.name.split('.')[-1]
        tt = tempfile.NamedTemporaryFile(delete=False, suffix=f".{ext}")
        tt.write(t_file.read())

        proc = TemplateProcessor()

        st.divider()
        cp, cc = st.columns([3, 1])
        
        with cc:
            st.write(f"Posição Y: **{st.session_state.y_pos}**")
            if st.button("⬆️ Subir"): st.session_state.y_pos -= 50
            if st.button("⬇️ Descer"): st.session_state.y_pos += 50
            if st.button("🔄 Centro"): st.session_state.y_pos = 0
            st.divider()
            render = st.button("✨ RENDERIZAR VÍDEO", type="primary")

        with cp:
            st.caption("👁️ Preview (Frame Estático)")
            # Gera preview usando um frame do vídeo principal E um frame do template
            prev = proc.get_preview_frame(tv.name, tt.name, st.session_state.y_pos)
            if prev: st.image(prev, use_column_width=True)
            else: st.error("Erro no preview. Verifique se o template é um arquivo de vídeo válido.")

        if render:
            bar = st.progress(0, "Iniciando renderização...")
            def up_bar(p, t): bar.progress(p, text=t)
            
            res = proc.render_video_with_template(tv.name, tt.name, st.session_state.y_pos, up_bar)
            bar.progress(100, "Concluído!")
            
            if res:
                st.balloons()
                st.success("✅ Vídeo Pronto! Clique no botão verde abaixo para salvar.")
                with open(res, "rb") as f:
                    # Botão Grande para Download
                    st.download_button(
                        label="📥 CLIQUE AQUI PARA BAIXAR O VÍDEO FINAL",
                        data=f,
                        file_name="video_viral_template.mp4",
                        mime="video/mp4",
                        use_container_width=True
                    )
