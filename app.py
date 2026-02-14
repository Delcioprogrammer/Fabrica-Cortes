import streamlit as st
import tempfile
import os
import time
from backend import VideoProcessor

st.set_page_config(page_title="Editor Viral Pro", page_icon="✂️", layout="wide")

st.markdown("""
<style>
    .stTextArea textarea { font-size: 16px !important; font-weight: 500; }
    .stStatus { font-size: 18px !important; }
</style>
""", unsafe_allow_html=True)

st.title("✂️ Fábrica de Cortes Virais")
st.caption("Baixe do YouTube ou suba arquivos. A IA faz o resto.")

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Configurações")
    api_key = st.text_input("🔑 Google Gemini API Key", type="password")
    
    st.divider()
    speed = st.slider("Velocidade do Corte", 1.0, 2.0, 1.1, 0.1)
    st.info("Nota: Playlists são limitadas a 5 vídeos por vez.")

# --- LÓGICA DE CONDICIONAL (Só mostra instruções se tiver API Key) ---
user_instructions = ""

if api_key:
    # Cria container para as instruções aparecerem em destaque
    with st.container():
        st.success("🔓 Sistema Desbloqueado!")
        col_inst, col_dicas = st.columns([2, 1])
        
        with col_inst:
            user_instructions = st.text_area(
                "🧠 Ordens para a IA (Opcional):",
                placeholder="Ex: Corte apenas as partes engraçadas... Se deixar vazio, corto por Telas Pretas.",
                height=100
            )
        with col_dicas:
            st.markdown("**Dicas Rápidas:**")
            if st.button("🤣 Engraçados"): user_instructions = "Corte apenas momentos de risada e humor."
            if st.button("🔥 Ação"): user_instructions = "Corte momentos de ação intensa e gritos."
else:
    st.warning("🔒 Para desbloquear a caixa de instruções e iniciar, insira sua API Key na barra lateral.")

# --- ÁREA DE INPUT (Abas) ---
tab_yt, tab_file = st.tabs(["🔴 Link do YouTube", "📂 Arquivo Local"])

video_paths = []
processar = False

# ABA 1: YOUTUBE
with tab_yt:
    yt_url = st.text_input("Cole o link (Vídeo ou Playlist):", placeholder="https://youtube.com/...")
    if st.button("🚀 Processar YouTube", type="primary", disabled=not api_key):
        processar = True
        origem = "youtube"

# ABA 2: ARQUIVO
with tab_file:
    uploaded = st.file_uploader("Arraste o arquivo", type=["mp4", "mov", "mkv"])
    if st.button("🚀 Processar Arquivo", type="primary", disabled=not (api_key and uploaded)):
        processar = True
        origem = "arquivo"

# --- O GRANDE PROCESSAMENTO ---
if processar and api_key:
    processor = VideoProcessor(api_key)
    
    # CONTAINER DE PROGRESSO (Histórico do que está acontecendo)
    with st.status("🏭 Iniciando a Fábrica...", expanded=True) as status:
        
        # 1. DOWNLOAD (Se for YouTube)
        if origem == "youtube":
            status.write("⬇️ Baixando vídeos do YouTube...")
            video_paths = processor.download_from_youtube(yt_url, lambda x: status.write(f"📥 {x}"))
            if not video_paths:
                status.update(label="❌ Erro no Download", state="error")
                st.stop()
        else:
            # Salva arquivo local
            tfile = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
            tfile.write(uploaded.read())
            video_paths = [tfile.name]

        status.write(f"✅ Temos {len(video_paths)} vídeo(s) na fila.")

        # 2. LOOP DE PROCESSAMENTO (Para cada vídeo)
        todos_cortes = []
        
        for i, vid_path in enumerate(video_paths):
            nome_vid = os.path.basename(vid_path)
            status.write(f"🎞️ Processando [{i+1}/{len(video_paths)}]: {nome_vid}")
            
            # Análise IA
            status.write("🤖 IA Assistindo e Ouvindo...")
            cortes = processor.analyze_video(vid_path, user_instructions)
            
            if cortes:
                status.write(f"✂️ IA encontrou {len(cortes)} cortes. Renderizando...")
                # Edição Física
                arquivos_finais = processor.process_cuts(
                    vid_path, 
                    cortes, 
                    speed_factor=speed,
                    progress_callback=lambda p: None # Simplifiquei pra não poluir o status
                )
                todos_cortes.extend(arquivos_finais)
            else:
                status.write("⚠️ Nenhum corte encontrado neste vídeo.")

        # 3. FINALIZAÇÃO
        if todos_cortes:
            status.update(label="🎉 Processo Concluído!", state="complete", expanded=False)
            st.balloons()
            
            st.divider()
            st.subheader("📦 Seus Cortes Estão Prontos:")
            
            cols = st.columns(2)
            for idx, f in enumerate(todos_cortes):
                nome = os.path.basename(f)
                with cols[idx % 2]:
                    st.video(f)
                    with open(f, "rb") as vid:
                        st.download_button(f"⬇️ Baixar {nome}", vid, file_name=nome, mime="video/mp4")
        else:
            status.update(label="❌ Nenhum corte gerado no total.", state="error")
