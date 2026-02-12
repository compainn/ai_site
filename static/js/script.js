class PulseAI {
    constructor() {
        this.messageInput = document.getElementById('messageInput');
        this.sendBtn = document.getElementById('sendBtn');
        this.messages = document.getElementById('messages');
        this.chatArea = document.getElementById('chatArea');
        this.centerContent = document.getElementById('centerContent');

        this.isLoading = false;
        this.bindEvents();

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

            // Активируем кнопку если есть текст
            if (this.messageInput.value.trim().length > 0) {
                this.sendBtn.classList.add('active');
            } else {
                this.sendBtn.classList.remove('active');
            }
        });
    }

    async sendMessage() {
        const message = this.messageInput.value.trim();
        if (!message || this.isLoading) return;

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
            } else {
                this.addMessage('❌ Ошибка. Попробуй еще раз', 'assistant');
            }
        } catch (error) {
            this.removeTypingIndicator();
            this.addMessage('❌ Ошибка соединения', 'assistant');
        } finally {
            this.isLoading = false;
            this.sendBtn.disabled = false;
            this.messageInput.focus();
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
    // Экранируем HTML
    const div = document.createElement('div');
    div.textContent = text;
    text = div.innerHTML;

    // Убираем Markdown таблицы и мусор
    text = text.replace(/\|/g, '');              // убираем пайпы |
    text = text.replace(/[-]{3,}/g, '');         // убираем разделители ---
    text = text.replace(/#{1,6}\s?/g, '');       // убираем заголовки #
    text = text.replace(/\*\*/g, '');            // убираем **
    text = text.replace(/__/g, '');              // убираем __
    text = text.replace(/\*/g, '');              // убираем *
    text = text.replace(/_/g, '');               // убираем _
    text = text.replace(/`{3}/g, '');            // убираем ```
    text = text.replace(/`/g, '');               // убираем `
    text = text.replace(/\[.*?\]\(.*?\)/g, '');  // убираем ссылки [text](url)
    
    // ===== ДОБАВЛЯЕМ ЭТИ ТРИ СТРОКИ =====
    text = text.replace(/\|/g, '');              // УБИРАЕМ ВСЕ ПАЙПЫ |
    text = text.replace(/[-]{3,}/g, '');         // УБИРАЕМ ---
    text = text.replace(/\|/g, '');              // ЕЩЕ РАЗ НА ВСЯКИЙ
    // ===================================

    // Блоки кода (если остались)
    text = text.replace(/```(\w*)\n([\s\S]*?)```/g, '<pre><code>$2</code></pre>');
    text = text.replace(/`([^`]+)`/g, '<code>$1</code>');

    // УБИРАЕМ ПРИНУДИТЕЛЬНЫЕ ПЕРЕНОСЫ СТРОК
    // text = text.replace(/\n/g, '<br>');  // ЗАКОММЕНТИРОВАНО

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

document.addEventListener('DOMContentLoaded', () => {
    new PulseAI();
});
