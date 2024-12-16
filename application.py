from flask import Flask, render_template, request, jsonify, Response, make_response
from flask_cors import CORS
import azure.cognitiveservices.speech as speechsdk
from azure.cognitiveservices.speech import SpeechConfig
import logging
import json
import uuid
import os
import queue
from dotenv import load_dotenv
import tempfile
import time
from datetime import datetime
from cachetools import TTLCache, LRUCache
from collections import deque
import sys
import signal
from waitress import serve
from concurrent.futures import ThreadPoolExecutor
from werkzeug.serving import is_running_from_reloader
from functools import lru_cache
import aiohttp
import werkzeug.serving
from werkzeug.middleware.shared_data import SharedDataMiddleware
from werkzeug.serving import WSGIRequestHandler
from threading import Lock, Thread
import asyncio
import base64
from queue import Queue
import pyaudio

executor = ThreadPoolExecutor(max_workers=10)
# Configure logging for Azure App Service
def setup_logging():
    # Use Azure's default log path or fall back to a temp directory
    log_path = os.environ.get('HOME', '/tmp') + '/LogFiles'
    os.makedirs(log_path, exist_ok=True)
    
    current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(os.path.join(log_path, f'app_{current_time}.log'), mode='a')
        ]
    )
    
    # Create a logger instance
    logger = logging.getLogger(__name__)
    
    # Remove any existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Add handlers
    file_handler = logging.FileHandler(os.path.join(log_path, f'app_{current_time}.log'))
    console_handler = logging.StreamHandler(sys.stdout)
    
    # Set formatter
    formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(filename)s:%(lineno)d - %(message)s')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

# Initialize logger
logger = setup_logging()
load_dotenv()

log_directory = '/home/LogFiles'  
if not os.path.exists(log_directory):
    os.makedirs(log_directory)

current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
file_handler = logging.FileHandler(f'{log_directory}/app_{current_time}.log')
console_handler = logging.StreamHandler(sys.stdout)

log_format = logging.Formatter('%(asctime)s [%(levelname)s] %(filename)s:%(lineno)d - %(message)s')
file_handler.setFormatter(log_format)
console_handler.setFormatter(log_format)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.addHandler(file_handler)
logger.addHandler(console_handler)

app = Flask(__name__)
CORS(app, resources={
    r"/*": {
        "origins": "*",
        "allow_headers": ["Content-Type", "Authorization", "Accept-Encoding", "X-Requested-With", "Cache-Control"],
        "expose_headers": ["Content-Length", "X-Requested-With"],
        "methods": ["GET", "POST", "OPTIONS", "PUT", "DELETE"],
        "supports_credentials": True,
        "max_age": 120
    }
})

class CustomRequestHandler(WSGIRequestHandler):
    def handle_error(self):
        try:
            super().handle_error()
        except OSError as e:
            if e.winerror == 10038:  # Socket error
                logger.error("Socket error occurred, attempting to recover")
            else:
                raise

app.wsgi_app = SharedDataMiddleware(app.wsgi_app, {})
werkzeug.serving.WSGIRequestHandler = CustomRequestHandler

# Azure Speech Service configuration
speech_key = os.environ.get('AZURE_SPEECH_KEY')
service_region = os.environ.get('AZURE_SPEECH_REGION')

# Azure Translator configuration
TRANSLATOR_KEY = os.environ.get('AZURE_TRANSLATOR_KEY')
TRANSLATOR_ENDPOINT = os.environ.get('AZURE_TRANSLATOR_ENDPOINT')
TRANSLATOR_LOCATION = os.environ.get('AZURE_TRANSLATOR_LOCATION')

# Cache and state management
translation_cache = TTLCache(maxsize=200000, ttl=24*360000)
recent_translations = LRUCache(maxsize=10000)
translation_lock = Lock()

translation_rate_limit = {
    'requests': deque(maxlen=10000),
    'limit': 10000,
    'window': 60
}
last_translation_time = {}
DEBOUNCE_DELAY = 1.0

# Global variables
is_streaming = False
transcription_queue = Queue()
audio_queue = queue.Queue()
connected_clients = {}
cleanup_done = False

# Audio settings
CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000

# CORS headers
@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    response.headers.add('Access-Control-Allow-Credentials', 'true')
    return response

# Add Azure-specific logging configuration
if os.environ.get('WEBSITE_SITE_NAME'):
    log_directory = os.path.join(os.environ['HOME'], 'LogFiles')
    file_handler = logging.FileHandler(os.path.join(log_directory, f'app_{current_time}.log'))

# Utility functions
def check_client_connections():
    """Periodically check and log client connection status"""
    while True:
        try:
            current_clients = list(connected_clients.keys())
            logger.info(f"Active clients: {current_clients}")
            for client_id in current_clients:
                if client_id not in connected_clients:
                    logger.warning(f"Client {client_id} disconnected")
            time.sleep(30)
        except Exception as e:
            logger.error(f"Error checking client connections: {str(e)}")

# Start connection checker thread
Thread(target=check_client_connections, daemon=True).start()

@lru_cache(maxsize=1000)
def normalize_text(text):
    """Normalize text to reduce duplicate translations"""
    return ' '.join(text.lower().split())

def send_translation_to_client(client_id, translation, is_final):
    """Send translation to client through queue"""
    try:
        if client_id in connected_clients:
            logger.debug(f"Sending translation to client {client_id}: {translation}")
            translation_queue = connected_clients[client_id]['translation_queue']
            message = {
                'type': 'final' if is_final else 'partial',
                'translation': translation
            }
            translation_queue.put(message)
            logger.debug(f"Translation sent successfully to client {client_id}")
        else:
            logger.warning(f"Client {client_id} not found in connected_clients")
    except Exception as e:
        logger.error(f"Error sending translation to client {client_id}: {str(e)}")

async def translate_text(text, target_language):
    """Perform the actual translation"""
    logger.info(f"Starting translation request - Text: '{text}', Target language: {target_language}")
    
    language_map = {
        'es': 'es',
        'en': 'en',
        'pt': 'pt-BR'
    }
    
    target_lang = language_map.get(target_language)
    if not target_lang:
        logger.error(f"Invalid target language requested: {target_language}")
        raise ValueError(f"Invalid target language: {target_language}")

    endpoint = f'{TRANSLATOR_ENDPOINT}/translate'
    params = {
        'api-version': '3.0',
        'to': target_lang
    }
    headers = {
        'Ocp-Apim-Subscription-Key': TRANSLATOR_KEY,
        'Ocp-Apim-Subscription-Region': TRANSLATOR_LOCATION,
        'Content-type': 'application/json'
    }
    body = [{
        'text': text
    }]

    try:
        async with aiohttp.ClientSession() as session:
            logger.debug(f"Making API request to {endpoint}")
            async with session.post(endpoint, params=params, headers=headers, json=body) as response:
                response.raise_for_status()
                result = await response.json()
                translation = result[0]['translations'][0]['text']
                logger.info(f"Translation completed successfully")
                return translation
    except Exception as e:
        logger.error(f"Translation error: {str(e)}")
        raise

# Route Handlers
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/go_live')
def go_live():
    logger.info("Go live page requested")
    return render_template('go_live.html')

@app.route('/join_live')
def join_live():
    logger.info("Join live page requested")
    return render_template('join_live.html')

@app.route('/process_audio', methods=['POST'])
async def process_audio():
    """Handle audio processing from browser"""
    try:
        audio_data = request.get_json().get('audio')
        if not audio_data:
            return jsonify({'error': 'No audio data provided'}), 400

        # Decode base64 audio data
        audio_binary = base64.b64decode(audio_data.split(',')[1])
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as temp_audio:
            temp_audio.write(audio_binary)
            temp_filepath = temp_audio.name

        try:
            # Configure speech recognition
            speech_config = speechsdk.SpeechConfig(
                subscription=speech_key, 
                region=service_region
            )
            audio_config = speechsdk.audio.AudioConfig(filename=temp_filepath)
            speech_recognizer = speechsdk.SpeechRecognizer(
                speech_config=speech_config,
                audio_config=audio_config
            )

            # Create a future for async result
            done = asyncio.Future()

            def handle_result(evt):
                if evt.result.reason == speechsdk.ResultReason.RecognizedSpeech:
                    done.set_result(evt.result.text)
                elif evt.result.reason == speechsdk.ResultReason.NoMatch:
                    done.set_result("")

            speech_recognizer.recognized.connect(handle_result)
            speech_recognizer.start_continuous_recognition()
            
            try:
                text = await asyncio.wait_for(done, timeout=2.0)
            finally:
                speech_recognizer.stop_continuous_recognition()
                os.unlink(temp_filepath)

            transcription_queue.put({'text': text, 'is_final': True})
            return jsonify({'success': True, 'text': text})

        except Exception as e:
            logger.error(f"Speech recognition error: {str(e)}")
            return jsonify({'error': str(e)}), 500

    except Exception as e:
        logger.error(f"Error processing audio: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/translate_realtime', methods=['POST'])
async def translate_realtime():
    """Handle real-time translation requests"""
    logger.info("Real-time translation endpoint called")
    try:
        data = request.get_json()
        text = data.get('text', '').strip()
        target_language = data.get('targetLanguage', '')
        client_id = data.get('clientId')
        is_final = data.get('isFinal', False)

        if not all([text, target_language, client_id]):
            return jsonify({'error': 'Missing required parameters'}), 400

        normalized_text = normalize_text(text)
        cache_key = f"{normalized_text}:{target_language}"

        # Check caches first
        if cache_key in recent_translations:
            translation = recent_translations[cache_key]
        elif cache_key in translation_cache:
            translation = translation_cache[cache_key]
            recent_translations[cache_key] = translation
        else:
            # Perform new translation
            translation = await translate_text(normalized_text, target_language)
            with translation_lock:
                translation_cache[cache_key] = translation
                recent_translations[cache_key] = translation

        send_translation_to_client(client_id, translation, is_final)
        return jsonify({'success': True})

    except Exception as e:
        logger.error(f"Translation error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/start_stream', methods=['POST'])
def start_stream():
    global is_streaming
    if not is_streaming:
        is_streaming = True
        executor.submit(stream_audio)
    return jsonify({"status": "started"})


@app.route('/stop_stream', methods=['POST'])
def stop_stream():
    """Stop all streaming and processing"""
    global is_streaming
    try:
        logger.info("Stopping stream processing")
        is_streaming = False
        
        # Clear transcription queue
        while not transcription_queue.empty():
            try:
                transcription_queue.get_nowait()
            except queue.Empty:
                break
        
        # Clear audio queue
        while not audio_queue.empty():
            try:
                audio_queue.get_nowait()
            except queue.Empty:
                break
        
        # Notify all connected clients
        for client_id in list(connected_clients.keys()):
            try:
                if client_id in connected_clients:
                    connected_clients[client_id]['translation_queue'].put({
                        'type': 'final',
                        'translation': ''
                    })
            except Exception as e:
                logger.error(f"Error notifying client {client_id}: {str(e)}")
        
        logger.info("Stream stopped successfully")
        return jsonify({"status": "stopped"})
    except Exception as e:
        logger.error(f"Error stopping stream: {str(e)}")
        return jsonify({'error': str(e)}), 500

def stream_audio():
    """Handle continuous speech recognition and audio streaming"""
    global is_streaming
    speech_recognizer = None
    stream = None
    p = None
    
    try:
        logger.info("Initializing speech recognition")
        speech_config = speechsdk.SpeechConfig(subscription=speech_key, region=service_region)
        speech_config.speech_recognition_language = "en-US"
        audio_config = speechsdk.audio.AudioConfig(use_default_microphone=True)
        
        speech_recognizer = speechsdk.SpeechRecognizer(
            speech_config=speech_config, 
            audio_config=audio_config
        )

        def recognized_cb(evt):
            if is_streaming:  # Only process if still streaming
                try:
                    text = evt.result.text
                    logger.info(f"Speech recognized: {text}")
                    logger.debug(f"Recognition result details: {evt.result}")
                    transcription_queue.put({'text': text, 'is_final': True})
                except Exception as e:
                    logger.error(f"Error in recognition callback: {str(e)}")

        def recognizing_cb(evt):
            if is_streaming:  # Only process if still streaming
                try:
                    text = evt.result.text
                    logger.debug(f"Speech recognizing: {text}")
                    logger.debug(f"Recognition interim details: {evt.result}")
                    transcription_queue.put({'text': text, 'is_final': False})
                except Exception as e:
                    logger.error(f"Error in recognizing callback: {str(e)}")

        def canceled_cb(evt):
            logger.warning(f"Speech recognition canceled: {evt.result.cancellation_details}")
            
        speech_recognizer.recognized.connect(recognized_cb)
        speech_recognizer.recognizing.connect(recognizing_cb)
        speech_recognizer.canceled.connect(canceled_cb)

        logger.info("Starting continuous recognition")
        speech_recognizer.start_continuous_recognition()
        
        try:
            p = pyaudio.PyAudio()
            stream = p.open(
                format=FORMAT,
                channels=CHANNELS,
                rate=RATE,
                input=True,
                frames_per_buffer=CHUNK
            )
            
            logger.info("Audio stream started")
            while is_streaming:
                try:
                    data = stream.read(CHUNK, exception_on_overflow=False)
                    audio_queue.put(data)
                except Exception as e:
                    logger.error(f"Error reading audio stream: {str(e)}", exc_info=True)
                    break
                
        except Exception as e:
            logger.error(f"Error in audio stream setup: {str(e)}", exc_info=True)
        finally:
            if stream:
                stream.stop_stream()
                stream.close()
            if p:
                p.terminate()
            
    except Exception as e:
        logger.error(f"Critical error in stream_audio: {str(e)}", exc_info=True)
    finally:
        if speech_recognizer:
            try:
                speech_recognizer.stop_continuous_recognition()
                logger.info("Speech recognition stopped")
            except Exception as e:
                logger.error(f"Error stopping speech recognition: {str(e)}")
        
        # Clear the audio queue
        while not audio_queue.empty():
            try:
                audio_queue.get_nowait()
            except queue.Empty:
                break

@app.route('/stream_transcription')
def stream_transcription():
    """Stream transcription results"""
    def generate():
        while True:
            try:
                item = transcription_queue.get(timeout=1)
                if item:
                    yield f"data: {json.dumps(item)}\n\n"
            except Exception:
                yield f"data: {json.dumps({'keepalive': True})}\n\n"

    response = Response(generate(), mimetype='text/event-stream')
    response.headers['Cache-Control'] = 'no-cache'
    response.headers['X-Accel-Buffering'] = 'no'
    return response

@app.route('/stream_translation/<string:lang>')
def stream_translation(lang):
    """Stream translation results"""
    client_id = request.args.get('client_id')
    logger.info(f"New translation stream connection for client: {client_id}, language: {lang}")

    if lang not in ['en', 'es', 'pt']:
        return jsonify({'error': 'Invalid language code'}), 400

    def generate():
        if client_id not in connected_clients:
            connected_clients[client_id] = {
                'target_language': lang,
                'translation_queue': Queue(),
                'last_active': time.time()
            }

        translation_queue = connected_clients[client_id]['translation_queue']

        while True:
            try:
                message = translation_queue.get(timeout=1)
                connected_clients[client_id]['last_active'] = time.time()
                yield f"data: {json.dumps(message)}\n\n"
            except Exception:
                yield f"data: {json.dumps({'keepalive': True})}\n\n"

    response = Response(generate(), mimetype='text/event-stream')
    response.headers['Cache-Control'] = 'no-cache'
    response.headers['X-Accel-Buffering'] = 'no'
    return response

@app.route('/synthesize_speech', methods=['POST'])
def synthesize_speech():
    """Handle text-to-speech synthesis"""
    try:
        data = request.get_json()
        text = data.get('text')
        language = data.get('language')

        if not text:
            return jsonify({'error': 'No text provided'}), 400

        speech_config = SpeechConfig(
            subscription=speech_key,
            region=service_region
        )

        # Set voice based on language
        if language == 'pt':
            speech_config.speech_synthesis_voice_name = "pt-BR-AntonioNeural"
        elif language == 'es':
            speech_config.speech_synthesis_voice_name = "es-ES-AlvaroNeural"
        else:
            return jsonify({'error': 'Unsupported language'}), 400

        # Create temporary file for audio
        temp_filepath = os.path.join(tempfile.gettempdir(), f'speech_{uuid.uuid4()}.wav')
        audio_config = speechsdk.audio.AudioOutputConfig(filename=temp_filepath)
        
        synthesizer = speechsdk.SpeechSynthesizer(
            speech_config=speech_config,
            audio_config=audio_config
        )

        result = synthesizer.speak_text_async(text).get()

        if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
            with open(temp_filepath, 'rb') as audio_file:
                audio_data = audio_file.read()

            response = make_response(audio_data)
            response.headers['Content-Type'] = 'audio/wav'
            response.headers['Content-Disposition'] = 'attachment; filename=speech.wav'
            return response

        else:
            error_details = result.cancellation_details
            return jsonify({
                'error': 'Speech synthesis failed',
                'details': error_details.error_details
            }), 500

    except Exception as e:
        logger.error(f"Speech synthesis error: {str(e)}")
        return jsonify({'error': str(e)}), 500
    finally:
        try:
            if 'synthesizer' in locals() and synthesizer:
                synthesizer = None
            if os.path.exists(temp_filepath):
                os.unlink(temp_filepath)
        except Exception as e:
            logger.warning(f"Cleanup error: {str(e)}")

# Cleanup and resource management
def cleanup():
    """Clean up resources before shutdown"""
    global is_streaming, cleanup_done
    if not cleanup_done:
        logger.info("Cleaning up resources...")
        is_streaming = False
        
        # Close all event sources
        for client_id in list(connected_clients.keys()):
            try:
                if client_id in connected_clients:
                    logger.debug(f"Cleaning up client: {client_id}")
                    del connected_clients[client_id]
            except Exception as e:
                logger.error(f"Error cleaning up client {client_id}: {e}")

        # Shutdown executor
        try:
            logger.debug("Shutting down executor")
            executor.shutdown(wait=False)
        except Exception as e:
            logger.error(f"Error shutting down executor: {e}")

        # Clear queues
        try:
            logger.debug("Clearing queues")
            while not transcription_queue.empty():
                transcription_queue.get_nowait()
        except Exception as e:
            logger.error(f"Error clearing queues: {e}")

        cleanup_done = True
        logger.info("Cleanup completed")

def signal_handler(signum, frame):
    """Handle system signals"""
    logger.info(f"Received signal {signum}")
    cleanup()
    sys.exit(0)

# Register signal handlers
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# Error handlers
@app.errorhandler(404)
def not_found_error(error):
    return jsonify({'error': 'Not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500

# Health check endpoint
@app.route('/health')
def health_check():
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'active_clients': len(connected_clients)
    })

# Main application entry
if __name__ == '__main__':
    try:
        logger.info("Starting Flask application")
        port = int(os.environ.get('PORT', 8010))
        app.config['AZURE_WEBAPP'] = True
        
        if os.environ.get('WEBSITE_SITE_NAME'):  # Running on Azure
            app.run(
                host='0.0.0.0',
                port=port
            )
        else:
            serve(app, 
                host='0.0.0.0',
                port=5000,
                threads=8)
    except Exception as e:
        logger.error(f"Application startup error: {str(e)}", exc_info=True)
        cleanup()
