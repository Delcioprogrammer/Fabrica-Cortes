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
st.caption("Baixe do YouTube (Anti-Bloqueio) ou suba arquivos. A IA faz o resto.")

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Configurações")
    api_key = st.text_input("🔑 Google Gemini API Key", type="password")
    
    st.divider()
    
    # NOVO: Uploader de Cookies
    st.subheader("🍪 Acesso YouTube (Anti-Bloqueio)")
    cookies_file = st.file_uploader("Solte o arquivo cookies.txt aqui", type=["txt"], help="Essencial para vídeos com restrição de idade ou bloqueio de bot.")
    
    st.divider()
    speed = st.slider("Velocidade do Corte", 1.0, 2.0, 1.1, 0.1)

# --- LÓGICA DE CONDICIONAL ---
user_instructions = ""

if api_key:
    with st.container():
        st.success("🔓 Sistema Ativo")
        col_inst, col_dicas = st.columns([2, 1])
        
        with col_inst:
            user_instructions = st.text_area(
                "🧠 Ordens para a IA:",
                placeholder="Ex: Corte as partes engraçadas... (Vazio = Telas Pretas)",
                height=100
            )
        with col_dicas:
            st.markdown("**Dicas:**")
            if st.button("🤣 Humor"): user_instructions = "Corte momentos de risada e piadas."
            if st.button("💀 Crime/Suspense"): user_instructions = "Foque na narrativa de crime e momentos de tensão."
else:
    st.warning("🔒 Insira a API Key para começar.")

# --- ABAS ---
tab_yt, tab_file = st.tabs(["🔴 Link do YouTube", "📂 Arquivo Local"])

video_paths = []
processar = False
cookies_path = None

# Trata o arquivo de cookies se ele foi enviado
if cookies_file:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".txt", mode='wb') as f:
        f.write(cookies_file.getvalue())
        cookies_path = f.name

with tab_yt:
    yt_url = st.text_input("Cole o link (Vídeo/Playlist):")
    if st.button("🚀 Processar YouTube", type="primary", disabled=not api_key):
        processar = True
        origem = "youtube"

with tab_file:
    uploaded = st.file_uploader("Arquivo de Vídeo", type=["mp4", "mov", "mkv"])
    if st.button("🚀 Processar Arquivo", type="primary", disabled=not (api_key and uploaded)):
        processar = True
        origem = "arquivo"

# --- PROCESSAMENTO ---
if processar and api_key:
    processor = VideoProcessor(api_key)
    
    with st.status("🏭 Iniciando a Fábrica...", expanded=True) as status:
        
        # 1. DOWNLOAD
        if origem == "youtube":
            status.write("⬇️ Baixando vídeos do YouTube...")
            # Passa o caminho dos cookies para o backend
            video_paths = processor.download_from_youtube(
                yt_url, 
                cookies_path=cookies_path, 
                progress_callback=lambda x: status.write(f"📥 {x}")
            )
            if not video_paths:
                status.update(label="❌ Falha no Download (YouTube bloqueou)", state="error")
                st.error("Dica: Use o arquivo 'cookies.txt' na barra lateral para evitar bloqueios.")
                st.stop()
        else:
            tfile = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
            tfile.write(uploaded.read())
            video_paths = [tfile.name]

        status.write(f"✅ {len(video_paths)} vídeos na fila.")

        # 2. LOOP
        todos_cortes = []
        for i, vid_path in enumerate(video_paths):
            nome_vid = os.path.basename(vid_path)
            status.write(f"🎞️ [{i+1}/{len(video_paths)}] Analisando: {nome_vid}")
            
            cortes = processor.analyze_video(vid_path, user_instructions)
            
            if cortes:
                status.write(f"✂️ {len(cortes)} cortes encontrados. Editando...")
                arquivos = processor.process_cuts(vid_path, cortes, speed_factor=speed)
                todos_cortes.extend(arquivos)
            else:
                status.write("⚠️ Nenhum corte detectado (IA não encontrou o padrão ou bloqueou).")

        # 3. FIM
        if todos_cortes:
            status.update(label="🎉 Sucesso!", state="complete", expanded=False)
            st.balloons()
            st.divider()
            
            cols = st.columns(2)
            for idx, f in enumerate(todos_cortes):
                nome = os.path.basename(f)
                with cols[idx % 2]:
                    st.video(f)
                    with open(f, "rb") as vid:
                        st.download_button(f"⬇️ Baixar {nome}", vid, file_name=nome, mime="video/mp4")
        else:
            status.update(label="❌ Nenhum vídeo gerado.", state="error")
