
import os
import sys
import json
import time
import threading
import requests
import readline
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv

# Load API key from environment
load_dotenv()
API_KEY = os.getenv("OPENROUTER_API_KEY")
SITE_URL = os.getenv("SITE_URL", "https://localhost")
SITE_NAME = os.getenv("SITE_NAME", "Terminal AI Agent")

if not API_KEY:
    print("Error: OPENROUTER_API_KEY not found in environment or .env file")
    print("Create a .env file with OPENROUTER_API_KEY=your_key_here")
    sys.exit(1)

# Set up readline for command history
HISTORY_FILE = os.path.expanduser("~/.ai_terminal_history")
try:
    readline.read_history_file(HISTORY_FILE)
    readline.set_history_length(1000)
except FileNotFoundError:
    open(HISTORY_FILE, 'w').close()

# Create a session for faster HTTP requests
http_session = requests.Session()

# Configure timeouts for faster response on network issues
TIMEOUT = (3.05, 30)  # (connect timeout, read timeout)

class SpinnerThread(threading.Thread):
    def __init__(self, message="Thinking"):
        super().__init__()
        self.message = message
        self.stop_event = threading.Event()
        self.daemon = True
        
    def run(self):
        spinner = ['⣾', '⣽', '⣻', '⢿', '⡿', '⣟', '⣯', '⣷']
        i = 0
        while not self.stop_event.is_set():
            sys.stdout.write(f"\r{self.message} {spinner[i]} ")
            sys.stdout.flush()
            i = (i + 1) % len(spinner)
            time.sleep(0.1)
        
        # Clear spinner line
        sys.stdout.write("\r" + " " * (len(self.message) + 10) + "\r")
        sys.stdout.flush()
    
    def stop(self):
        self.stop_event.set()

def get_ai_response(user_input, model="deepseek/deepseek-r1:free", conversation_history=None):
    """Get response from the AI using OpenRouter API"""
    if conversation_history is None:
        conversation_history = []
    
    # Add the new user message
    conversation_history.append({"role": "user", "content": user_input})
    
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": SITE_URL,
        "X-Title": SITE_NAME,
    }
    
    data = {
        "model": model,
        "messages": conversation_history,
        "stream": False  # Set to True for streaming responses if needed
    }
    
    try:
        response = http_session.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=data,
            timeout=TIMEOUT
        )
        
        if response.status_code != 200:
            return f"Error: API returned status code {response.status_code}\n{response.text}", conversation_history
        
        result = response.json()
        assistant_message = result["choices"][0]["message"]["content"]
        
        # Add the assistant's response to the conversation history
        conversation_history.append({"role": "assistant", "content": assistant_message})
        
        return assistant_message, conversation_history
    except requests.exceptions.Timeout:
        return "The request timed out. Please try again or use a different model.", conversation_history
    except requests.exceptions.ConnectionError:
        return "Connection error. Please check your internet connection.", conversation_history
    except Exception as e:
        return f"Error: {str(e)}", conversation_history

def execute_command(command):
    """Execute a shell command and return its output"""
    import subprocess
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        output = result.stdout
        if result.stderr:
            output += "\nErrors:\n" + result.stderr
        return output
    except Exception as e:
        return f"Error executing command: {str(e)}"

def main():
    print("╔══════════════════════════════════════════════════╗")
    print("║               Terminal AI Assistant              ║")
    print("║            (using OpenRouter & DeepSeek)          ║")
    print("╚══════════════════════════════════════════════════╝")
    print("\nCommands:")
    print("  !exit or !quit  - End the session")
    print("  !exec <command> - Execute a shell command")
    print("  !clear          - Clear conversation history")
    print("  !help           - Show this help message")
    print("  !models         - List available models")
    print("  !model <name>   - Change the AI model")
    
    # Initialize conversation history and executor
    conversation_history = []
    current_model = "deepseek/deepseek-r1:free"
    executor = ThreadPoolExecutor(max_workers=1)
    
    available_models = {
        "deepseek": "deepseek/deepseek-r1:free",
        "llama3": "meta-llama/llama-3-70b-instruct:free",
        "qwen": "qwen/qwen1.5-7b-chat:free",
        "mistral": "mistralai/mistral-7b-instruct:free",
        "claude": "anthropic/claude-3-haiku:free"
    }
    
    while True:
        try:
            user_input = input("\n> ")
            readline.write_history_file(HISTORY_FILE)
            
            # Handle special commands
            if user_input.lower() in ("!exit", "!quit"):
                break
                
            elif user_input.lower() == "!help":
                print("\nCommands:")
                print("  !exit or !quit  - End the session")
                print("  !exec <command> - Execute a shell command")
                print("  !clear          - Clear conversation history")
                print("  !help           - Show this help message")
                print("  !models         - List available models")
                print("  !model <name>   - Change the AI model")
                continue
                
            elif user_input.lower() == "!models":
                print("\nAvailable models:")
                for name, model_id in available_models.items():
                    print(f"  {name}: {model_id}")
                continue
                
            elif user_input.lower().startswith("!model "):
                model_name = user_input.lower().split(" ", 1)[1].strip()
                if model_name in available_models:
                    current_model = available_models[model_name]
                    print(f"Model changed to: {current_model}")
                else:
                    print(f"Unknown model: {model_name}")
                    print("Available models:")
                    for name, model_id in available_models.items():
                        print(f"  {name}: {model_id}")
                continue
                
            elif user_input.lower() == "!clear":
                conversation_history = []
                print("Conversation history cleared")
                continue
                
            elif user_input.lower().startswith("!exec "):
                command = user_input[6:]
                print(f"\nExecuting: {command}")
                # Run command execution in thread to keep UI responsive
                with ThreadPoolExecutor(max_workers=1) as cmd_executor:
                    future = cmd_executor.submit(execute_command, command)
                    spinner = SpinnerThread("Executing")
                    spinner.start()
                    output = future.result()
                    spinner.stop()
                print(f"\nOutput:\n{output}")
                continue
            
            # Get AI response in a separate thread with a spinner animation
            future = executor.submit(get_ai_response, user_input, current_model, conversation_history)
            spinner = SpinnerThread()
            spinner.start()
            
            # Wait for response
            response, conversation_history = future.result()
            spinner.stop()
            
            print(response)
            
        except KeyboardInterrupt:
            print("\nUse !exit or !quit to exit")
        except EOFError:
            break
    
    print("\nGoodbye!")
    executor.shutdown(wait=False)

if __name__ == "__main__":
    main()
