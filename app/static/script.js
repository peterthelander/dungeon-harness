        let currentSuggestions = [];

        function isFreeFormSuggestion(item) {
            return ["other", "something else"].includes(item.toLowerCase().replace(/[.?!]/g, ''));
        }

        function renderSuggestions(items) {
            const container = document.getElementById('suggestions');
            const uniqueItems = [...new Set((Array.isArray(items) ? items : [])
                .filter((item) => typeof item === 'string')
                .map((item) => item.trim())
                .filter((item) => item && item.length <= 32 && !isFreeFormSuggestion(item)))].slice(0, 4);

            currentSuggestions = uniqueItems;
            container.replaceChildren();
            container.hidden = uniqueItems.length === 0;

            for (const item of uniqueItems) {
                const button = document.createElement('button');
                button.type = 'button';
                button.className = 'suggestion-btn';
                button.textContent = item;
                button.addEventListener('click', () => sendAction(item));
                container.appendChild(button);
            }
        }

        function setSuggestionsDisabled(disabled) {
            document.querySelectorAll('.suggestion-btn').forEach((button) => {
                button.disabled = disabled;
            });
        }

        // Start Initialization Request to the Backend
        async function initializeEngine() {
            const fileInput = document.getElementById('pdf-upload');
            const file = fileInput.files[0];
            const btn = document.getElementById('init-engine-btn');
            const loadText = document.getElementById('loading-text');

            if (!file) {
                alert("Please select a PDF module first.");
                return;
            }

            // UI State change
            btn.disabled = true;
            btn.innerText = "Preparing...";
            loadText.style.display = "block";

            // Prepare Form Data
            const formData = new FormData();
            formData.append('file', file);

            try {
                // Fetch to standard implicit client backend route
                const response = await fetch('/upload', {
                    method: 'POST',
                    body: formData
                });
                
                await handleInitializationResponse(response);
            } catch (err) {
                console.error(err);
                alert("Could not connect to the engine.");
                resetInitUI();
            }
        }
        
        async function loadUrl(url) {
            const btn = document.getElementById('init-engine-btn');
            const loadText = document.getElementById('loading-text');

            // UI State change
            btn.disabled = true;
            btn.innerText = "Downloading & Preparing...";
            loadText.style.display = "block";

            try {
                const response = await fetch('/load_url', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ url: url })
                });
                
                await handleInitializationResponse(response);
            } catch (err) {
                console.error(err);
                alert("Could not connect to the engine.");
                resetInitUI();
            }
        }

        async function handleInitializationResponse(response) {
            const data = await response.json();

            if (response.ok) {
                // Inject the dynamic DM entry message generated from the PDF
                if (data.dm_text) {
                    appendMessage(data.dm_text, 'dm');
                }
                renderSuggestions(data.suggestions);

                // Show the initial generated image based on the intro text
                if (data.image_data) {
                    const canvas = document.getElementById('image-canvas');
                    const placeholder = document.getElementById('canvas-placeholder');
                    
                    canvas.src = data.image_data;
                    canvas.style.display = "block";
                    placeholder.style.display = "none";
                }

                // Success! Hide the overlay to reveal dashboard
                const overlay = document.getElementById('upload-overlay');
                overlay.style.opacity = '0';
                setTimeout(() => {
                    overlay.style.display = 'none';
                    document.getElementById('dashboard').style.display = 'flex';
                }, 500);
            } else {
                alert("Initialization error: " + data.error);
                resetInitUI();
            }
        }

        function resetInitUI() {
            const btn = document.getElementById('init-engine-btn');
            const loadText = document.getElementById('loading-text');
            btn.disabled = false;
            btn.innerText = "Begin Quest";
            loadText.style.display = "none";
        }

        // Handle Enter key for fast typing
        function handleKeyPress(e) {
            if (e.key === 'Enter') {
                sendAction();
            }
        }

        // Append DOM message utility
        function appendMessage(text, role) {
            const chatBox = document.getElementById('chat-window');
            const msgDiv = document.createElement('div');
            msgDiv.classList.add('message', role);
            
            // Model and player text are untrusted; sanitize the rendered Markdown.
            msgDiv.innerHTML = DOMPurify.sanitize(marked.parse(text));
            
            chatBox.appendChild(msgDiv);
            chatBox.scrollTop = chatBox.scrollHeight; // Auto-scroll to bottom
        }

        // Send Player text and execute backend thread
        async function sendAction(suggestedText = null) {
            const inputField = document.getElementById('action-input');
            const btn = document.getElementById('send-action-btn');
            const text = (suggestedText || inputField.value).trim();
            const previousSuggestions = currentSuggestions;
            const usedSuggestion = typeof suggestedText === 'string';

            if (!text) return;

            // Optimistic player text rendering
            appendMessage(text, 'player');
            inputField.value = '';
            
            // Disable input while resolving action
            inputField.disabled = true;
            btn.disabled = true;
            btn.textContent = "…";
            btn.setAttribute("aria-label", "DM thinking");
            btn.setAttribute("aria-busy", "true");
            renderSuggestions([]);
            setSuggestionsDisabled(true);
            
            const chatBox = document.getElementById('chat-window');
            
            // Create the real-time DM markdown container
            let msgDiv = document.createElement('div');
            msgDiv.classList.add('message', 'dm');
            msgDiv.style.display = 'none';
            chatBox.appendChild(msgDiv);
            chatBox.scrollTop = chatBox.scrollHeight;
            
            let fullText = "";

            try {
                const response = await fetch('/action', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ text: text })
                });

                if (!response.ok) {
                    const data = await response.json();
                    msgDiv.textContent = "ERROR: " + data.error;
                    renderSuggestions(previousSuggestions);
                } else {
                    // Read the NDJSON stream
                    const reader = response.body.getReader();
                    const decoder = new TextDecoder('utf-8');
                    let buffer = '';

                    while (true) {
                        const { done, value } = await reader.read();
                        if (done) break;
                        
                        buffer += decoder.decode(value, { stream: true });
                        const lines = buffer.split('\n');
                        buffer = lines.pop(); // keep partial lines in buffer

                        for (const line of lines) {
                            if (!line.trim()) continue;
                            const data = JSON.parse(line);
                            
                            if (data.type === 'text_chunk') {
                                fullText += data.text;
                                msgDiv.style.display = '';
                                msgDiv.innerHTML = DOMPurify.sanitize(marked.parse(fullText));
                                chatBox.scrollTop = chatBox.scrollHeight;
                            } 
                            else if (data.type === 'tool_call') {
                                const sysDiv = document.createElement('div');
                                sysDiv.classList.add('message', 'system');
                                sysDiv.innerHTML = DOMPurify.sanitize(marked.parse(data.message));
                                chatBox.appendChild(sysDiv);
                                
                                // Reset the DM message div for any subsequent text
                                msgDiv = document.createElement('div');
                                msgDiv.classList.add('message', 'dm');
                                msgDiv.style.display = 'none';
                                chatBox.appendChild(msgDiv);
                                fullText = "";
                                chatBox.scrollTop = chatBox.scrollHeight;
                            }
                            else if (data.type === 'status') {
                                btn.setAttribute("aria-label", data.message);
                                btn.title = data.message;
                            }
                            else if (data.type === 'suggestions') {
                                renderSuggestions(data.items);
                            }
                            else if (data.type === 'image') {
                                const canvas = document.getElementById('image-canvas');
                                const placeholder = document.getElementById('canvas-placeholder');
                                canvas.src = data.image_data;
                                canvas.style.display = "block";
                                placeholder.style.display = "none";
                            }
                            else if (data.type === 'error') {
                                msgDiv.append(document.createElement('br'), document.createTextNode("ERROR: " + data.error));
                            }
                            else if (data.type === 'done') {
                                break;
                            }
                        }
                    }
                }
            } catch (err) {
                console.error(err);
                msgDiv.innerHTML = "CRITICAL: Failed to communicate with engine backend.";
                renderSuggestions(previousSuggestions);
            } finally {
                // Re-enable inputs post-action
                inputField.disabled = false;
                btn.disabled = false;
                btn.textContent = "↑";
                btn.setAttribute("aria-label", "Send action");
                btn.removeAttribute("aria-busy");
                btn.title = "Send action";
                if (usedSuggestion) {
                    inputField.blur();
                } else {
                    inputField.focus();
                }
                
                // If DM message is empty after stream finishes (e.g. error or empty reply), remove it
                if (!fullText.trim()) {
                    // msgDiv.remove();
                }
            }
        }
