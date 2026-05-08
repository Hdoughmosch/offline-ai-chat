# Offline AI Chat Bot

A Python script that creates a local Chat connected to your offline Ollama AI, with favorites library and conversation controls.

---

## What This Code Does

| Component | What it does |
|-----------|--------------|
| **Creates a web server** | Runs a local website at `http://localhost:8080` |
| **Displays chat interface** | Shows a beautiful chat window in your browser |
| **Connects to Ollama** | Sends your questions to your local AI model |
| **Shows streaming responses** | Displays AI replies word-by-word as they generate |
| **Saves favorites** | Stores your favorite questions in SQLite database |
| **Manages favorites** | Lets you add, edit, delete, and categorize saved commands |
| **Controls conversations** | Pause, resume, stop, reset, and clear chat |
| **Supports RTL** | Switches between Arabic and English text direction |
| **Copies responses** | One-click copy of AI answers |

---




How to Change the AI Model

By default, chat.py uses a model named my_model. To use a different model, follow these steps:

Step 1: Find your installed models

Open Command Prompt and type:

```bash
ollama list
```

Copy the exact name of the model you want to use (e.g., llama3.2:3b).

Step 2: Open chat.py in Notepad

Right-click chat.py → Open with → Notepad

Step 3: Find and change this line

Look for this line in the file:

```python
'model': 'my_model',
```

Change my_model to your model name. For example:

```python
'model': 'llama3.2:3b',
```

Step 4: Save and restart

Press Ctrl + S to save, close Notepad, then restart the application:

```bash
python Chat.py
```

That's it! Your chat will now use the new AI model.


🔮 Coming Soon in Next Update

· Auto Model Detection - The app will automatically show you a list of all your installed models
· One-Click Model Switching - Change models directly from the web interface without editing files

⭐ Support this project by giving it a star on GitHub!

Your star helps others discover this project 


## 💬 Help Me Make This #1

I want to make this the best offline AI chat tool!

**Features I can add:**
- Dark mode
- Chat history save/export
- Document upload (PDF, Word, TXT)
- Voice input
- Auto model switcher
- Search chat history

**Tell me what YOU want!**

👉 [Open an Issue on GitHub](https://github.com/Hdoughmosch/offline-ai-chat/issues)

## 🤖 Agent Mode (Coming Soon)

I am working on a **massive update** that will turn `chat.py` into a real AI Agent that can do things on your computer - not just chat!

### What Will the AI Be Able to Do?

| Task | Example Command |
|------|-----------------|
| 🔍 **Search your files** | "Find all PDF invoices in my Downloads folder" |
| 🌐 **Check your network** | "Scan my local network for connected devices" |
| 📁 **Read and analyze files** | "Read my error.log and tell me what's wrong" |
| ✏️ **Create and save files** | "Write a Python script and save it to my desktop" |
| 🖧 **Check open ports** | "Check if port 443 is open on google.com" |
| ⚙️ **Run system commands** | "Show me all running processes" |
| 🛡️ **Security scanning** | "Check my server logs for suspicious activity" |




