class PulseAI {
    constructor() {
        this.messageInput = document.getElementById('messageInput');
        this.sendBtn = document.getElementById('sendBtn');
        this.messages = document.getElementById('messages');
        this.chatArea = document.getElementById('chatArea');
        this.centerContent = document.getElementById('centerContent');

        this.isLoading = false;
        this.bindEvents();
        this.loadCurrentChatMessages();

        setTimeout(() => this.messageInput.focus(), 100);
    }

    bindEvents() {
        this.sendBtn.addEventListener('click', () => this.sendMessage());

        this.messageInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });

        this.messageInput.addEventListener('input', () => {
            this.messageInput.style.height = 'auto';
            this.messageInput.style.height = this.messageInput.scrollHeight + 'px';

            if (this.messageInput.value.trim().length > 0) {
                this.sendBtn.classList.add('active');
            } else {
                this.sendBtn.classList.remove('active');
            }
        });
    }

    loadCurrentChatMessages() {
        try {
            const messageElements = document.querySelectorAll('.message');
            if (messageElements.length > 0) {
                this.centerContent.style.display = 'none';
                this.chatArea.style.display = 'block';
            }
        } catch (e) {
            console.error('Error loading messages', e);
        }
    }

    async sendMessage() {
        const message = this.messageInput.value.trim();
        if (!message || this.isLoading) return;

        this.messageInput.blur();

        this.centerContent.style.opacity = '0';
        setTimeout(() => {
            this.centerContent.style.display = 'none';
            this.chatArea.style.display = 'block';
        }, 300);

        this.addMessage(message, 'user');

        this.messageInput.value = '';
        this.messageInput.style.height = 'auto';
        this.sendBtn.classList.remove('active');

        this.showTypingIndicator();

        this.isLoading = true;
        this.sendBtn.disabled = true;

        try {
            const response = await fetch('/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message })
            });

            const data = await response.json();

            this.removeTypingIndicator();

            if (response.ok) {
                this.addMessage(data.response, 'assistant');
                if (menuPanel && menuPanel.classList.contains('open')) {
                    loadChatHistory();
                }
            } else {
                this.addMessage('Ошибка с моделью, администрация уже уведомлена', 'assistant');
            }
        } catch (error) {
            this.removeTypingIndicator();
            this.addMessage('Ошибка соединения', 'assistant');
        } finally {
            this.isLoading = false;
            this.sendBtn.disabled = false;
        }
    }

    addMessage(text, role) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${role}`;

        messageDiv.innerHTML = `
            <div class="message-content">
                <div class="message-text">${this.formatText(text)}</div>
            </div>
        `;

        this.messages.appendChild(messageDiv);
        this.scrollToBottom();
    }

    formatText(text) {
        const div = document.createElement('div');
        div.textContent = text;
        text = div.innerHTML;

        text = text.replace(/```(\w*)\n([\s\S]*?)```/g, '<pre><code>$2</code></pre>');
        text = text.replace(/`([^`]+)`/g, '<code>$1</code>');
        text = text.replace(/\n/g, '<br>');

        return text;
    }

    showTypingIndicator() {
        const indicator = document.createElement('div');
        indicator.className = 'typing-indicator';
        indicator.id = 'typingIndicator';
        indicator.innerHTML = `
            <div class="typing-dot"></div>
            <div class="typing-dot"></div>
            <div class="typing-dot"></div>
        `;
        this.messages.appendChild(indicator);
        this.scrollToBottom();
    }

    removeTypingIndicator() {
        const indicator = document.getElementById('typingIndicator');
        if (indicator) indicator.remove();
    }

    scrollToBottom() {
        this.chatArea.scrollTop = this.chatArea.scrollHeight;
    }
}

function showNotification(message, isError = false) {
    const oldNotification = document.querySelector('.notification');
    if (oldNotification) oldNotification.remove();

    const notification = document.createElement('div');
    notification.className = 'notification';
    notification.textContent = message;
    notification.style.background = isError ? 'rgba(220, 53, 69, 0.9)' : 'var(--surface-hover)';

    document.body.appendChild(notification);

    setTimeout(() => {
        notification.remove();
    }, 3000);
}

async function loadChatHistory() {
    const historyList = document.getElementById('chatHistoryList');
    if (!historyList) return;

    try {
        const response = await fetch('/api/chats');
        const chats = await response.json();

        if (chats.length === 0) {
            historyList.innerHTML = '<div class="history-empty">Нет сохраненных чатов</div>';
            return;
        }

        historyList.innerHTML = chats.map(chat => `
            <div class="history-item ${chat.is_current ? 'current' : ''}" data-chat-id="${chat.id}">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 9l5 5 5-5M12 14V4"/>
                </svg>
                <span class="history-title">${chat.title}</span>
                <span class="history-date">${new Date(chat.updated_at).toLocaleDateString()}</span>
                <button class="delete-chat" onclick="deleteChat(${chat.id}, event)">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M18 6L6 18M6 6l12 12"/>
                    </svg>
                </button>
            </div>
        `).join('');

        document.querySelectorAll('.history-item').forEach(item => {
            const chatId = item.dataset.chatId;

            item.addEventListener('click', async (e) => {
                if (e.target.closest('.delete-chat')) return;

                const response = await fetch(`/api/chat/${chatId}/load`, { method: 'POST' });
                if (response.ok) {
                    window.location.reload();
                }
            });
        });

    } catch (e) {
        console.error('Failed to load chat history', e);
    }
}

async function deleteChat(chatId, event) {
    event.stopPropagation();

    if (!confirm('Удалить этот чат?')) return;

    try {
        const response = await fetch(`/api/chat/${chatId}/delete`, { method: 'POST' });
        if (response.ok) {
            loadChatHistory();

            const currentItem = document.querySelector(`.history-item[data-chat-id="${chatId}"].current`);
            if (currentItem) {
                window.location.reload();
            }
        }
    } catch (e) {
        console.error('Failed to delete chat', e);
    }
}

async function createNewChat() {
    try {
        const response = await fetch('/api/chat/new', { method: 'POST' });
        const data = await response.json();

        if (response.ok) {
            window.location.reload();
        } else if (response.status === 401) {
            showNotification('Зарегистрируйтесь', true);
            closeMenuFunc();
        }
    } catch (e) {
        console.error('Failed to create new chat', e);
    }
}

const burgerMenu = document.getElementById('burgerMenu');
const menuPanel = document.getElementById('menuPanel');
const menuOverlay = document.getElementById('menuOverlay');
const closeMenu = document.getElementById('closeMenu');
const newChatBtn = document.getElementById('newChatBtn');
const themeMenuItem = document.getElementById('themeMenuItem');

function openMenu() {
    burgerMenu.classList.add('open');
    menuPanel.classList.add('open');
    menuOverlay.classList.add('active');
    document.body.style.overflow = 'hidden';
    loadChatHistory();
}

function closeMenuFunc() {
    burgerMenu.classList.remove('open');
    menuPanel.classList.remove('open');
    menuOverlay.classList.remove('active');
    document.body.style.overflow = '';
}

if (burgerMenu && menuPanel && menuOverlay) {
    burgerMenu.addEventListener('click', openMenu);
    closeMenu.addEventListener('click', closeMenuFunc);
    menuOverlay.addEventListener('click', closeMenuFunc);

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && menuPanel.classList.contains('open')) {
            closeMenuFunc();
        }
    });
}

if (newChatBtn) {
    newChatBtn.addEventListener('click', createNewChat);
}

document.addEventListener('DOMContentLoaded', () => {
    const sunIcon = document.querySelector('.sun-icon');
    const moonIcon = document.querySelector('.moon-icon');
    const body = document.body;

    const savedTheme = localStorage.getItem('theme');
    if (savedTheme === 'light') {
        body.classList.add('light-theme');
        if (sunIcon && moonIcon) {
            sunIcon.style.display = 'none';
            moonIcon.style.display = 'block';
        }
    }

    if (themeMenuItem) {
        themeMenuItem.addEventListener('click', () => {
            body.classList.toggle('light-theme');

            if (body.classList.contains('light-theme')) {
                if (sunIcon && moonIcon) {
                    sunIcon.style.display = 'none';
                    moonIcon.style.display = 'block';
                }
                localStorage.setItem('theme', 'light');
            } else {
                if (sunIcon && moonIcon) {
                    sunIcon.style.display = 'block';
                    moonIcon.style.display = 'none';
                }
                localStorage.setItem('theme', 'dark');
            }
        });
    }
});

document.addEventListener('DOMContentLoaded', () => {
    new PulseAI();
});
