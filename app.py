import streamlit as st
import tempfile
import os
import time
from backend import VideoProcessor # Importa nosso cérebro

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    page_title="Editor Viral Pro",
    page_icon="✂️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS para deixar a interface mais bonita (Opcional)
st.markdown("""
<style>
    .stTextArea textarea {
        font-size: 16px !important;
        font-weight: 500;
    }
</style>
""", unsafe_allow_html=True)

# Título
st.title("✂️ Fábrica de Cortes Virais (Multimodal)")
st.caption("A IA agora VÊ e OUVE seu vídeo. Peça o que quiser.")

# --- BARRA LATERAL (CONFIGURAÇÕES TÉCNICAS) ---
with st.sidebar:
    st.header("⚙️ Configurações")
    
    # 1. API KEY
    api_key = st.text_input("🔑 Google Gemini API Key", type="password", help="Cole sua chave aqui")
    
    st.divider()
    
    # 2. AJUSTES DE VÍDEO
    st.subheader("🎬 Renderização")
    speed = st.slider("Velocidade do Corte", 1.0, 2.0, 1.1, 0.1, help="Acelera levemente para reter atenção (Padrão TikTok: 1.1x)")
    
    st.info("💡 Dica: Para cortes de gameplay ou podcast, a IA usa o áudio para detectar emoções.")

# --- ÁREA PRINCIPAL ---

uploaded_file = st.file_uploader("📂 Arraste seu arquivo (MP4, MKV, MOV)", type=["mp4", "mov", "mkv"])

if uploaded_file and api_key:
    # Salva temporariamente
    tfile = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
    tfile.write(uploaded_file.read())
    video_path = tfile.name

    # Colunas para organizar o layout (Vídeo à esquerda, Controles à direita)
    col1, col2 = st.columns([1, 1])

    with col1:
        st.subheader("📺 Preview")
        st.video(video_path)

    with col2:
        st.subheader("🧠 Cérebro da Edição")
        st.markdown("**O que devo procurar?**")
        
        # Sugestões rápidas
        col_chip1, col_chip2, col_chip3 = st.columns(3)
        prompt_sugestao = ""
        
        if col_chip1.button("🤣 Momentos Engraçados"):
            prompt_sugestao = "Identifique momentos de humor, risadas e piadas. Corte apenas as partes engraçadas."
        if col_chip2.button("🔥 Ação Intensa"):
            prompt_sugestao = "Identifique momentos de ação rápida, gritos ou tensão visual."
        if col_chip3.button("🤐 Silêncios"):
            prompt_sugestao = "Corte os momentos de silêncio constrangedor ou pausas longas."

        # A CAIXA DE ORDENS (Agora no Centro)
        user_instructions = st.text_area(
            "Digite sua ordem para a IA:",
            value=prompt_sugestao,
            placeholder="Ex: Corte todas as vezes que eu falo a palavra 'Dinheiro'...",
            height=150
        )
        
        st.caption("Se deixar vazio, a IA usará o padrão visual (Telas Pretas/Title Cards).")

        st.write("---")
        
        # Botão de Ação Gigante
        start_btn = st.button("🚀 PROCESSAR VÍDEO AGORA", type="primary", use_container_width=True)

    # --- LÓGICA DE PROCESSAMENTO ---
    if start_btn:
        processor = VideoProcessor(api_key)
        
        # 1. ANÁLISE
        cortes_detectados = []
        with st.status("🤖 A IA está analisando (Visão + Audição)...", expanded=True) as status:
            
            def update_status(msg):
                status.write(f"👀 {msg}")
            
            # Envia para o Backend
            cortes_detectados = processor.upload_and_analyze(
                video_path, 
                user_orders=user_instructions, 
                status_callback=update_status
            )
            
            if cortes_detectados:
                status.update(label="✅ Análise Concluída!", state="complete", expanded=False)
            else:
                status.update(label="❌ Falha na Análise", state="error")
                st.error("A IA não conseguiu processar o vídeo. Verifique se o vídeo tem áudio/imagem claros.")

        # 2. RESULTADOS
        if cortes_detectados:
            st.divider()
            st.success(f"🎬 {len(cortes_detectados)} clipes gerados com sucesso!")
            
            with st.expander("Ver detalhes dos cortes (JSON)"):
                st.json(cortes_detectados)
            
            # Barra de progresso da renderização
            progress_bar = st.progress(0, text="Renderizando cortes finais...")
            
            def update_render(p, m):
                progress_bar.progress(p, text=m)

            # Processamento físico (Corte)
            final_files = processor.process_cuts(
                video_path, 
                cortes_detectados, 
                speed_factor=speed, 
                progress_callback=update_render
            )
            
            progress_bar.empty()
            
            # Galeria de Downloads
            if final_files:
                st.balloons()
                st.markdown("### 📥 Seus Cortes:")
                
                cols_download = st.columns(2)
                for idx, file_path in enumerate(final_files):
                    file_name = os.path.basename(file_path)
                    with cols_download[idx % 2]:
                        st.video(file_path)
                        with open(file_path, "rb") as f:
                            st.download_button(
                                label=f"Baixar {file_name}",
                                data=f,
                                file_name=file_name,
                                mime="video/mp4",
                                use_container_width=True
                            )

elif not api_key:
    st.warning("👈 Por favor, insira sua API Key na barra lateral esquerda para ativar o sistema.")
