import os
import time
import json
import re
import glob
import logging
import uuid
import shutil
from datetime import datetime
import yt_dlp
import google.generativeai as genai
from moviepy.editor import VideoFileClip, vfx

# --- CONFIGURAÇÃO DE LOGGING (Essencial para Debug) ---
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class VideoProcessor:
    def __init__(self, api_key):
        self.api_key = api_key
        if api_key:
            try:
                genai.configure(api_key=self.api_key)
                logger.info("Gemini API configurada com sucesso.")
            except Exception as e:
                logger.error(f"Erro ao configurar API Key: {e}")
        self.model_name = 'models/gemini-1.5-flash'
        
        # Cria pastas necessárias na inicialização
        for folder in ["downloads_yt", "cortes_temp"]:
            os.makedirs(folder, exist_ok=True)

    def optimize_prompt(self, raw_text):
        """Melhora o prompt do usuário usando IA."""
        if not raw_text or len(raw_text) < 3:
            return raw_text

        try:
            prompt_refinador = f"""
            Você é um Engenheiro de Prompt Especialista.
            Reescreva a instrução abaixo para ser técnica e perfeita para visão computacional de vídeo.
            ORIGINAL: "{raw_text}"
            Retorne APENAS o texto melhorado, em Português.
            """
            model = genai.GenerativeModel(self.model_name)
            response = model.generate_content(prompt_refinador)
            return response.text.strip()
        except Exception as e:
            logger.warning(f"Falha ao otimizar prompt: {e}")
            return raw_text

    def _cleanup_old_files(self, folder, hours=1):
        """Limpa arquivos muito antigos para não lotar o servidor."""
        try:
            now = time.time()
            for f in glob.glob(f"{folder}/*"):
                if os.stat(f).st_mtime < now - (hours * 3600):
                    if os.path.isfile(f): os.remove(f)
                    elif os.path.isdir(f): shutil.rmtree(f)
        except Exception as e:
            logger.warning(f"Erro na limpeza automática: {e}")

    def download_from_youtube(self, url, cookies_path=None, progress_callback=None):
        """Baixa vídeos com tratamento robusto de erros e nomes únicos."""
        self._cleanup_old_files("downloads_yt") # Limpa lixo antigo
        
        if progress_callback: progress_callback("Conectando ao YouTube...")
        
        # Gera um ID único para esta sessão de download
        session_id = str(uuid.uuid4())[:8]
        
        ydl_opts = {
            'format': 'best[ext=mp4]/best',
            # Nome do arquivo inclui ID único para evitar colisão entre usuários
            'outtmpl': f'downloads_yt/{session_id}_%(title)s.%(ext)s',
            'quiet': True,
            'no_warnings': True,
            'ignoreerrors': True,
            'playlistend': 5,
            'http_headers': {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        }

        if cookies_path:
            ydl_opts['cookiefile'] = cookies_path

        downloaded_paths = []
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                
                entries = info['entries'] if 'entries' in info else [info]
                
                for entry in entries:
                    if entry:
                        filename = ydl.prepare_filename(entry)
                        # O yt-dlp às vezes muda a extensão, vamos verificar
                        if os.path.exists(filename):
                            downloaded_paths.append(filename)
                        else:
                            # Tenta encontrar o arquivo caso a extensão tenha mudado (ex: mkv -> mp4)
                            base_name = os.path.splitext(filename)[0]
                            found = glob.glob(f"{base_name}.*")
                            if found: downloaded_paths.append(found[0])

            valid_paths = [p for p in downloaded_paths if p and os.path.getsize(p) > 0]
            
            if progress_callback: 
                msg = f"✅ Download: {len(valid_paths)} vídeos." if valid_paths else "⚠️ Falha no download (Bloqueio ou erro)."
                progress_callback(msg)
            
            logger.info(f"Download concluído. Arquivos: {valid_paths}")
            return valid_paths

        except Exception as e:
            logger.error(f"Erro Crítico no Download: {e}")
            if progress_callback: progress_callback(f"❌ Erro: {str(e)}")
            return []

    def _clean_json_response(self, text):
        """Limpeza de JSON ultra-resiliente."""
        try:
            # 1. Tenta extrair bloco JSON markdown
            match = re.search(r'```json\s*(.*?)```', text, re.DOTALL)
            json_str = match.group(1) if match else text
            
            # 2. Tenta encontrar o array [...]
            match_list = re.search(r'\[.*\]', json_str, re.DOTALL)
            if match_list:
                json_str = match_list.group(0)
            
            # 3. Limpeza de caracteres inválidos comuns
            json_str = json_str.strip()
            # Remove vírgulas trailling (ex: [{"a":1},] -> [{"a":1}])
            json_str = re.sub(r',\s*\]', ']', json_str)
            
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.error(f"Erro de JSON Decode: {e}. Texto original: {text[:100]}...")
            return []
        except Exception as e:
            logger.error(f"Erro genérico no parser JSON: {e}")
            return []

    def analyze_video(self, video_path, user_orders="", status_callback=None):
        if status_callback: status_callback(f"Enviando vídeo para o Gemini...")
        
        try:
            logger.info(f"Iniciando upload: {video_path}")
            video_file = genai.upload_file(path=video_path)
            
            # Timeout de 2 minutos para processamento
            timeout_start = time.time()
            while video_file.state.name == "PROCESSING":
                if time.time() - timeout_start > 120:
                    raise TimeoutError("O Google demorou demais para processar o vídeo.")
                time.sleep(3)
                video_file = genai.get_file(video_file.name)

            if video_file.state.name == "FAILED":
                logger.error(f"Google marcou o vídeo como FAILED: {video_file.uri}")
                return []

            if status_callback: status_callback("IA analisando cortes (Filtros: OFF)...")

            prompt = f"""
            ATUE COMO EDITOR DE VÍDEO SÊNIOR.
            Tarefa: Analisar vídeo (Visual + Áudio) para criar cortes virais.
            
            INSTRUÇÃO DO USUÁRIO: "{user_orders}"
            
            FALLBACK (Se instrução vazia): Identifique cortes baseados em Title Cards (Telas pretas).
            
            Requisito de Saída: JSON VÁLIDO contendo lista de objetos.
            Formato: [{{"inicio": "MM:SS", "fim": "MM:SS", "titulo_arquivo": "Nome_do_Evento"}}]
            """
            
            # Configurações para garantir resposta
            generation_config = {
                "temperature": 0.2, # Mais preciso, menos criativo
                "top_p": 0.8,
                "top_k": 40,
            }

            safety = [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
            ]
            
            model = genai.GenerativeModel(self.model_name, generation_config=generation_config)
            
            # Tenta gerar conteúdo
            response = model.generate_content([video_file, prompt], safety_settings=safety)
            
            # Verifica se foi bloqueado mesmo com BLOCK_NONE
            if response.prompt_feedback and response.prompt_feedback.block_reason:
                logger.warning(f"Bloqueio de segurança detectado: {response.prompt_feedback}")
                return []
                
            return self._clean_json_response(response.text)

        except Exception as e:
            logger.error(f"Erro na Análise IA: {e}")
            if status_callback: status_callback("❌ Erro na análise da IA.")
            return []

    def _time_to_seconds(self, time_str):
        """Converte string de tempo para segundos com validação."""
        if not isinstance(time_str, str): return 0
        try:
            # Remove espaços e caracteres invisíveis
            time_str = time_str.strip()
            parts = list(map(float, time_str.split(':'))) # float para aceitar segundos quebrados
            if len(parts) == 1: return parts[0]
            if len(parts) == 2: return parts[0]*60 + parts[1]
            if len(parts) == 3: return parts[0]*3600 + parts[1]*60 + parts[2]
            return 0
        except Exception:
            return 0

    def process_cuts(self, video_path, cuts_data, speed_factor=1.1, progress_callback=None):
        clip = None
        generated_files = []
        try:
            clip = VideoFileClip(video_path)
            total_duration = clip.duration
            
            # Limpeza automática de cortes antigos
            self._cleanup_old_files("cortes_temp")

            total_cuts = len(cuts_data)
            
            for i, cut in enumerate(cuts_data):
                try:
                    start = self._time_to_seconds(cut.get('inicio', '0'))
                    end = self._time_to_seconds(cut.get('fim', '0'))
                    
                    # Validações de segurança
                    if start >= end: continue
                    if start < 0: start = 0
                    if end > total_duration: end = total_duration
                    if (end - start) < 1.0: continue # Ignora cortes menores que 1 seg

                    # Higienização do nome do arquivo
                    raw_title = cut.get('titulo_arquivo', 'corte')
                    safe_title = "".join([c for c in raw_title if c.isalnum() or c in (' ','_','-')]).strip()
                    safe_title = safe_title.replace(" ", "_")[:40]
                    
                    # Nome único para o arquivo de saída
                    filename = f"cortes_temp/Cut_{uuid.uuid4().hex[:6]}_{safe_title}.mp4"

                    # Processamento do corte
                    sub = clip.subclip(start, end)
                    if speed_factor != 1.0:
                        sub = sub.fx(vfx.speedx, speed_factor)
                    
                    sub.write_videofile(
                        filename, 
                        codec="libx264", 
                        audio_codec="aac", 
                        preset='ultrafast', # Prioriza velocidade
                        threads=4,          # Usa múltiplos núcleos
                        logger=None         # Silencia output do ffmpeg
                    )
                    generated_files.append(filename)
                    
                    if progress_callback: progress_callback((i+1)/total_cuts)
                    
                except Exception as e:
                    logger.error(f"Erro ao processar corte {i}: {e}")
                    continue

            return generated_files

        except Exception as e:
            logger.error(f"Erro crítico ao abrir vídeo para cortes: {e}")
            return []
            
        finally:
            # GARANTE que o arquivo de vídeo seja fechado para liberar memória
            if clip:
                try: clip.close()
                except: pass
