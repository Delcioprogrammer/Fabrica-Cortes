import streamlit as st
import tempfile
import os
import time
import zipfile
from backend import VideoProcessor

# --- CONFIGURAÇÃO INICIAL ---
st.set_page_config(page_title="Editor Viral Pro", page_icon="✂️", layout="wide")

st.markdown("""
<style>
    .stTextArea textarea { font-size: 16px !important; font-weight: 500; }
    .stStatus { font-size: 18px !important; }
</style>
""", unsafe_allow_html=True)

# --- FUNÇÕES UTILITÁRIAS ---
def cleanup_temp_file(path):
    if path and os.path.exists(path):
        try: os.remove(path)
        except: pass

def create_zip_of_files(file_paths):
    if not os.path.exists("cortes_temp"): os.makedirs("cortes_temp")
    zip_path = os.path.join("cortes_temp", "Todos_Os_Cortes.zip")
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for file in file_paths:
            if os.path.exists(file): zipf.write(file, os.path.basename(file))
    return zip_path

# --- INICIALIZAÇÃO DE ESTADO ---
# Garante que as variáveis existam antes de qualquer coisa
if "api_key_session" not in st.session_state:
    st.session_state["api_key_session"] = ""

# --- CALLBACK DO BOTÃO (A MÁGICA) ---
def btn_otimizar_clicado():
    """Esta função roda nos bastidores quando clica no botão"""
    # 1. Pega o texto que está na caixa AGORA
    texto_usuario = st.session_state.get("widget_instrucao", "")
    chave_api = st.session_state.get("api_key_session", "")

    if texto_usuario and chave_api:
        try:
            # 2. Chama o Backend
            proc = VideoProcessor(chave_api)
            novo_texto = proc.optimize_prompt(texto_usuario)
            
            # 3. Atualiza a caixa de texto para a próxima renderização
            st.session_state["widget_instrucao"] = novo_texto
            
        except Exception as e:
            st.error(f"Erro na IA: {e}")
    else:
        st.toast("⚠️ Preencha a API Key e o Texto primeiro!")

# --- BARRA LATERAL ---
with st.sidebar:
    st.header("⚙️ Configurações")
    
    # Tenta pegar dos secrets ou usa o input
    default_key = st.secrets.get("GEMINI_KEY", "")
    api_key_input = st.text_input("🔑 Google Gemini API Key", value=default_key, type="password")
    
    # Salva na sessão para o callback usar
    st.session_state["api_key_session"] = api_key_input
    
    st.divider()
    with st.expander("🛠️ Avançado"):
        cookies_file = st.file_uploader("Arquivo cookies.txt", type=["txt"])
        speed = st.slider("Velocidade", 1.0, 2.0, 1.1, 0.1)

# --- INTERFACE PRINCIPAL ---
st.title("✂️ Fábrica de Cortes Virais")
st.caption("Baixe do YouTube ou suba arquivos. A IA faz o resto.")

if st.session_state["api_key_session"]:
    with st.container():
        st.success("🔓 Sistema Ativo")
        
        col_txt, col_btn = st.columns([4, 1])
        
        with col_txt:
            # A CAIXA DE TEXTO OFICIAL
            # O segredo é usar apenas 'key'. O Streamlit gerencia o valor sozinho.
            st.text_area(
                "🧠 Ordens para a IA:",
                placeholder="Ex: Corte as partes engraçadas... (Vazio = Telas Pretas)",
                height=130,
                key="widget_instrucao" # <--- Essa chave é controlada pelo callback
            )

        with col_btn:
            st.markdown("<br><br>", unsafe_allow_html=True)
            # O BOTÃO
            st.button(
                "✨ Melhorar\nInstrução", 
                type="secondary", 
                help="A IA reescreve seu pedido tecnicamente",
                on_click=btn_otimizar_clicado # Chama a função lá de cima
            )
else:
    st.warning("🔒 Digite sua API Key na barra lateral.")

# --- ABAS E PROCESSAMENTO ---
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
    yt_url = st.text_input("Link do Vídeo:")
    valid_url = len(yt_url) > 10
    has_key = bool(st.session_state["api_key_session"])
    
    if st.button("🚀 Processar YouTube", type="primary", disabled=not (has_key and valid_url)):
        processar = True
        origem = "youtube"

with tab_file:
    uploaded = st.file_uploader("Arquivo de Vídeo", type=["mp4", "mov", "mkv"])
    has_key = bool(st.session_state["api_key_session"])
    if st.button("🚀 Processar Arquivo", type="primary", disabled=not (has_key and uploaded)):
        processar = True
        origem = "arquivo"

# --- LÓGICA DE CORTE ---
if processar:
    # Pega o texto direto do widget
    instrucao_final = st.session_state.get("widget_instrucao", "")
    api_key_atual = st.session_state["api_key_session"]
    
    processor = VideoProcessor(api_key_atual)
    
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
                    status.update(label="❌ Erro Download", state="error")
                    st.stop()
            else:
                tfile = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
                tfile.write(uploaded.read())
                video_paths = [tfile.name]
            
            # 2. ANÁLISE
            status.write(f"✅ {len(video_paths)} vídeos.")
            todos_cortes = []
            
            for i, vid in enumerate(video_paths):
                status.write(f"🎞️ Analisando: {os.path.basename(vid)}")
                cortes = processor.analyze_video(vid, instrucao_final)
                
                if cortes:
                    status.write(f"✂️ {len(cortes)} cortes. Renderizando...")
                    files = processor.process_cuts(vid, cortes, speed_factor=speed)
                    todos_cortes.extend(files)
            
            # 3. RESULTADO
            if todos_cortes:
                status.update(label="🎉 Pronto!", state="complete", expanded=False)
                st.balloons()
                
                # Zip
                if len(todos_cortes) > 1:
                    zip_file = create_zip_of_files(todos_cortes)
                    with open(zip_file, "rb") as zf:
                        st.download_button("📦 Baixar Tudo (ZIP)", zf, "Cortes.zip", "application/zip", type="primary")
                    st.divider()
                
                # Videos
                cols = st.columns(2)
                for idx, f in enumerate(todos_cortes):
                    with cols[idx % 2]:
                        st.video(f)
                        with open(f, "rb") as v:
                            st.download_button(f"⬇️ {os.path.basename(f)}", v, os.path.basename(f))
            else:
                status.update(label="⚠️ Sem cortes", state="error")

    except Exception as e:
        st.error(f"Erro: {e}")
    finally:
        cleanup_temp_file(cookies_path)
        if origem == "arquivo" and video_paths:
            cleanup_temp_file(video_paths[0])
