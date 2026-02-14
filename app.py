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
    if not os.path.exists("cortes_temp"):
        os.makedirs("cortes_temp")
    zip_path = os.path.join("cortes_temp", "Todos_Os_Cortes.zip")
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for file in file_paths:
            if os.path.exists(file):
                zipf.write(file, os.path.basename(file))
    return zip_path

def cleanup_temp_file(path):
    if path and os.path.exists(path):
        try: os.remove(path)
        except: pass

# --- CALLBACK PARA OTIMIZAÇÃO (SEM ERRO DE WIDGET) ---
def otimizar_callback():
    texto_atual = st.session_state.get("text_area_input", "")
    # Pega a API Key do estado ou dos secrets
    chave_atual = st.session_state.get("api_key_final", "")
    
    if texto_atual and chave_atual:
        try:
            proc = VideoProcessor(chave_atual)
            novo_prompt = proc.optimize_prompt(texto_atual)
            st.session_state["text_area_input"] = novo_prompt
            st.session_state["user_prompt"] = novo_prompt
        except Exception as e:
            st.error(f"Erro na otimização: {e}")
    else:
        st.toast("⚠️ Falta API Key ou Texto.")

# --- ESTADO DA SESSÃO ---
if "user_prompt" not in st.session_state:
    st.session_state["user_prompt"] = ""

# --- CABEÇALHO ---
st.title("✂️ Fábrica de Cortes Virais")
st.caption("Transforme vídeos longos em Shorts/Reels. Suporte a YouTube (Playlists) e Arquivos Locais.")

# --- BARRA LATERAL INTELIGENTE (AUTO-SAVE) ---
with st.sidebar:
    st.header("⚙️ Configurações")
    
    # 1. TENTA LER DOS SEGREDOS (Configuração na Nuvem)
    # Procura por uma chave chamada "GEMINI_KEY" nos segredos do Streamlit
    secret_key = st.secrets.get("GEMINI_KEY", None)
    
    api_key = ""
    
    if secret_key:
        st.success("🔑 API Key carregada do Sistema!")
        api_key = secret_key
    else:
        # Se não tiver segredo, mostra o campo manual
        api_key = st.text_input("🔑 Google Gemini API Key", type="password")
        st.caption("Dica: Configure 'Secrets' no painel do Streamlit para salvar permanentemente.")
    
    # Salva no estado para o callback usar
    st.session_state["api_key_final"] = api_key
    
    st.divider()
    
    with st.expander("🛠️ Avançado (Cookies & Velocidade)"):
        st.info("Use cookies se o YouTube bloquear o download.")
        cookies_file = st.file_uploader("Arquivo cookies.txt", type=["txt"])
        st.divider()
        speed = st.slider("Velocidade (Viral Mode)", 1.0, 2.0, 1.1, 0.1)

# --- ÁREA DE INSTRUÇÕES ---
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
            st.button(
                "✨ Otimizar com IA", 
                type="secondary", 
                help="Reescreve seu pedido tecnicamente",
                on_click=otimizar_callback
            )

else:
    st.warning("🔒 Digite sua API Key na barra lateral para liberar o sistema.")

# --- SELEÇÃO DE FONTE ---
tab_yt, tab_file = st.tabs(["🔴 YouTube", "📂 Arquivo Local"])

video_paths = []
processar = False
cookies_path = None
origem = ""

if cookies_file:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".txt", mode='wb') as f:
        f.write(cookies_file.getvalue())
        cookies_path = f.name

with tab_yt:
    yt_url = st.text_input("Link do Vídeo ou Playlist:")
    valid_url = len(yt_url) > 10 and ("youtube.com" in yt_url or "youtu.be" in yt_url)
    if st.button("🚀 Processar YouTube", type="primary", disabled=not (api_key and valid_url)):
        processar = True
        origem = "youtube"

with tab_file:
    uploaded = st.file_uploader("Arquivo MP4/MOV/MKV", type=["mp4", "mov", "mkv"])
    if st.button("🚀 Processar Arquivo", type="primary", disabled=not (api_key and uploaded)):
        processar = True
        origem = "arquivo"

# --- LÓGICA PRINCIPAL ---
if processar and api_key:
    instrucao_final = st.session_state.get("text_area_input", "")
    processor = VideoProcessor(api_key)
    
    try:
        with st.status("🏭 Iniciando linha de produção...", expanded=True) as status:
            
            # 1. AQUISIÇÃO
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
                tfile = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
                tfile.write(uploaded.read())
                video_paths = [tfile.name]

            status.write(f"✅ {len(video_paths)} arquivos prontos para análise.")

            # 2. PROCESSAMENTO
            todos_cortes = []
            
            for i, vid_path in enumerate(video_paths):
                nome_vid = os.path.basename(vid_path)
                status.write(f"🎞️ [{i+1}/{len(video_paths)}] Analisando: **{nome_vid}**")
                
                cortes = processor.analyze_video(vid_path, instrucao_final)
                
                if cortes:
                    status.write(f"✂️ {len(cortes)} segmentos identificados. Renderizando cortes...")
                    arquivos = processor.process_cuts(vid_path, cortes, speed_factor=speed)
                    todos_cortes.extend(arquivos)
                else:
                    status.write("⚠️ Nenhum corte detectado pela IA neste vídeo.")

            # 3. ENTREGA
            if todos_cortes:
                status.update(label="🎉 Processamento Finalizado!", state="complete", expanded=False)
                st.balloons()
                st.divider()
                st.subheader("📦 Galeria de Cortes")

                if len(todos_cortes) > 1:
                    try:
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
                    except Exception as e:
                        st.warning(f"Não foi possível criar o ZIP: {e}")

                cols = st.columns(2)
                for idx, f in enumerate(todos_cortes):
                    if os.path.exists(f):
                        nome = os.path.basename(f)
                        with cols[idx % 2]:
                            st.video(f)
                            with open(f, "rb") as vid:
                                st.download_button(f"⬇️ Baixar {nome}", vid, file_name=nome, mime="video/mp4")
            else:
                status.update(label="❌ Nenhum corte gerado.", state="error")
                st.warning("A IA analisou o conteúdo mas não encontrou trechos compatíveis.")

    except Exception as e:
        st.error(f"💥 Ocorreu um erro inesperado no sistema: {e}")
    
    finally:
        cleanup_temp_file(cookies_path)
        if origem == "arquivo" and video_paths:
            cleanup_temp_file(video_paths[0])
