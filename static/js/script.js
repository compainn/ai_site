class PulseAI {
    constructor() {
        this.messageInput = document.getElementById('messageInput');
        this.sendBtn = document.getElementById('sendBtn');
        this.micBtn = document.getElementById('micBtn');
        this.messages = document.getElementById('messages');
        this.chatArea = document.getElementById('chatArea');
        this.centerContent = document.getElementById('centerContent');
        this.newChatIcon = document.getElementById('newChatIcon');
        this.isRecording = false;
        this.recognition = null;

        this.isLoading = false;
        this.bindEvents();
        this.loadCurrentChatMessages();
        this.initSpeech();

        setTimeout(() => this.messageInput.focus(), 100);
    }

    bindEvents() {
        this.sendBtn.addEventListener('click', () => this.sendMessage());

        if (this.newChatIcon) {
            this.newChatIcon.addEventListener('click', () => this.createNewChat());
        }

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

        if (this.micBtn) {
            this.micBtn.addEventListener('click', () => this.toggleRecording());
        }
    }

    initSpeech() {
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        if (!SpeechRecognition) return;

        this.recognition = new SpeechRecognition();
        this.recognition.lang = 'ru-RU';
        this.recognition.continuous = false;
        this.recognition.interimResults = false;

        this.recognition.onresult = (e) => {
            const transcript = e.results[0][0].transcript;
            this.messageInput.value = transcript;
            this.messageInput.style.height = 'auto';
            this.messageInput.style.height = this.messageInput.scrollHeight + 'px';
            this.sendBtn.classList.add('active');
            this.stopRecording();
        };

        this.recognition.onerror = () => this.stopRecording();
        this.recognition.onend = () => this.stopRecording();
    }

    toggleRecording() {
        if (!this.recognition) {
            showNotification('Микрофон не поддерживается в этом браузере', true);
            return;
        }
        if (this.isRecording) {
            this.stopRecording();
        } else {
            this.startRecording();
        }
    }

    startRecording() {
        this.isRecording = true;
        this.micBtn.classList.add('recording');
        this.recognition.start();
    }

    stopRecording() {
        this.isRecording = false;
        if (this.micBtn) this.micBtn.classList.remove('recording');
        try { this.recognition.stop(); } catch(e) {}
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

    async createNewChat() {
        try {
            const response = await fetch('/api/chat/new', { method: 'POST' });
            if (response.ok) {
                window.location.reload();
            } else if (response.status === 401) {
                showNotification('Зарегистрируйтесь', true);
            }
        } catch (e) {
            console.error('Failed to create new chat', e);
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
                await this.typeMessage(data.response);
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

        let htmlText;

        if (role === 'assistant') {
            htmlText = this.formatText(text);
        } else {
            const tempDiv = document.createElement('div');
            tempDiv.textContent = text;
            htmlText = tempDiv.innerHTML;
        }

        messageDiv.innerHTML = `
            <div class="message-content">
                <div class="message-text">${htmlText}</div>
            </div>
        `;

        this.messages.appendChild(messageDiv);
        this.scrollToBottom();
    }

    async typeMessage(text) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message assistant';
        messageDiv.innerHTML = '<div class="message-content"><div class="message-text"></div></div>';
        this.messages.appendChild(messageDiv);
        const textEl = messageDiv.querySelector('.message-text');

        let displayed = '';
        const delay = text.length > 300 ? 8 : 14;

        for (let i = 0; i < text.length; i++) {
            displayed += text[i];
            textEl.innerHTML = this.formatText(displayed);
            this.scrollToBottom();
            await new Promise(r => setTimeout(r, delay));
        }

        textEl.innerHTML = this.formatText(text);
        this.scrollToBottom();
    }

    formatText(text) {
        const div = document.createElement('div');
        div.textContent = text;
        text = div.innerHTML;

        const hasSteps = /\[STEP\s*\d+:/i.test(text) || /\[ANSWER\]/i.test(text) ||
                         /\[ШАГ\s*\d+:/i.test(text) || /\[ОТВЕТ\]/i.test(text);

        if (hasSteps) {
            const parts = text.split(/(\[(?:STEP|ШАГ)\s*\d+:[^\]]+\]|\[(?:ANSWER|ОТВЕТ)\])/i);
            let result = '';
            let openBlock = false;
            parts.forEach((part) => {
                const stepMatch = part.match(/\[(?:STEP|ШАГ)\s*(\d+):\s*([^\]]+)\]/i);
                const answerMatch = part.match(/\[(?:ANSWER|ОТВЕТ)\]/i);
                if (stepMatch) {
                    if (openBlock) result += '</div></div>';
                    result += '<div class="step-block"><div class="step-header"><span class="step-number">Шаг ' + stepMatch[1] + '</span><span class="step-title">' + stepMatch[2].trim() + '</span></div><div class="step-body">';
                    openBlock = true;
                } else if (answerMatch) {
                    if (openBlock) result += '</div></div>';
                    result += '<div class="answer-block"><div class="answer-header">&#10003; Ответ</div><div class="answer-body">';
                    openBlock = true;
                } else {
                    result += part;
                }
            });
            if (openBlock) result += '</div></div>';
            text = result;
        }

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
    notification.style.position = 'fixed';
    notification.style.top = '20px';
    notification.style.left = '50%';
    notification.style.transform = 'translateX(-50%)';
    notification.style.padding = '12px 24px';
    notification.style.borderRadius = '30px';
    notification.style.zIndex = '2000';
    notification.style.fontSize = '14px';
    notification.style.fontWeight = '500';
    notification.style.boxShadow = '0 4px 12px rgba(0,0,0,0.3)';

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
                <span class="history-title">${chat.title}</span>
                <button class="delete-chat" onclick="deleteChat(${chat.id}, event)">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
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

const burgerMenu = document.getElementById('burgerMenu');
const menuPanel = document.getElementById('menuPanel');
const menuOverlay = document.getElementById('menuOverlay');
const closeMenu = document.getElementById('closeMenu');
const themeMenuLink = document.getElementById('themeMenuLink');
const logoutFromMenu = document.getElementById('logoutFromMenu');

function openMenu() {
    burgerMenu.classList.add('open');
    menuPanel.classList.add('open');
    menuOverlay.classList.add('active');
    document.body.style.overflow = 'hidden';
    loadChatHistory();
}


#проверка

function updateAILogo() {
    const isLight = document.body.classList.contains('light-theme');
    const aiLogo = document.getElementById('aiLogoDropdown');
    if (aiLogo) {
        aiLogo.src = isLight ? '/static/ai_logo_black.png' : '/static/ai_logo_white.png';
        console.log('Лого обновлен:', aiLogo.src);
    }
}    


function closeMenuFunc() {
    burgerMenu.classList.remove('open');
    menuPanel.classList.remove('open');
    menuOverlay.classList.remove('active');
    document.body.style.overflow = '';
}

if (burgerMenu && menuPanel && menuOverlay) {
    burgerMenu.addEventListener('click', openMenu);
    if (closeMenu) closeMenu.addEventListener('click', closeMenuFunc);
    menuOverlay.addEventListener('click', closeMenuFunc);

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && menuPanel.classList.contains('open')) {
            closeMenuFunc();
        }
    });
}

if (logoutFromMenu) {
    logoutFromMenu.addEventListener('click', () => {
        window.location.href = '/logout';
    });
}





function updateTelegramIcons() {
    const isLight = document.body.classList.contains('light-theme');
    const tgIcons = document.querySelectorAll('.tg-icon');
    tgIcons.forEach(icon => {
        icon.src = isLight ? '/static/telegram-black.png' : '/static/telegram-white.png';
    });
    const supportIcon = document.getElementById('supportIcon');
    if (supportIcon) {
        supportIcon.src = isLight ? '/static/support_black.png' : '/static/support_white.png';
    }
    const aiLogos = document.querySelectorAll('.ai-logo-dropdown');
    aiLogos.forEach(logo => {
        logo.src = isLight ? '/static/ai_logo_black.png' : '/static/ai_logo_white.png';
    });
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
    updateTelegramIcons();
    updateAILogo(); // <-- ТЕСТ ФУНКЦИЯ

    if (themeMenuLink) {
        themeMenuLink.addEventListener('click', () => {
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

            updateTelegramIcons();
        });
    }
});

document.addEventListener('DOMContentLoaded', () => {
    new PulseAI();
});

const openLoginModal = document.getElementById('openLoginModal');
const openLoginModalMenu = document.getElementById('openLoginModalMenu');
const loginModal = document.getElementById('loginModal');
const telegramLoginOption = document.getElementById('telegram-login-option');

function showLoginModal() {
    loginModal.style.display = 'block';
    menuOverlay.classList.add('active');
    document.body.style.overflow = 'hidden';
}

function closeLoginModal() {
    loginModal.style.display = 'none';
    menuOverlay.classList.remove('active');
    document.body.style.overflow = '';
}

if (openLoginModal) {
    openLoginModal.addEventListener('click', showLoginModal);
}

if (openLoginModalMenu) {
    openLoginModalMenu.addEventListener('click', showLoginModal);
}

menuOverlay.addEventListener('click', closeLoginModal);

function waitForElement(selector, callback) {
    const observer = new MutationObserver(() => {
        const element = document.querySelector(selector);
        if (element) {
            observer.disconnect();
            callback(element);
        }
    });
    observer.observe(document.body, { childList: true, subtree: true });
}

telegramLoginOption.addEventListener('click', () => {
    const widgetContainer = document.getElementById('telegram-widget-modal');
    widgetContainer.style.display = 'block';
    widgetContainer.innerHTML = '';
    const script = document.createElement('script');
    script.async = true;
    script.src = "https://telegram.org/js/telegram-widget.js?22";
    script.setAttribute('data-telegram-login', "pulseai_robot");
    script.setAttribute('data-size', "large");
    script.setAttribute('data-userpic', "false");
    script.setAttribute('data-onauth', "onTelegramAuth(user)");
    script.setAttribute('data-request-access', "write");
    widgetContainer.appendChild(script);
    waitForElement('#telegram-widget-modal iframe', (iframe) => {
        iframe.click();
    });
});

document.addEventListener('DOMContentLoaded', () => {
    const modelSelector = document.getElementById('modelSelector');
    const modelDropdown = document.getElementById('modelDropdown');
    if (modelSelector) {
        modelSelector.addEventListener('click', (e) => {
            e.stopPropagation();
            modelSelector.classList.toggle('open');
        });
        document.addEventListener('click', () => {
            modelSelector.classList.remove('open');
        });
    }
});
