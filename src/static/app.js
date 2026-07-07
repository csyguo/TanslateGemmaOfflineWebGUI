/* TranslateGemma4B GUI — Frontend (MIT License) */

(function () {
    'use strict';

    // --- DOM references ---
    var sourceLangSelect = document.getElementById('source-lang');
    var targetLangSelect = document.getElementById('target-lang');
    var sourceTextarea = document.getElementById('source-text');
    var targetTextarea = document.getElementById('target-text');
    var swapBtn = document.getElementById('swap-btn');
    var translateBtn = document.getElementById('translate-btn');
    var statusEl = document.getElementById('status');

    var isTranslating = false;
    var abortController = null;

    // --- Populate language dropdowns ---
    function populateLangSelect(selectEl, languages, commonCodes, defaultCode) {
        selectEl.innerHTML = '';

        // Common languages group
        var commonGroup = document.createElement('optgroup');
        commonGroup.label = 'Common';
        var allGroup = document.createElement('optgroup');
        allGroup.label = 'All Languages';

        var commonSet = {};
        for (var i = 0; i < commonCodes.length; i++) {
            commonSet[commonCodes[i]] = true;
        }

        for (var j = 0; j < languages.length; j++) {
            var lang = languages[j];
            var option = document.createElement('option');
            option.value = lang.code;
            option.textContent = lang.name;
            if (commonSet[lang.code]) {
                commonGroup.appendChild(option);
            } else {
                allGroup.appendChild(option);
            }
        }

        selectEl.appendChild(commonGroup);
        selectEl.appendChild(allGroup);
        selectEl.value = defaultCode;
    }

    function loadLanguages() {
        fetch('/api/languages')
            .then(function (res) { return res.json(); })
            .then(function (data) {
                var commonCodes = data.common_languages.map(function (l) { return l.code; });
                populateLangSelect(sourceLangSelect, data.all_languages, commonCodes, data.default_source_lang);
                populateLangSelect(targetLangSelect, data.all_languages, commonCodes, data.default_target_lang);
            })
            .catch(function (err) {
                setStatus('Failed to load language list', 'error');
                console.error(err);
            });
    }

    // --- Status ---
    function setStatus(msg, type) {
        statusEl.textContent = msg;
        statusEl.className = 'status';
        if (type) {
            statusEl.classList.add(type);
        }
    }

    // --- Translation ---
    function doTranslate() {
        if (isTranslating) return;

        var text = sourceTextarea.value.trim();
        if (!text) {
            setStatus('Please enter text to translate.', 'error');
            return;
        }

        var sourceLang = sourceLangSelect.value;
        var targetLang = targetLangSelect.value;

        isTranslating = true;
        translateBtn.disabled = true;
        targetTextarea.value = '';
        setStatus('Translating...', 'translating');

        abortController = new AbortController();

        fetch('/api/translate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                source_lang: sourceLang,
                target_lang: targetLang,
                text: text
            }),
            signal: abortController.signal
        }).then(function (response) {
            if (!response.ok) {
                return response.json().then(function (err) {
                    throw new Error(err.error || 'Translation failed');
                });
            }

            var reader = response.body.getReader();
            var decoder = new TextDecoder();
            var buffer = '';

            function processStream() {
                return reader.read().then(function (result) {
                    if (result.done) return;

                    buffer += decoder.decode(result.value, { stream: true });

                    // Process complete SSE events from buffer
                    var lines = buffer.split('\n');
                    // Keep incomplete line in buffer
                    buffer = lines.pop() || '';

                    for (var i = 0; i < lines.length; i++) {
                        var line = lines[i];
                        if (!line.startsWith('data: ')) continue;

                        var jsonStr = line.substring(6);
                        try {
                            var data = JSON.parse(jsonStr);
                            if (data.token) {
                                targetTextarea.value += data.token;
                                targetTextarea.scrollTop = targetTextarea.scrollHeight;
                            }
                            if (data.done) {
                                finishTranslation('Ready');
                                return;
                            }
                            if (data.error) {
                                finishTranslation(data.error, 'error');
                                return;
                            }
                        } catch (e) {
                            // Skip unparseable lines
                        }
                    }

                    return processStream();
                });
            }

            return processStream();
        }).catch(function (err) {
            if (err.name === 'AbortError') {
                finishTranslation('Ready');
            } else {
                finishTranslation(err.message, 'error');
            }
        });
    }

    function finishTranslation(msg, type) {
        isTranslating = false;
        translateBtn.disabled = false;
        abortController = null;
        setStatus(msg || 'Ready', type);
    }

    // --- Swap languages ---
    function swapLanguages() {
        var tmp = sourceLangSelect.value;
        sourceLangSelect.value = targetLangSelect.value;
        targetLangSelect.value = tmp;

        // Also swap text if target has content
        if (targetTextarea.value.trim()) {
            sourceTextarea.value = targetTextarea.value;
            targetTextarea.value = '';
        }
    }

    // --- Event bindings ---
    translateBtn.addEventListener('click', doTranslate);

    swapBtn.addEventListener('click', swapLanguages);

    document.addEventListener('keydown', function (e) {
        if (e.ctrlKey && e.key === 'Enter') {
            e.preventDefault();
            doTranslate();
        }
    });

    // Focus source textarea on load
    sourceTextarea.focus();

    // --- Init ---
    loadLanguages();
})();
