import streamlit as st
from backend import VideoProcessor

def processar_otimizacao(api_key):
    """
    Função isolada para gerenciar a otimização do prompt.
    Deve ser chamada ANTES de desenhar os widgets na tela.
    """
    # Verifica se o botão foi clicado na rodada anterior
    if st.session_state.get("clicou_otimizar", False):
        
        texto_atual = st.session_state.get("user_prompt", "")
        
        if texto_atual and api_key:
            try:
                with st.spinner("A IA está reescrevendo seu pedido..."):
                    proc = VideoProcessor(api_key)
                    novo_prompt = proc.optimize_prompt(texto_atual)
                    
                    # Atualiza o estado principal
                    st.session_state["user_prompt"] = novo_prompt
                    
                    # Desliga o gatilho para não rodar de novo
                    st.session_state["clicou_otimizar"] = False
                    
                    # Recarrega a página para mostrar o texto novo
                    st.rerun()
            except Exception as e:
                st.error(f"Erro na IA: {e}")
                st.session_state["clicou_otimizar"] = False
        else:
            st.warning("Escreva algo antes de otimizar.")
            st.session_state["clicou_otimizar"] = False

def botao_otimizar_clicado():
    """Callback simples apenas para marcar que o botão foi clicado."""
    st.session_state["clicou_otimizar"] = True
