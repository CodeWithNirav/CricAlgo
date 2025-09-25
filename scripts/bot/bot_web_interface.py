#!/usr/bin/env python3
"""
Simple web interface to test bot features
"""

import asyncio
import json
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import uvicorn
import sys
import os

# Add the app directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.bot.telegram_bot import get_bot, get_dispatcher
from app.core.config import settings

app = FastAPI(title="CricAlgo Bot Test Interface")
templates = Jinja2Templates(directory=".")

# Mock message class for testing
class MockMessage:
    def __init__(self, text, user_id=12345, chat_id=67890):
        self.text = text
        self.from_user = type('User', (), {'id': user_id, 'username': f'user_{user_id}'})()
        self.chat = type('Chat', (), {'id': chat_id})()
        self.last_answer = ""
        self.last_reply_markup = None
    
    async def answer(self, text, reply_markup=None, parse_mode=None):
        self.last_answer = text
        self.last_reply_markup = reply_markup
        return True

# Mock callback query class
class MockCallbackQuery:
    def __init__(self, data, user_id=12345, chat_id=67890):
        self.data = data
        self.from_user = type('User', (), {'id': user_id, 'username': f'user_{user_id}'})()
        self.message = MockMessage("", user_id, chat_id)
    
    async def answer(self, text=None):
        return True

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Home page with bot test interface"""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>CricAlgo Bot Test Interface</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }
            .container { max-width: 800px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
            h1 { color: #2c3e50; text-align: center; }
            .bot-info { background: #e8f5e8; padding: 15px; border-radius: 5px; margin: 20px 0; }
            .test-section { margin: 20px 0; padding: 20px; border: 1px solid #ddd; border-radius: 5px; }
            .command { background: #f8f9fa; padding: 10px; margin: 10px 0; border-left: 4px solid #007bff; }
            .result { background: #f8f9fa; padding: 15px; margin: 10px 0; border-radius: 5px; white-space: pre-wrap; }
            button { background: #007bff; color: white; padding: 10px 20px; border: none; border-radius: 5px; cursor: pointer; margin: 5px; }
            button:hover { background: #0056b3; }
            input, textarea { width: 100%; padding: 10px; margin: 5px 0; border: 1px solid #ddd; border-radius: 5px; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🤖 CricAlgo Bot Test Interface</h1>
            
            <div class="bot-info">
                <h3>📱 Bot Information</h3>
                <p><strong>Bot Username:</strong> @CricAlgoBot</p>
                <p><strong>Status:</strong> ✅ Running</p>
                <p><strong>Environment:</strong> Development</p>
            </div>
            
            <div class="test-section">
                <h3>🧪 Test Bot Commands</h3>
                <p>Test the bot commands without using Telegram directly:</p>
                
                <div class="command">
                    <h4>/start Command</h4>
                    <button onclick="testCommand('/start')">Test /start</button>
                    <button onclick="testCommand('/start INVITE123')">Test /start with invite code</button>
                </div>
                
                <div class="command">
                    <h4>Menu Commands</h4>
                    <button onclick="testCommand('/menu')">Test /menu</button>
                    <button onclick="testCommand('/balance')">Test /balance</button>
                </div>
                
                <div class="command">
                    <h4>Financial Commands</h4>
                    <button onclick="testCommand('/deposit')">Test /deposit</button>
                    <button onclick="testCommand('/withdraw')">Test /withdraw</button>
                </div>
                
                <div class="command">
                    <h4>Contest Commands</h4>
                    <button onclick="testCommand('/contests')">Test /contests</button>
                </div>
                
                <div class="command">
                    <h4>Custom Command</h4>
                    <input type="text" id="customCommand" placeholder="Enter custom command (e.g., /start TEST123)" value="/start">
                    <button onclick="testCustomCommand()">Test Custom Command</button>
                </div>
                
                <div id="result" class="result" style="display: none;"></div>
            </div>
            
            <div class="test-section">
                <h3>📋 Available Features</h3>
                <ul>
                    <li>✅ Invite code system with bonus crediting</li>
                    <li>✅ Per-user deposit addresses and notifications</li>
                    <li>✅ Withdrawal interface with amount selection</li>
                    <li>✅ Enhanced contest details and UX</li>
                    <li>✅ Contest settlement notifications</li>
                    <li>✅ Chat mapping and idempotency</li>
                    <li>✅ Comprehensive inline keyboards</li>
                </ul>
            </div>
            
            <div class="test-section">
                <h3>🔗 Real Telegram Testing</h3>
                <p>To test with real Telegram:</p>
                <ol>
                    <li>Open Telegram and search for <strong>@CricAlgoBot</strong></li>
                    <li>Send <code>/start</code> to begin</li>
                    <li>Try <code>/start INVITE123</code> for invite code testing</li>
                    <li>Use <code>/menu</code> to see all available options</li>
                </ol>
            </div>
        </div>
        
        <script>
            async function testCommand(command) {
                await testCustomCommand(command);
            }
            
            async function testCustomCommand(cmd = null) {
                const command = cmd || document.getElementById('customCommand').value;
                const resultDiv = document.getElementById('result');
                
                resultDiv.style.display = 'block';
                resultDiv.textContent = 'Testing command: ' + command + '\\n\\nLoading...';
                
                try {
                    const response = await fetch('/test-command', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                        body: 'command=' + encodeURIComponent(command)
                    });
                    
                    const data = await response.json();
                    resultDiv.textContent = 'Command: ' + command + '\\n\\nResult:\\n' + data.result;
                } catch (error) {
                    resultDiv.textContent = 'Error: ' + error.message;
                }
            }
        </script>
    </body>
    </html>
    """

@app.post("/test-command")
async def test_command(command: str = Form(...)):
    """Test a bot command"""
    try:
        # Import command handlers
        from app.bot.handlers.commands import start_command, menu_command, balance_command, deposit_command, withdraw_command, contests_command
        
        # Create mock message
        message = MockMessage(command)
        
        # Route to appropriate command
        if command.startswith('/start'):
            await start_command(message)
        elif command == '/menu':
            await menu_command(message)
        elif command == '/balance':
            await balance_command(message)
        elif command == '/deposit':
            from aiogram.fsm.context import FSMContext
            state = type('FSMContext', (), {})()  # Mock state
            await deposit_command(message, state)
        elif command == '/withdraw':
            from aiogram.fsm.context import FSMContext
            state = type('FSMContext', (), {})()  # Mock state
            await withdraw_command(message, state)
        elif command == '/contests':
            await contests_command(message)
        else:
            message.last_answer = f"Unknown command: {command}"
        
        return {"result": message.last_answer}
        
    except Exception as e:
        return {"result": f"Error: {str(e)}"}

if __name__ == "__main__":
    print("🌐 Starting CricAlgo Bot Web Test Interface...")
    print("📱 Bot: @CricAlgoBot")
    print("🔗 Web Interface: http://localhost:8001")
    print("🤖 Bot Process: Running in background")
    uvicorn.run(app, host="0.0.0.0", port=8001)
