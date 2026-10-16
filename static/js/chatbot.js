document.addEventListener('DOMContentLoaded', function() {
    const chatForm = document.getElementById('chat-form');
    const chatInput = document.getElementById('chat-input');
    const chatMessages = document.getElementById('chat-messages');
    const submitBtn = document.getElementById('chat-submit');
    const convIdInput = document.getElementById('current-conversation-id');
    const docSelect = document.getElementById('document-select');
    
    // Modes & Empty States
    const modeCards = document.querySelectorAll('.chat-mode-card');
    const docSelectorContainer = document.getElementById('document-selector-container');
    const generalEmptyState = document.getElementById('general-empty-state');
    const documentEmptyState = document.getElementById('document-empty-state');
    
    let currentMode = 'general';
    let currentDocId = '';

    // Templates
    const userTpl = document.getElementById('user-message-template');
    const aiTpl = document.getElementById('ai-message-template');
    
    // --- MODE SWITCHING ---
    modeCards.forEach(card => {
        card.addEventListener('click', function() {
            if (!this.hasAttribute('data-mode')) return; // Link to KB
            
            modeCards.forEach(c => c.classList.remove('active'));
            this.classList.add('active');
            
            currentMode = this.dataset.mode;
            chatMessages.innerHTML = ''; // Clear chat on mode switch
            convIdInput.value = ''; // Reset conversation
            
            if (currentMode === 'general') {
                docSelectorContainer.style.display = 'none';
                chatMessages.appendChild(generalEmptyState);
                generalEmptyState.style.display = 'flex';
                documentEmptyState.style.display = 'none';
                currentDocId = '';
            } else if (currentMode === 'document') {
                docSelectorContainer.style.display = 'block';
                chatMessages.appendChild(documentEmptyState);
                generalEmptyState.style.display = 'none';
                documentEmptyState.style.display = 'flex';
                
                // If a doc is already selected in dropdown, use it
                if (docSelect.value) {
                    currentDocId = docSelect.value;
                    documentEmptyState.style.display = 'none';
                }
            }
        });
    });

    // --- DOCUMENT SELECTION ---
    if (docSelect) {
        docSelect.addEventListener('change', function() {
            currentDocId = this.value;
            if (currentDocId) {
                documentEmptyState.style.display = 'none';
                if(chatMessages.children.length === 1 && chatMessages.children[0].id === 'document-empty-state') {
                    // Start fresh
                    chatMessages.innerHTML = '';
                    // Optionally, show a welcome message from AI about the doc
                }
            } else {
                chatMessages.innerHTML = '';
                chatMessages.appendChild(documentEmptyState);
                documentEmptyState.style.display = 'flex';
            }
            convIdInput.value = ''; // Reset conversation
        });
    }

    // --- SUGGESTED QUESTIONS ---
    document.querySelectorAll('.suggested-question').forEach(sq => {
        sq.addEventListener('click', function() {
            chatInput.value = this.textContent;
            chatForm.dispatchEvent(new Event('submit'));
        });
    });

    // --- AI ANSWER POPUP ---
    const answerPopup = document.getElementById('answer-popup');
    const answerPopupContent = document.getElementById('answer-popup-content');
    const closePopupBtn = document.getElementById('close-answer-popup');
    const closePopupBottomBtn = document.getElementById('close-answer-popup-bottom');
    const copyPopupBtn = document.getElementById('copy-answer-popup');

    let currentAnswerText = '';

    function showAnswerPopup(answerHtml, sourcesHtml, rawText) {
        if (!answerPopup || !answerPopupContent) return;

        currentAnswerText = rawText || '';
        answerPopupContent.innerHTML = answerHtml + (sourcesHtml || '');
        answerPopup.classList.add('is-open');
        answerPopup.setAttribute('aria-hidden', 'false');
        document.body.style.overflow = 'hidden';

        if (window.MathJax && window.MathJax.typesetPromise) {
            MathJax.typesetPromise([answerPopupContent])
                .catch(err => console.error(err));
        }

        closePopupBtn?.focus();
    }

    function closeAnswerPopup() {
        answerPopup.classList.remove('is-open');
        answerPopup.setAttribute('aria-hidden', 'true');
        document.body.style.overflow = '';
    }

    closePopupBtn?.addEventListener('click', closeAnswerPopup);
    closePopupBottomBtn?.addEventListener('click', closeAnswerPopup);

    answerPopup?.addEventListener('click', function (event) {
        if (event.target === answerPopup) closeAnswerPopup();
    });

    document.addEventListener('keydown', function (event) {
        if (event.key === 'Escape' &&
            answerPopup.classList.contains('is-open')) {
            closeAnswerPopup();
        }
    });

    copyPopupBtn?.addEventListener('click', async function () {
        try {
            await navigator.clipboard.writeText(currentAnswerText);
            copyPopupBtn.innerHTML =
                '<i class="bi bi-check2"></i> Copied!';
            setTimeout(() => {
                copyPopupBtn.innerHTML =
                    '<i class="bi bi-clipboard"></i> Copy Answer';
            }, 1500);
        } catch (error) {
            alert('Copy failed. Please select and copy the answer manually.');
        }
    });

    // --- CHAT LOGIC ---
    function appendUserMessage(text) {
        generalEmptyState.style.display = 'none';
        documentEmptyState.style.display = 'none';
        
        const clone = userTpl.content.cloneNode(true);
        clone.querySelector('.message-content').textContent = text;
        chatMessages.appendChild(clone);
        scrollToBottom();
    }
    
    function appendAiMessage(text, sources) {
        const clone = aiTpl.content.cloneNode(true);
        
        // Protect MathJax blocks from marked.js parsing
        let mathBlocks = [];
        let tempText = text;
        
        // Protect block math: $$...$$
        tempText = tempText.replace(/\$\$([\s\S]+?)\$\$/g, function(match) {
            mathBlocks.push(match);
            return `__MATH_BLOCK_${mathBlocks.length - 1}__`;
        });
        
        // Protect inline math: $...$
        tempText = tempText.replace(/\$((?:[^$]|\\[$])+?)\$/g, function(match) {
            mathBlocks.push(match);
            return `__MATH_BLOCK_${mathBlocks.length - 1}__`;
        });
        
        // Markdown parsing and sanitization
        let formattedText = typeof marked !== 'undefined' ? marked.parse(tempText) : tempText.replace(/\n/g, '<br>');
        if (typeof DOMPurify !== 'undefined') {
            formattedText = DOMPurify.sanitize(formattedText);
        }
        
        // Restore math blocks
        mathBlocks.forEach((block, index) => {
            formattedText = formattedText.replace(`__MATH_BLOCK_${index}__`, block);
        });
        
        clone.querySelector('.message-content').innerHTML = formattedText;
        
        // Render MathJax if available
        if (window.MathJax && window.MathJax.typesetPromise) {
            // Because clone is a DocumentFragment, we can just render its content after appending.
            // But we append it below.
        }
        
        if (sources && sources.length > 0) {
            const container = clone.querySelector('.sources-container');
            const list = clone.querySelector('.sources-list');
            container.style.display = 'block';
            
            // Remove duplicates
            const uniqueSources = [];
            const seen = new Set();
            sources.forEach(s => {
                const identifier = s.type === 'knowledge_base' ? s.title : s.filename;
                if(!seen.has(identifier)) {
                    seen.add(identifier);
                    uniqueSources.push(s);
                }
            });
            
            uniqueSources.forEach(s => {
                const div = document.createElement('div');
                div.className = 'message-source';
                
                let icon = 'bi-file-earmark-text';
                let typeText = 'Document';
                
                if(s.type === 'knowledge_base') {
                    icon = 'bi-book';
                    typeText = 'Knowledge Base';
                }
                
                div.innerHTML = `<i class="bi ${icon} text-primary"></i> ${s.title || s.filename} <span class="badge bg-light text-dark border ms-auto">${typeText}</span>`;
                list.appendChild(div);
            });
        }
        
        
const answerHtml = clone.querySelector('.message-bubble').innerHTML;
const sourcesContainer = clone.querySelector('.sources-container');

showAnswerPopup(
    answerHtml,
    sourcesContainer ? sourcesContainer.outerHTML : '',
    text
);}

    
    function showLoading() {
        const div = document.createElement('div');
        div.id = 'chat-loading';
        div.className = 'message ai';
        div.innerHTML = `
            <div class="d-flex align-items-end mb-1">
                <div class="bg-primary text-white rounded-circle d-flex align-items-center justify-content-center me-2" style="width: 24px; height: 24px; font-size: 12px;">
                    <i class="bi bi-robot"></i>
                </div>
                <small class="text-muted fw-bold">LexAI</small>
            </div>
            <div class="message-bubble" style="background: transparent; border: none;">
                <div class="spinner-grow spinner-grow-sm text-primary me-1" role="status"></div>
                <div class="spinner-grow spinner-grow-sm text-primary me-1" role="status" style="animation-delay: 0.2s"></div>
                <div class="spinner-grow spinner-grow-sm text-primary" role="status" style="animation-delay: 0.4s"></div>
            </div>
        `;
        chatMessages.appendChild(div);
        scrollToBottom();
    }
    
    function removeLoading() {
        const loading = document.getElementById('chat-loading');
        if (loading) loading.remove();
    }
    
    function scrollToBottom() {
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }
    
    chatForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        
        const message = chatInput.value.trim();
        if (!message) return;
        
        if (currentMode === 'document' && !currentDocId) {
            alert('Please select a document first.');
            return;
        }
        
        appendUserMessage(message);
        chatInput.value = '';
        chatInput.disabled = true;
        submitBtn.disabled = true;
        showLoading();
        
        const payload = {
            message: message,
            document_id: currentMode === 'document' ? currentDocId : null,
            conversation_id: convIdInput.value || null
        };
        
        try {
            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            
            removeLoading();
            
            if (response.ok) {
                const data = await response.json();
                convIdInput.value = data.conversation_id; 
                appendAiMessage(data.answer, data.sources);
            } else {
                let errorMsg = "Unknown error occurred.";
                const contentType = response.headers.get("content-type");
                if (contentType && contentType.includes("application/json")) {
                    const err = await response.json();
                    errorMsg = err.error || errorMsg;
                } else {
                    errorMsg = `Server returned status ${response.status}`;
                }
                appendAiMessage("Error: " + errorMsg, []);
            }
        } catch (err) {
            removeLoading();
            appendAiMessage("Network error occurred.", []);
        } finally {
            chatInput.disabled = false;
            submitBtn.disabled = false;
            chatInput.focus();
        }
    });

    // Check URL params on load
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get('mode') === 'document' && urlParams.get('doc')) {
        setTimeout(() => {
            if (docSelect) {
                docSelect.value = urlParams.get('doc');
                docSelect.dispatchEvent(new Event('change'));
            }
        }, 100);
    }
    
    const savedConversationId = urlParams.get('conversation_id');

    if (savedConversationId) {
        convIdInput.value = savedConversationId;

        fetch(`/api/conversations/${savedConversationId}/messages`)
            .then(response => response.json())
            .then(data => {
                chatMessages.innerHTML = '';

                data.messages.forEach(msg => {
                    if (msg.sender === 'user') {
                        appendUserMessage(msg.message);
                    } else {
                        appendAiMessage(msg.message, []);
                    }
                });
            })
            .catch(error => console.error(error));
    }

});
