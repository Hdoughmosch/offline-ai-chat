# Offline AI Chat

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
## Features

Live streaming, favorites with SQLite, pause/resume/stop, RTL support.