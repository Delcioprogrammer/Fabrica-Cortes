import streamlit as st
import tempfile
import os
import zipfile
from backend import VideoProcessor
from ui_helpers import processar_otimizacao, botao_otimizar_clicado # Importa nosso novo arquivo

# --- CONFIGURAÇÃO INICIAL ---
st.set_page_config(page_title="Editor Viral Pro", page_icon="✂️", layout="wide")

st.markdown("""
<style>
    .stTextArea textarea { font-size: 16px !important; font-weight: 500; }
    .stStatus { font-size: 18px !important; }
    .stDownloadButton button { width: 100%; }
</style>
""", unsafe_allow_html=True)

# --- INICIALIZAÇÃO DO ESTADO ---
if "user_prompt" not in st.session_state:
    st.session_state["user_prompt"] = ""
if "gemini_api_key" not in st.session_state:
    st.session_state["gemini_api_key"] = ""
if "clicou_otimizar" not in st.session_state:
    st.session_state["clicou_otimizar"] = False

# --- BARRA LATERAL (Carrega a chave PRIMEIRO) ---
with st.sidebar:
    st.header("⚙️ Configurações")
    default_key = st.secrets.get("GEMINI_KEY", "")
    api_key_input = st.text_input("🔑 Google Gemini API Key", value=default_key, type="password")
    
    # Salva a chave no estado
    st.session_state["gemini_api_key"] = api_key_input
    
    st.divider()
    with st.expander("🛠️ Avançado"):
        cookies_file = st.file_uploader("Arquivo cookies.txt", type=["txt"])
        speed = st.slider("Velocidade", 1.0, 2.0, 1.1, 0.1)

# --- MÁGICA 1: PROCESSA A OTIMIZAÇÃO ANTES DE DESENHAR A TELA ---
# Se o usuário clicou no botão na rodada anterior, isso aqui roda,
# atualiza o texto e dá refresh na página antes de desenhar a caixa antiga.
processar_otimizacao(st.session_state["gemini_api_key"])


# --- CABEÇALHO ---
st.title("✂️ Fábrica de Cortes Virais")
st.caption("Baixe do YouTube ou suba arquivos. A IA faz o resto.")

# --- ÁREA DE INSTRUÇÕES ---
if st.session_state["gemini_api_key"]:
    with st.container():
        st.success("🔓 Sistema Conectado")
        
        col_input, col_magic = st.columns([3, 1])
        
        with col_input:
            # AQUI ESTÁ O SEGREDO: O 'value' vem direto do estado atualizado
            user_input = st.text_area(
                "🧠 O que você quer cortar?",
                value=st.session_state["user_prompt"], # Lê do estado
                placeholder="Ex: Corte as partes engraçadas...",
                height=130
            )
            # Atualiza o estado se o usuário digitar manualmente
            st.session_state["user_prompt"] = user_input

        with col_magic:
            st.markdown("<br><br>", unsafe_allow_html=True)
            # O botão apenas ativa o gatilho "clicou_otimizar"
            st.button(
                "✨ Otimizar com IA", 
                type="secondary", 
                help="Melhora seu prompt automaticamente",
                on_click=botao_otimizar_clicado # Chama a função do ui_helpers
            )
else:
    st.warning("🔒 Digite sua API Key na barra lateral.")

# --- SELEÇÃO DE FONTE ---
tab_yt, tab_file = st.tabs(["🔴 YouTube", "📂 Arquivo Local"])

video_paths = []
processar = False
cookies_path = None
origem = ""

# Processa cookies
if cookies_file:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".txt", mode='wb') as f:
        f.write(cookies_file.getvalue())
        cookies_path = f.name

with tab_yt:
    yt_url = st.text_input("Link do Vídeo ou Playlist:")
    has_key = bool(st.session_state["gemini_api_key"])
    valid_url = len(yt_url) > 10
    
    if st.button("🚀 Processar YouTube", type="primary", disabled=not (has_key and valid_url)):
        processar = True
        origem = "youtube"

with tab_file:
    uploaded = st.file_uploader("Arquivo MP4/MOV/MKV", type=["mp4", "mov", "mkv"])
    has_key = bool(st.session_state["gemini_api_key"])
    
    if st.button("🚀 Processar Arquivo", type="primary", disabled=not (has_key and uploaded)):
        processar = True
        origem = "arquivo"

# --- LÓGICA DE CORTE ---
if processar:
    current_key = st.session_state["gemini_api_key"]
    instrucao_final = st.session_state["user_prompt"] # Pega a instrução final
    
    processor = VideoProcessor(current_key)
    
    try:
        with st.status("🏭 Trabalhando...", expanded=True) as status:
            # 1. DOWNLOAD
            if origem == "youtube":
                status.write("⬇️ Baixando...")
                video_paths = processor.download_from_youtube(
                    yt_url, 
                    cookies_path=cookies_path,
                    progress_callback=lambda x: status.write(f"📥 {x}")
                )
                if not video_paths:
                    status.update(label="❌ Erro no Download", state="error")
                    st.stop()
            else:
                tfile = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
                tfile.write(uploaded.read())
                video_paths = [tfile.name]
            
            # 2. ANÁLISE E CORTE
            todos_cortes = []
            for i, vid in enumerate(video_paths):
                status.write(f"🎞️ Analisando [{i+1}/{len(video_paths)}]: {os.path.basename(vid)}")
                cortes = processor.analyze_video(vid, instrucao_final)
                
                if cortes:
                    status.write(f"✂️ {len(cortes)} cortes encontrados.")
                    files = processor.process_cuts(vid, cortes, speed_factor=speed)
                    todos_cortes.extend(files)
            
            # 3. ENTREGA
            if todos_cortes:
                status.update(label="🎉 Pronto!", state="complete", expanded=False)
                st.balloons()
                
                # Zip
                if len(todos_cortes) > 1:
                    zip_path = os.path.join("cortes_temp", "Cortes_Virais.zip")
                    with zipfile.ZipFile(zip_path, 'w') as zf:
                        for f in todos_cortes: zf.write(f, os.path.basename(f))
                    
                    with open(zip_path, "rb") as z:
                        st.download_button("📦 Baixar Tudo (ZIP)", z, "cortes.zip", "application/zip", type="primary")
                
                # Individuais
                cols = st.columns(2)
                for idx, f in enumerate(todos_cortes):
                    with cols[idx % 2]:
                        st.video(f)
                        with open(f, "rb") as v:
                            st.download_button(f"⬇️ {os.path.basename(f)}", v, os.path.basename(f))
            else:
                status.update(label="⚠️ Nenhum corte gerado", state="error")
                
    except Exception as e:
        st.error(f"Erro: {e}")
