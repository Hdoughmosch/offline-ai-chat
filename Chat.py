#!/usr/bin/env python
# -*- coding: utf-8 -*-

import http.server
import socketserver
import json
import sqlite3
import subprocess
import time
import sys
import os
import urllib.parse
import threading
import requests

# Database setup
DB_PATH = "ai_favorites.db"

def init_database():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS favorites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            command TEXT NOT NULL,
            category TEXT NOT NULL,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            usage_count INTEGER DEFAULT 0
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS categories (
            name TEXT PRIMARY KEY
        )
    ''')
    default_categories = ['General', 'Code', 'Translate', 'Question', 'Custom']
    for cat in default_categories:
        cursor.execute('INSERT OR IGNORE INTO categories (name) VALUES (?)', (cat,))
    conn.commit()
    conn.close()

init_database()

# Global state for pause/resume
server_paused = False
server_should_stop = False

# HTML Template
HTML_TEMPLATE = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI Chat | Offline</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 20px;
        }
        .chat-container {
            width: 100%;
            max-width: 1000px;
            height: 90vh;
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }
        .chat-header {
            background: #2c3e50;
            color: white;
            padding: 12px 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 10px;
        }
        .status {
            display: inline-block;
            width: 10px;
            height: 10px;
            border-radius: 50%;
            animation: pulse 2s infinite;
        }
        @keyframes pulse {
            0% { opacity: 1; }
            50% { opacity: 0.5; }
            100% { opacity: 1; }
        }
        .header-left {
            display: flex;
            align-items: center;
            gap: 10px;
            flex-wrap: wrap;
        }
        .fav-btn {
            background: #f39c12;
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 20px;
            cursor: pointer;
            font-size: 0.9rem;
            font-weight: bold;
        }
        .fav-btn:hover { background: #e67e22; }
        .rtl-btn {
            background: #3498db;
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 20px;
            cursor: pointer;
            font-size: 0.9rem;
            font-weight: bold;
        }
        .rtl-btn:hover { background: #2980b9; }
        .pause-badge {
            background: #f39c12;
            padding: 4px 10px;
            border-radius: 20px;
            font-size: 0.75rem;
            font-weight: bold;
        }
        .header-buttons { display: flex; gap: 8px; flex-wrap: wrap; }
        .btn {
            border: none;
            padding: 6px 14px;
            border-radius: 15px;
            cursor: pointer;
            font-size: 0.8rem;
            font-weight: bold;
        }
        .btn-pause { background: #f39c12; color: white; }
        .btn-resume { background: #2ecc71; color: white; }
        .btn-stop { background: #e74c3c; color: white; }
        .btn-reset { background: #1abc9c; color: white; }
        .btn-clear { background: #e74c3c; color: white; }
        .btn:disabled { opacity: 0.4; cursor: not-allowed; }
        .chat-messages {
            flex: 1;
            overflow-y: auto;
            padding: 20px;
            background: #f8f9fa;
        }
        .message { margin-bottom: 15px; display: flex; flex-direction: column; }
        .user-message { align-items: flex-end; }
        .ai-message { align-items: flex-start; }
        .message-wrapper {
            display: flex;
            align-items: flex-start;
            gap: 8px;
            max-width: 85%;
        }
        .message-content {
            padding: 12px 16px;
            border-radius: 18px;
            word-wrap: break-word;
            white-space: pre-wrap;
        }
        .user-message .message-content {
            background: #667eea;
            color: white;
            border-bottom-right-radius: 4px;
        }
        .ai-message .message-content {
            background: white;
            color: #333;
            border: 1px solid #ddd;
            border-bottom-left-radius: 4px;
        }
        .copy-btn {
            background: none;
            border: none;
            cursor: pointer;
            font-size: 16px;
            padding: 5px 8px;
            border-radius: 8px;
            opacity: 0.5;
        }
        .copy-btn:hover { opacity: 1; background: #e0e0e0; }
        .chat-input-area {
            padding: 20px;
            background: white;
            border-top: 1px solid #ddd;
            display: flex;
            gap: 10px;
        }
        .chat-input {
            flex: 1;
            padding: 12px;
            border: 2px solid #ddd;
            border-radius: 25px;
            font-size: 1rem;
            outline: none;
        }
        .chat-input:focus { border-color: #667eea; }
        .send-button {
            padding: 12px 24px;
            background: #667eea;
            color: white;
            border: none;
            border-radius: 25px;
            cursor: pointer;
        }
        .send-button:hover { background: #5a67d8; }
        .typing-indicator {
            display: flex;
            gap: 5px;
            padding: 12px 16px;
            background: white;
            border-radius: 18px;
            width: fit-content;
        }
        .typing-indicator span {
            width: 8px;
            height: 8px;
            background: #999;
            border-radius: 50%;
            animation: bounce 1.4s infinite;
        }
        @keyframes bounce {
            0%, 60%, 100% { transform: translateY(0); }
            30% { transform: translateY(-10px); }
        }
        .rtl { direction: rtl; text-align: right; }
        .ltr { direction: ltr; text-align: left; }
        .modal {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.5);
            z-index: 1000;
            justify-content: center;
            align-items: center;
        }
        .modal-content {
            background: white;
            padding: 25px;
            border-radius: 20px;
            width: 500px;
            max-width: 90%;
            max-height: 80vh;
            overflow-y: auto;
        }
        .modal-content h3 { margin-bottom: 15px; color: #2c3e50; }
        .modal-content input, .modal-content select, .modal-content textarea {
            width: 100%;
            padding: 10px;
            margin-bottom: 12px;
            border: 1px solid #ddd;
            border-radius: 10px;
            font-size: 14px;
        }
        .modal-content textarea { resize: vertical; min-height: 60px; }
        .modal-buttons {
            display: flex;
            gap: 10px;
            justify-content: flex-end;
            margin-top: 10px;
        }
        .modal-buttons button {
            padding: 8px 20px;
            border: none;
            border-radius: 10px;
            cursor: pointer;
        }
        .modal-save { background: #667eea; color: white; }
        .modal-cancel { background: #bdc3c7; color: white; }
        .fav-list {
            max-height: 300px;
            overflow-y: auto;
            margin: 15px 0;
        }
        .fav-item {
            background: #f8f9fa;
            padding: 10px;
            margin-bottom: 8px;
            border-radius: 10px;
            cursor: pointer;
            border-left: 3px solid #667eea;
            position: relative;
        }
        .fav-item:hover { background: #e9ecef; }
        .fav-command {
            font-size: 0.85rem;
            font-weight: bold;
            word-break: break-all;
            padding-right: 60px;
        }
        .fav-category { font-size: 0.65rem; color: #667eea; margin-top: 4px; }
        .fav-actions {
            position: absolute;
            top: 8px;
            right: 8px;
            display: flex;
            gap: 5px;
        }
        .fav-actions button {
            background: none;
            border: none;
            cursor: pointer;
            font-size: 12px;
            padding: 2px 6px;
            border-radius: 5px;
        }
        .fav-actions button:hover { background: #ddd; }
        .filter-bar {
            display: flex;
            gap: 5px;
            flex-wrap: wrap;
            margin-bottom: 15px;
        }
        .filter-btn {
            padding: 4px 10px;
            border: none;
            border-radius: 15px;
            cursor: pointer;
            font-size: 0.7rem;
            background: #ecf0f1;
        }
        .filter-btn.active { background: #667eea; color: white; }
        .add-btn {
            width: 100%;
            padding: 10px;
            background: #667eea;
            color: white;
            border: none;
            border-radius: 10px;
            cursor: pointer;
            margin-bottom: 15px;
            font-weight: bold;
        }
        .toast {
            position: fixed;
            bottom: 20px;
            left: 50%;
            transform: translateX(-50%);
            background: #2c3e50;
            color: white;
            padding: 8px 16px;
            border-radius: 20px;
            font-size: 14px;
            z-index: 1001;
            opacity: 0;
            transition: opacity 0.3s;
        }
        .toast.show { opacity: 1; }
    </style>
</head>
<body>
    <div class="chat-container">
        <div class="chat-header">
            <div class="header-left">
                <span class="status" id="ollamaStatus"></span>
                <span>AI Assistant</span>
                <button class="fav-btn" id="openFavBtn">⭐ Favorites</button>
                <button class="rtl-btn" id="rtlToggleBtn">🌐 RTL</button>
                <span id="pauseBadge" class="pause-badge" style="display: none;">⏸ PAUSED</span>
            </div>
            <div class="header-buttons">
                <button class="btn btn-pause" id="pauseBtn">⏸ Pause</button>
                <button class="btn btn-resume" id="resumeBtn" style="display: none;">▶️ Resume</button>
                <button class="btn btn-stop" id="stopBtn" disabled>⏹️ Stop</button>
                <button class="btn btn-reset" id="resetBtn">🔄 Reset</button>
                <button class="btn btn-clear" id="clearBtn">🗑️ Clear</button>
            </div>
        </div>
        <div class="chat-messages" id="chatMessages">
            <div class="message ai-message">
                <div class="message-wrapper">
                    <div class="message-content" id="welcomeMsg">Hello! Click ⭐ Favorites to save commands!</div>
                    <button class="copy-btn" onclick="copyToClipboard(this, 'Hello! Click ⭐ Favorites to save commands!')">📋</button>
                </div>
            </div>
        </div>
        <div class="chat-input-area">
            <input type="text" id="messageInput" class="chat-input" placeholder="Type your question here...">
            <button id="sendButton" class="send-button">Send</button>
        </div>
    </div>

    <!-- Favorites Modal -->
    <div id="favModal" class="modal">
        <div class="modal-content">
            <h3>⭐ My Favorites</h3>
            <div class="filter-bar" id="filterBar"></div>
            <button class="add-btn" id="openAddModalBtn">+ Add New Favorite</button>
            <div id="favList" class="fav-list">Loading...</div>
            <div class="modal-buttons">
                <button id="closeFavBtn" class="modal-cancel">Close</button>
            </div>
        </div>
    </div>

    <!-- Add/Edit Modal -->
    <div id="editModal" class="modal">
        <div class="modal-content">
            <h3 id="editTitle">Add Favorite</h3>
            <input type="text" id="editCommand" placeholder="Command (e.g., Write Python function)">
            <textarea id="editDesc" placeholder="Description (optional)"></textarea>
            <select id="editCat">
                <option value="General">General</option>
                <option value="Code">Code</option>
                <option value="Translate">Translate</option>
                <option value="Question">Question</option>
                <option value="Custom">Custom</option>
            </select>
            <div class="modal-buttons">
                <button id="editDeleteBtn" style="display: none;" class="modal-delete">Delete</button>
                <button id="editCancelBtn" class="modal-cancel">Cancel</button>
                <button id="editSaveBtn" class="modal-save">Save</button>
            </div>
        </div>
    </div>

    <div id="toast" class="toast"></div>

    <script>
        let isProcessing = false;
        let currentController = null;
        let isPaused = false;
        let pendingChunks = [];
        let fullResponse = '';
        let streamingDiv = null;
        let currentDirection = 'ltr';
        let currentFilter = 'All';
        let editingId = null;

        function showToast(msg) {
            const toast = document.getElementById('toast');
            toast.textContent = msg;
            toast.classList.add('show');
            setTimeout(() => toast.classList.remove('show'), 2000);
        }

        function copyToClipboard(btn, text) {
            navigator.clipboard.writeText(text).then(() => {
                btn.textContent = '✓';
                showToast('Copied!');
                setTimeout(() => btn.textContent = '📋', 1500);
            });
        }

        function toggleRTL() {
            const input = document.getElementById('messageInput');
            const welcome = document.getElementById('welcomeMsg');
            const allMsgs = document.querySelectorAll('.message-content');
            
            if (currentDirection === 'ltr') {
                currentDirection = 'rtl';
                input.style.direction = 'rtl';
                input.style.textAlign = 'right';
                if (welcome) welcome.classList.add('rtl');
                allMsgs.forEach(m => m.classList.add('rtl'));
                showToast('RTL mode - Arabic');
            } else {
                currentDirection = 'ltr';
                input.style.direction = 'ltr';
                input.style.textAlign = 'left';
                if (welcome) welcome.classList.remove('rtl');
                allMsgs.forEach(m => m.classList.remove('rtl'));
                showToast('LTR mode - English');
            }
        }

        async function loadFavorites() {
            const url = currentFilter === 'All' ? '/favorites' : `/favorites?category=${encodeURIComponent(currentFilter)}`;
            const res = await fetch(url);
            const favs = await res.json();
            const container = document.getElementById('favList');
            
            if (favs.length === 0) {
                container.innerHTML = '<div style="text-align:center;padding:20px;color:#999;">No favorites saved</div>';
                return;
            }
            
            container.innerHTML = '';
            for (const f of favs) {
                const div = document.createElement('div');
                div.className = 'fav-item';
                div.innerHTML = `
                    <div class="fav-command">${escapeHtml(f.command.substring(0, 80))}${f.command.length > 80 ? '...' : ''}</div>
                    <div class="fav-category">📁 ${escapeHtml(f.category)} | Used ${f.usage_count} times</div>
                    <div class="fav-actions">
                        <button onclick="event.stopPropagation();openEditModal(${f.id}, '${escapeHtml(f.command).replace(/'/g, "\\'")}', '${escapeHtml(f.description || '').replace(/'/g, "\\'")}', '${escapeHtml(f.category)}')">✏️</button>
                        <button onclick="event.stopPropagation();deleteFavorite(${f.id})">🗑️</button>
                    </div>
                `;
                div.onclick = () => { closeFavModal(); document.getElementById('messageInput').value = f.command; sendMessage(); };
                container.appendChild(div);
            }
        }

        async function loadFilters() {
            const res = await fetch('/categories');
            const cats = await res.json();
            const container = document.getElementById('filterBar');
            let html = `<button class="filter-btn active" onclick="setFilter('All', event)">All</button>`;
            for (const c of cats) {
                html += `<button class="filter-btn" onclick="setFilter('${c.name}', event)">${c.name}</button>`;
            }
            container.innerHTML = html;
        }

        function setFilter(cat, evt) {
            currentFilter = cat;
            document.querySelectorAll('.filter-btn').forEach(btn => btn.classList.remove('active'));
            if (evt && evt.target) evt.target.classList.add('active');
            loadFavorites();
        }

        function openFavModal() {
            loadFilters();
            loadFavorites();
            document.getElementById('favModal').style.display = 'flex';
        }

        function closeFavModal() {
            document.getElementById('favModal').style.display = 'none';
        }

        function openAddModal() {
            editingId = null;
            document.getElementById('editTitle').innerText = 'Add Favorite';
            document.getElementById('editCommand').value = '';
            document.getElementById('editDesc').value = '';
            document.getElementById('editCat').value = 'General';
            document.getElementById('editDeleteBtn').style.display = 'none';
            document.getElementById('editModal').style.display = 'flex';
        }

        function openEditModal(id, cmd, desc, cat) {
            editingId = id;
            document.getElementById('editTitle').innerText = 'Edit Favorite';
            document.getElementById('editCommand').value = cmd;
            document.getElementById('editDesc').value = desc;
            document.getElementById('editCat').value = cat;
            document.getElementById('editDeleteBtn').style.display = 'inline-block';
            document.getElementById('editModal').style.display = 'flex';
        }

        function closeEditModal() {
            document.getElementById('editModal').style.display = 'none';
            editingId = null;
        }

        async function saveFavorite() {
            const cmd = document.getElementById('editCommand').value.trim();
            const desc = document.getElementById('editDesc').value.trim();
            const cat = document.getElementById('editCat').value;
            if (!cmd) { showToast('Enter command'); return; }
            
            if (editingId) {
                await fetch(`/favorites/${editingId}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ command: cmd, description: desc, category: cat })
                });
                showToast('Updated!');
            } else {
                await fetch('/favorites', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ command: cmd, description: desc, category: cat })
                });
                showToast('Saved!');
            }
            closeEditModal();
            loadFavorites();
        }

        async function deleteFavorite(id) {
            if (confirm('Delete this favorite?')) {
                await fetch(`/favorites/${id}`, { method: 'DELETE' });
                showToast('Deleted');
                loadFavorites();
            }
        }

        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }

        async function checkStatus() {
            try {
                const res = await fetch('/status');
                const data = await res.json();
                document.getElementById('ollamaStatus').style.background = data.status === 'ok' ? '#2ecc71' : '#e74c3c';
            } catch {
                document.getElementById('ollamaStatus').style.background = '#e74c3c';
            }
        }

        function addMessage(content, isUser) {
            const container = document.getElementById('chatMessages');
            const msgDiv = document.createElement('div');
            msgDiv.className = `message ${isUser ? 'user-message' : 'ai-message'}`;
            const wrapper = document.createElement('div');
            wrapper.className = 'message-wrapper';
            const contentDiv = document.createElement('div');
            contentDiv.className = `message-content ${currentDirection}`;
            contentDiv.textContent = content;
            wrapper.appendChild(contentDiv);
            if (!isUser) {
                const copy = document.createElement('button');
                copy.className = 'copy-btn';
                copy.textContent = '📋';
                copy.onclick = () => copyToClipboard(copy, content);
                wrapper.appendChild(copy);
            }
            msgDiv.appendChild(wrapper);
            container.appendChild(msgDiv);
            container.scrollTop = container.scrollHeight;
            return contentDiv;
        }

        function showTyping() {
            const container = document.getElementById('chatMessages');
            const typing = document.createElement('div');
            typing.className = 'message ai-message';
            typing.id = 'typingIndicator';
            typing.innerHTML = '<div class="typing-indicator"><span></span><span></span><span></span></div>';
            container.appendChild(typing);
            container.scrollTop = container.scrollHeight;
        }

        function removeTyping() {
            const el = document.getElementById('typingIndicator');
            if (el) el.remove();
        }

        function clearChat() {
            if (isProcessing) stopGeneration();
            document.getElementById('chatMessages').innerHTML = '';
            const welcome = document.createElement('div');
            welcome.className = 'message ai-message';
            const wrapper = document.createElement('div');
            wrapper.className = 'message-wrapper';
            const content = document.createElement('div');
            content.className = `message-content ${currentDirection}`;
            content.id = 'welcomeMsg';
            content.textContent = 'Chat cleared! Ask me anything.';
            wrapper.appendChild(content);
            welcome.appendChild(wrapper);
            document.getElementById('chatMessages').appendChild(welcome);
        }

        async function resetAI() {
            if (isProcessing) stopGeneration();
            isPaused = false;
            pendingChunks = [];
            document.getElementById('pauseBtn').style.display = 'inline-block';
            document.getElementById('resumeBtn').style.display = 'none';
            document.getElementById('pauseBadge').style.display = 'none';
            await fetch('/reset', { method: 'POST' });
            showToast('Reset complete');
        }

        async function pauseGeneration() {
            if (!isProcessing) return;
            if (isPaused) return;
            isPaused = true;
            document.getElementById('pauseBtn').style.display = 'none';
            document.getElementById('resumeBtn').style.display = 'inline-block';
            document.getElementById('pauseBadge').style.display = 'inline-block';
            await fetch('/pause', { method: 'POST' });
        }

        async function resumeGeneration() {
            if (!isProcessing) return;
            if (!isPaused) return;
            isPaused = false;
            document.getElementById('pauseBtn').style.display = 'inline-block';
            document.getElementById('resumeBtn').style.display = 'none';
            document.getElementById('pauseBadge').style.display = 'none';
            await fetch('/resume', { method: 'POST' });
            if (pendingChunks.length > 0 && streamingDiv) {
                for (const ch of pendingChunks) {
                    fullResponse += ch;
                    streamingDiv.textContent = fullResponse;
                    document.getElementById('chatMessages').scrollTop = document.getElementById('chatMessages').scrollHeight;
                }
                pendingChunks = [];
            }
        }

        async function sendMessage() {
            if (isProcessing) { showToast('Please wait...'); return; }
            const input = document.getElementById('messageInput');
            const msg = input.value.trim();
            if (!msg) return;
            input.value = '';
            addMessage(msg, true);
            isProcessing = true;
            isPaused = false;
            pendingChunks = [];
            fullResponse = '';
            document.getElementById('pauseBtn').style.display = 'inline-block';
            document.getElementById('resumeBtn').style.display = 'none';
            document.getElementById('pauseBadge').style.display = 'none';
            document.getElementById('stopBtn').disabled = false;
            showTyping();
            currentController = new AbortController();

            try {
                const res = await fetch('/chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ prompt: msg }),
                    signal: currentController.signal
                });
                if (!res.ok) throw new Error('Error');
                removeTyping();

                const container = document.getElementById('chatMessages');
                const msgDiv = document.createElement('div');
                msgDiv.className = 'message ai-message';
                msgDiv.id = 'streamingMsg';
                const wrapper = document.createElement('div');
                wrapper.className = 'message-wrapper';
                const contentDiv = document.createElement('div');
                contentDiv.className = `message-content ${currentDirection}`;
                contentDiv.textContent = '';
                const copyBtn = document.createElement('button');
                copyBtn.className = 'copy-btn';
                copyBtn.textContent = '📋';
                copyBtn.disabled = true;
                copyBtn.style.opacity = '0.3';
                wrapper.appendChild(contentDiv);
                wrapper.appendChild(copyBtn);
                msgDiv.appendChild(wrapper);
                container.appendChild(msgDiv);
                container.scrollTop = container.scrollHeight;
                streamingDiv = contentDiv;

                const reader = res.body.getReader();
                const decoder = new TextDecoder();

                while (true) {
                    const { done, value } = await reader.read();
                    if (done) break;
                    const chunk = decoder.decode(value);
                    const lines = chunk.split('\\n');
                    for (const line of lines) {
                        if (line.trim() === '') continue;
                        try {
                            const data = JSON.parse(line);
                            if (data.response) {
                                if (isPaused) {
                                    pendingChunks.push(data.response);
                                } else {
                                    fullResponse += data.response;
                                    contentDiv.textContent = fullResponse;
                                    container.scrollTop = container.scrollHeight;
                                }
                            }
                        } catch(e) {}
                    }
                }
                contentDiv.textContent = fullResponse;
                copyBtn.disabled = false;
                copyBtn.style.opacity = '0.5';
                copyBtn.onclick = () => copyToClipboard(copyBtn, fullResponse);
                document.getElementById('streamingMsg')?.removeAttribute('id');
                streamingDiv = null;

            } catch(err) {
                removeTyping();
                if (err.name !== 'AbortError') {
                    addMessage('Error: ' + err.message, false);
                }
            } finally {
                isProcessing = false;
                isPaused = false;
                document.getElementById('stopBtn').disabled = true;
                currentController = null;
                streamingDiv = null;
            }
        }

        function stopGeneration() {
            if (currentController && isProcessing) {
                currentController.abort();
                removeTyping();
                isProcessing = false;
                isPaused = false;
                document.getElementById('stopBtn').disabled = true;
                currentController = null;
                streamingDiv = null;
                addMessage('Stopped by user.', false);
            }
        }

        document.getElementById('sendButton').onclick = sendMessage;
        document.getElementById('stopBtn').onclick = stopGeneration;
        document.getElementById('pauseBtn').onclick = pauseGeneration;
        document.getElementById('resumeBtn').onclick = resumeGeneration;
        document.getElementById('resetBtn').onclick = resetAI;
        document.getElementById('clearBtn').onclick = clearChat;
        document.getElementById('openFavBtn').onclick = openFavModal;
        document.getElementById('closeFavBtn').onclick = closeFavModal;
        document.getElementById('openAddModalBtn').onclick = openAddModal;
        document.getElementById('editSaveBtn').onclick = saveFavorite;
        document.getElementById('editCancelBtn').onclick = closeEditModal;
        document.getElementById('rtlToggleBtn').onclick = toggleRTL;
        document.getElementById('editDeleteBtn').onclick = () => {
            if (editingId && confirm('Delete?')) {
                fetch('/favorites/' + editingId, { method: 'DELETE' }).then(() => {
                    showToast('Deleted');
                    closeEditModal();
                    loadFavorites();
                });
            }
        };
        document.getElementById('messageInput').onkeypress = (e) => { if (e.key === 'Enter') sendMessage(); };
        window.onclick = (e) => {
            if (e.target === document.getElementById('favModal')) closeFavModal();
            if (e.target === document.getElementById('editModal')) closeEditModal();
        };

        checkStatus();
        setInterval(checkStatus, 5000);
    </script>
</body>
</html>'''

# Custom HTTP Request Handler
class AIRequestHandler(http.server.SimpleHTTPRequestHandler):
    
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        
        if path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(HTML_TEMPLATE.encode('utf-8'))
        elif path == '/status':
            self.send_json({'status': 'ok' if check_ollama() else 'error'})
        elif path == '/favorites':
            self.handle_get_favorites(parsed.query)
        elif path == '/categories':
            self.handle_get_categories()
        else:
            self.send_response(404)
            self.end_headers()
    
    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        
        if path == '/chat':
            self.handle_chat()
        elif path == '/favorites':
            self.handle_add_favorite()
        elif path == '/reset':
            global server_paused, server_should_stop
            server_paused = False
            server_should_stop = False
            self.send_json({'status': 'ok'})
        elif path == '/pause':
            
            server_paused = True
            self.send_json({'status': 'paused'})
        elif path == '/resume':
            
            server_paused = False
            self.send_json({'status': 'resumed'})
        else:
            self.send_response(404)
            self.end_headers()
    
    def do_PUT(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        
        if path.startswith('/favorites/'):
            id_str = path.split('/')[-1]
            self.handle_update_favorite(id_str)
        else:
            self.send_response(404)
            self.end_headers()
    
    def do_DELETE(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        
        if path.startswith('/favorites/'):
            id_str = path.split('/')[-1]
            self.handle_delete_favorite(id_str)
        else:
            self.send_response(404)
            self.end_headers()
    
    def send_json(self, data):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))
    
    def send_stream(self, generator):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.send_header('Cache-Control', 'no-cache')
        self.end_headers()
        for chunk in generator:
            self.wfile.write(chunk.encode('utf-8'))
            self.wfile.flush()
    
    def handle_get_favorites(self, query):
        category = None
        if query:
            params = urllib.parse.parse_qs(query)
            category = params.get('category', [None])[0]
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        if category and category != 'All':
            cursor.execute('SELECT id, command, category, description, usage_count FROM favorites WHERE category = ? ORDER BY usage_count DESC, created_at DESC', (category,))
        else:
            cursor.execute('SELECT id, command, category, description, usage_count FROM favorites ORDER BY usage_count DESC, created_at DESC')
        rows = cursor.fetchall()
        conn.close()
        
        result = [{'id': r[0], 'command': r[1], 'category': r[2], 'description': r[3], 'usage_count': r[4]} for r in rows]
        self.send_json(result)
    
    def handle_get_categories(self):
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('SELECT name FROM categories ORDER BY name')
        rows = cursor.fetchall()
        conn.close()
        self.send_json([{'name': r[0]} for r in rows])
    
    def handle_add_favorite(self):
        length = int(self.headers.get('Content-length', 0))
        data = json.loads(self.rfile.read(length))
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('INSERT INTO favorites (command, category, description) VALUES (?, ?, ?)',
                       (data['command'], data['category'], data.get('description', '')))
        conn.commit()
        conn.close()
        self.send_json({'status': 'ok'})
    
    def handle_update_favorite(self, id_str):
        length = int(self.headers.get('Content-length', 0))
        data = json.loads(self.rfile.read(length))
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('UPDATE favorites SET command = ?, category = ?, description = ? WHERE id = ?',
                       (data['command'], data['category'], data.get('description', ''), id_str))
        conn.commit()
        conn.close()
        self.send_json({'status': 'ok'})
    
    def handle_delete_favorite(self, id_str):
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('DELETE FROM favorites WHERE id = ?', (id_str,))
        conn.commit()
        conn.close()
        self.send_json({'status': 'ok'})
    
    def handle_chat(self):
        global server_paused, server_should_stop
        length = int(self.headers.get('Content-length', 0))
        data = json.loads(self.rfile.read(length))
        prompt = data.get('prompt', '')
        
        def generate():
            global server_paused, server_should_stop
            server_should_stop = False
            try:
                req = {
                    'model': 'my_model',
                    'prompt': prompt,
                    'stream': True,
                    'options': {'temperature': 0.2, 'num_predict': 500}
                }
                with requests.post('http://localhost:11434/api/generate', json=req, stream=True, timeout=120) as resp:
                    for line in resp.iter_lines():
                        if line:
                            while server_paused and not server_should_stop:
                                time.sleep(0.1)
                            if server_should_stop:
                                break
                            yield line.decode('utf-8') + '\n'
            except Exception as e:
                yield json.dumps({'response': f'Error: {e}'}) + '\n'
        
        self.send_stream(generate())

def check_ollama():
    try:
        r = requests.get('http://localhost:11434/api/tags', timeout=2)
        if r.status_code == 200:
            for m in r.json().get('models', []):
                if m.get('name', '').startswith('my_model'):
                    return True
        return False
    except:
        return False

def start_ollama():
    if not check_ollama():
        print("Starting Ollama...")
        try:
            if sys.platform == 'win32':
                subprocess.Popen(['ollama', 'serve'], creationflags=subprocess.CREATE_NO_WINDOW, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                subprocess.Popen(['ollama', 'serve'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(5)
        except:
            print("Please start Ollama manually: ollama serve")

if __name__ == '__main__':
    PORT = 8080
    print("=" * 60)
    print(" AI Chat Bot - Standalone Python Server")
    print("=" * 60)
    
    start_ollama()
    
    if check_ollama():
        print(" Ollama is running with my_model")
    else:
        print(" Ollama not running. Please start: ollama serve")
    
    print(f"\n Server running at: http://localhost:{PORT}")
    print(" Open this URL in your browser")
    print(" Features: RTL toggle, Favorites popup, Pause/Resume/Stop")
    print("=" * 60)
    
    with socketserver.TCPServer(("", PORT), AIRequestHandler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n Server stopped")
