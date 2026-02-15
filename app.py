import streamlit as st
import tempfile
import os
from backend import VideoProcessor, TemplateProcessor

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Editor Viral Pro", page_icon="✂️", layout="wide")

# CSS PARA DEIXAR O BOTÃO DE DOWNLOAD GIGANTE E VERDE
st.markdown("""
<style>
    .stButton button { width: 100%; }
    
    /* Estilo específico para o botão de Download */
    div[data-testid="stDownloadButton"] button {
        background-color: #28a745 !important; /* Verde */
        color: white !important;
        font-size: 20px !important;
        padding: 15px !important;
        border: 2px solid #20c997 !important;
        border-radius: 10px !important;
    }
    div[data-testid="stDownloadButton"] button:hover {
        background-color: #218838 !important;
        border-color: white !important;
    }
</style>
""", unsafe_allow_html=True)

st.title("🚀 Estúdio Viral Completo")

# Navegação
tab1, tab2 = st.tabs(["✂️ Cortes com IA", "🎨 Aplicar Template (Overlay)"])

# ==============================================================================
# ABA 1: CORTES AUTOMÁTICOS (IA)
# ==============================================================================
with tab1:
    with st.sidebar:
        st.header("⚙️ Configurações")
        api_key = st.text_input("🔑 Gemini API Key", type="password")
        speed = st.slider("Velocidade", 1.0, 2.0, 1.1)

    uploaded_file = st.file_uploader("📂 Vídeo Original", type=["mp4", "mov", "mkv"], key="cut_up")
    
    if uploaded_file and api_key:
        tfile = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
        tfile.write(uploaded_file.read())
        
        col1, col2 = st.columns([1,1])
        with col1: st.video(tfile.name)
        with col2:
            instr = st.text_area("Ordens para a IA:", placeholder="Ex: Cortes engraçados, momentos de tensão...")
            
            if st.button("🚀 PROCESSAR CORTES", type="primary"):
                proc = VideoProcessor(api_key)
                with st.status("🤖 IA trabalhando...", expanded=True) as status:
                    cortes = proc.upload_and_analyze(tfile.name, instr)
                    
                    if cortes:
                        status.update(label="✅ Cortes encontrados!", state="complete", expanded=False)
                        st.success(f"Sucesso! {len(cortes)} clipes gerados.")
                        
                        finals = proc.process_cuts(tfile.name, cortes, speed)
                        
                        # Galeria de Downloads
                        st.balloons()
                        st.markdown("### 📥 Seus Cortes:")
                        cols = st.columns(2)
                        for i, f in enumerate(finals):
                            with cols[i % 2]:
                                with open(f, "rb") as file:
                                    st.download_button(
                                        label=f"⬇️ Baixar {os.path.basename(f)}", 
                                        data=file, 
                                        file_name=os.path.basename(f),
                                        mime="video/mp4"
                                    )
                    else:
                        status.update(label="❌ Erro na análise", state="error")
                        st.error("A IA não encontrou cortes. Tente mudar o prompt.")

# ==============================================================================
# ABA 2: TEMPLATES (OVERLAY DE VÍDEO)
# ==============================================================================
with tab2:
    st.markdown("### 🎨 Estúdio de Templates")
    st.info("O Template deve ser um arquivo com FUNDO TRANSPARENTE (.mov, .webm) ou MP4 (cobre tudo).")

    # Uploads
    c1, c2 = st.columns(2)
    with c1: 
        v_file = st.file_uploader("1. Vídeo Principal (Corte)", type=["mp4","mov"], key="t_vid")
    with c2: 
        t_file = st.file_uploader("2. Template/Overlay", type=["mov","webm","mp4"], key="t_tpl")

    # Inicializa Estados da Sessão (Memória)
    if "y_pos" not in st.session_state: st.session_state.y_pos = 0
    if "final_video_path" not in st.session_state: st.session_state.final_video_path = None

    if v_file and t_file:
        # Salva arquivos temporários
        tv = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
        tv.write(v_file.read())
        
        ext = t_file.name.split('.')[-1]
        tt = tempfile.NamedTemporaryFile(delete=False, suffix=f".{ext}")
        tt.write(t_file.read())

        proc = TemplateProcessor()

        st.divider()
        col_preview, col_controls = st.columns([3, 2])
        
        # --- CONTROLES ---
        with col_controls:
            st.subheader("🛠️ Ajustes")
            st.write(f"Posição Vertical: **{st.session_state.y_pos} px**")
            
            b1, b2, b3 = st.columns(3)
            if b1.button("⬆️ Subir"): 
                st.session_state.y_pos -= 50
            if b2.button("⬇️ Descer"): 
                st.session_state.y_pos += 50
            if b3.button("🔄 Reset"): 
                st.session_state.y_pos = 0
            
            st.markdown("---")
            
            # Botão de Renderizar
            if st.button("✨ RENDERIZAR VÍDEO FINAL", type="primary"):
                st.session_state.final_video_path = None # Limpa render anterior
                
                progress = st.progress(0, "Iniciando renderização...")
                def update_bar(p, t): progress.progress(p, text=t)
                
                # Chama o Backend
                result_path = proc.render_video_with_template(
                    tv.name, 
                    tt.name, 
                    st.session_state.y_pos, 
                    progress_callback=update_bar
                )
                
                progress.progress(100, "Concluído!")
                
                # Salva na memória para o botão não sumir
                if result_path and os.path.exists(result_path):
                    st.session_state.final_video_path = result_path
                    st.balloons()
                else:
                    st.error("Erro ao renderizar. Verifique os arquivos.")

            # --- ZONA DE DOWNLOAD (PERSISTENTE) ---
            # Se existir um vídeo na memória, mostra o botão gigante
            if st.session_state.final_video_path:
                st.success("✅ Vídeo Processado com Sucesso!")
                with open(st.session_state.final_video_path, "rb") as f:
                    st.download_button(
                        label="📥 BAIXAR VÍDEO AGORA (CLIQUE AQUI)",
                        data=f,
                        file_name="video_com_template.mp4",
                        mime="video/mp4",
                        use_container_width=True
                    )

        # --- PREVIEW ---
        with col_preview:
            st.caption("👁️ Preview (Quadro Estático)")
            # Mostra preview atualizado com a posição
            preview_img = proc.get_preview_frame(tv.name, tt.name, st.session_state.y_pos)
            
            if preview_img:
                st.image(preview_img, use_column_width=True, caption="Prévia da montagem")
            else:
                st.warning("Não foi possível gerar o preview. Verifique se o template é compatível.")

    elif not api_key:
        st.warning("👈 Insira sua API Key na aba lateral para começar.")
