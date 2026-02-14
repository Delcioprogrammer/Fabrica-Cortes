import streamlit as st
import tempfile
import os
import time
import zipfile
import shutil
from backend import VideoProcessor

# --- CONFIGURAÇÃO INICIAL ---
st.set_page_config(page_title="Editor Viral Pro", page_icon="✂️", layout="wide")

st.markdown("""
<style>
    .stTextArea textarea { font-size: 16px !important; font-weight: 500; }
    .stStatus { font-size: 18px !important; }
    .stDownloadButton button { width: 100%; }
</style>
""", unsafe_allow_html=True)

# --- FUNÇÕES UTILITÁRIAS ---
def create_zip_of_files(file_paths):
    """Cria um arquivo ZIP contendo todos os vídeos processados."""
    zip_path = os.path.join("cortes_temp", "Todos_Os_Cortes.zip")
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for file in file_paths:
            zipf.write(file, os.path.basename(file))
    return zip_path

def cleanup_temp_file(path):
    """Remove arquivo temporário com segurança."""
    if path and os.path.exists(path):
        try: os.remove(path)
        except: pass

# --- ESTADO DA SESSÃO ---
if "user_prompt" not in st.session_state:
    st.session_state["user_prompt"] = ""

# --- CABEÇALHO ---
st.title("✂️ Fábrica de Cortes Virais")
st.caption("Transforme vídeos longos em Shorts/Reels. Suporte a YouTube (Playlists) e Arquivos Locais.")

# --- BARRA LATERAL ---
with st.sidebar:
    st.header("⚙️ Configurações")
    api_key = st.text_input("🔑 Google Gemini API Key", type="password")
    
    st.divider()
    
    # Agrupa configurações avançadas para limpar o visual
    with st.expander("🛠️ Avançado (Cookies & Velocidade)"):
        st.info("Use cookies se o YouTube bloquear o download.")
        cookies_file = st.file_uploader("Arquivo cookies.txt", type=["txt"])
        st.divider()
        speed = st.slider("Velocidade (Viral Mode)", 1.0, 2.0, 1.1, 0.1)

# --- ÁREA DE INSTRUÇÕES (COM IA GENERATIVA) ---
if api_key:
    with st.container():
        st.success("🔓 Sistema Conectado")
        
        col_input, col_magic = st.columns([3, 1])
        
        with col_input:
            input_text = st.text_area(
                "🧠 O que você quer cortar?",
                value=st.session_state["user_prompt"],
                placeholder="Ex: Corte as partes engraçadas... (Deixe vazio para cortar por Telas Pretas)",
                height=130,
                key="text_area_input"
            )
            st.session_state["user_prompt"] = input_text

        with col_magic:
            st.markdown("<br><br>", unsafe_allow_html=True)
            if st.button("✨ Otimizar com IA", type="secondary", help="Reescreve seu pedido tecnicamente"):
                if st.session_state["user_prompt"]:
                    with st.spinner("Aprimorando prompt..."):
                        try:
                            proc = VideoProcessor(api_key)
                            novo_prompt = proc.optimize_prompt(st.session_state["user_prompt"])
                            st.session_state["user_prompt"] = novo_prompt
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro ao otimizar: {e}")
                else:
                    st.toast("⚠️ Escreva uma instrução básica primeiro.")
else:
    st.warning("🔒 Digite sua API Key na barra lateral para liberar o sistema.")

# --- SELEÇÃO DE FONTE ---
tab_yt, tab_file = st.tabs(["🔴 YouTube", "📂 Arquivo Local"])

video_paths = []
processar = False
cookies_path = None
origem = ""

# Processamento do arquivo de cookies
if cookies_file:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".txt", mode='wb') as f:
        f.write(cookies_file.getvalue())
        cookies_path = f.name

with tab_yt:
    yt_url = st.text_input("Link do Vídeo ou Playlist:")
    # Validação simples de URL antes de liberar o botão
    valid_url = len(yt_url) > 10 and ("youtube.com" in yt_url or "youtu.be" in yt_url)
    if st.button("🚀 Processar YouTube", type="primary", disabled=not (api_key and valid_url)):
        processar = True
        origem = "youtube"

with tab_file:
    uploaded = st.file_uploader("Arquivo MP4/MOV/MKV", type=["mp4", "mov", "mkv"])
    if st.button("🚀 Processar Arquivo", type="primary", disabled=not (api_key and uploaded)):
        processar = True
        origem = "arquivo"

# --- LÓGICA PRINCIPAL BLINDADA ---
if processar and api_key:
    instrucao_final = st.session_state["user_prompt"]
    processor = VideoProcessor(api_key)
    
    # Container para capturar erros sem quebrar a UI inteira
    try:
        with st.status("🏭 Iniciando linha de produção...", expanded=True) as status:
            
            # 1. AQUISIÇÃO DOS VÍDEOS
            if origem == "youtube":
                status.write("⬇️ Baixando do YouTube...")
                video_paths = processor.download_from_youtube(
                    yt_url, 
                    cookies_path=cookies_path, 
                    progress_callback=lambda x: status.write(f"📥 {x}")
                )
                if not video_paths:
                    status.update(label="❌ Erro no Download", state="error")
                    st.error("O YouTube recusou a conexão. Verifique o link ou use o arquivo cookies.txt.")
                    st.stop()
            else:
                # Processamento local seguro
                tfile = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
                tfile.write(uploaded.read())
                video_paths = [tfile.name]

            status.write(f"✅ {len(video_paths)} arquivos prontos para análise.")

            # 2. PROCESSAMENTO EM LOTE
            todos_cortes = []
            
            for i, vid_path in enumerate(video_paths):
                nome_vid = os.path.basename(vid_path)
                status.write(f"🎞️ [{i+1}/{len(video_paths)}] Analisando: **{nome_vid}**")
                
                # Análise
                cortes = processor.analyze_video(vid_path, instrucao_final)
                
                if cortes:
                    status.write(f"✂️ {len(cortes)} segmentos identificados. Renderizando cortes...")
                    arquivos = processor.process_cuts(vid_path, cortes, speed_factor=speed)
                    todos_cortes.extend(arquivos)
                else:
                    status.write("⚠️ Nenhum corte detectado pela IA neste vídeo.")

            # 3. ENTREGA DOS RESULTADOS
            if todos_cortes:
                status.update(label="🎉 Processamento Finalizado!", state="complete", expanded=False)
                st.balloons()
                st.divider()
                st.subheader("📦 Galeria de Cortes")

                # Botão de Download em Massa (ZIP)
                if len(todos_cortes) > 1:
                    zip_file = create_zip_of_files(todos_cortes)
                    with open(zip_file, "rb") as zf:
                        st.download_button(
                            label=f"📦 BAIXAR TUDO (ZIP) - {len(todos_cortes)} Vídeos",
                            data=zf,
                            file_name="Cortes_Virais.zip",
                            mime="application/zip",
                            type="primary"
                        )
                    st.divider()

                # Galeria Individual
                cols = st.columns(2)
                for idx, f in enumerate(todos_cortes):
                    nome = os.path.basename(f)
                    with cols[idx % 2]:
                        st.video(f)
                        with open(f, "rb") as vid:
                            st.download_button(f"⬇️ Baixar {nome}", vid, file_name=nome, mime="video/mp4")
            else:
                status.update(label="❌ Nenhum corte gerado.", state="error")
                st.warning("A IA analisou o conteúdo mas não encontrou trechos que correspondessem ao seu pedido.")

    except Exception as e:
        st.error(f"💥 Ocorreu um erro inesperado no sistema: {e}")
    
    finally:
        # Limpeza de arquivos temporários de upload (Segurança)
        cleanup_temp_file(cookies_path)
        if origem == "arquivo" and video_paths:
            cleanup_temp_file(video_paths[0])
