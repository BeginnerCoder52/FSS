Module.register("MMM-FSS-VirtualKeyboard", {
    defaults: {
        layout: "qwerty",
        showSearchBar: true,
        placeholderText: "Nhập tên món ăn...",
        submitOnEnter: true
    },
    start() {
        this.query = "";
        this.isVisible = true;
        this.vnMode = true;
        this.buffer = "";
        this.shifted = false;
    },

    getDom() {
        const wrapper = document.createElement("div");
        wrapper.id = "fss-vk-container";

        if (this.config.showSearchBar) {
            const bar = document.createElement("div");
            bar.id = "fss-vk-search-bar";
            const input = document.createElement("input");
            input.id = "fss-vk-input";
            input.type = "text";
            input.placeholder = this.config.placeholderText;
            input.value = this.query;
            input.addEventListener("input", (e) => { this.query = e.target.value; });
            input.addEventListener("keydown", (e) => {
                if (e.key === "Enter") this.submit();
            });
            bar.appendChild(input);

            const searchBtn = document.createElement("button");
            searchBtn.id = "fss-vk-search-btn";
            searchBtn.textContent = "🔍";
            searchBtn.addEventListener("click", () => this.submit());
            bar.appendChild(searchBtn);
            wrapper.appendChild(bar);
        }

        const vnToggle = document.createElement("div");
        vnToggle.id = "fss-vk-lang-bar";
        const langBtn = document.createElement("button");
        langBtn.id = "fss-vk-lang-btn";
        langBtn.textContent = this.vnMode ? "VN" : "EN";
        langBtn.classList.toggle("vn-active", this.vnMode);
        langBtn.addEventListener("click", () => {
            this.vnMode = !this.vnMode;
            this.buffer = "";
            langBtn.textContent = this.vnMode ? "VN" : "EN";
            langBtn.classList.toggle("vn-active", this.vnMode);
        });
        vnToggle.appendChild(langBtn);

        const clearBtn = document.createElement("button");
        clearBtn.id = "fss-vk-clear-btn";
        clearBtn.textContent = "Clear";
        clearBtn.addEventListener("click", () => {
            this.query = "";
            this.buffer = "";
            const input = document.getElementById("fss-vk-input");
            if (input) input.value = "";
        });
        vnToggle.appendChild(clearBtn);
        wrapper.appendChild(vnToggle);

        const baseRows = [
            ["q","w","e","r","t","y","u","i","o","p"],
            ["a","s","d","f","g","h","j","k","l"],
            ["⇧","z","x","c","v","b","n","m","⌫"],
            ["123","␣","↵"]
        ];

        baseRows.forEach((row) => {
            const rowDiv = document.createElement("div");
            rowDiv.className = "fss-vk-row";
            row.forEach(key => {
                const btn = document.createElement("button");
                btn.className = "fss-vk-key";
                btn.textContent = key;
                btn.dataset.key = key;
                btn.addEventListener("click", () => this.onKeyPress(key));
                if (key === "␣") btn.classList.add("fss-vk-space");
                if (key === "↵") btn.classList.add("fss-vk-enter");
                if (key === "⌫") btn.classList.add("fss-vk-backspace");
                if (key === "⇧") btn.classList.add("fss-vk-shift");
                if (key === "123") btn.classList.add("fss-vk-num");
                rowDiv.appendChild(btn);
            });
            wrapper.appendChild(rowDiv);
        });

        return wrapper;
    },

    onKeyPress(key) {
        const input = document.getElementById("fss-vk-input");
        if (!input) return;

        if (key === "⌫") {
            if (this.buffer.length > 0) {
                this.buffer = this.buffer.slice(0, -1);
            } else {
                this.query = this.query.slice(0, -1);
            }
        } else if (key === "↵") {
            this.submit();
        } else if (key === "⇧") {
            this.shifted = !this.shifted;
        } else if (key === "123") {
            return;
        } else if (key === "␣") {
            this.flushBuffer();
            this.query += " ";
        } else {
            if (this.vnMode) {
                this.typeTelex(key);
            } else {
                this.flushBuffer();
                this.query += key;
            }
        }

        input.value = this.query + (this.buffer || "");
    },

    flushBuffer() {
        if (this.buffer) {
            this.query += this.buffer;
            this.buffer = "";
        }
    },

    typeTelex(ch) {
        const telexMap = {
            "a": { "w": "ă", "a": "â" },
            "d": { "d": "đ" },
            "e": { "e": "ê" },
            "o": { "w": "ơ", "o": "ô" },
            "u": { "w": "ư" }
        };

        const toneKeys = { "s": 1, "f": 1, "r": 1, "x": 1, "j": 1 };

        const composed = {
            "a": { "s": "á", "f": "à", "r": "ả", "x": "ã", "j": "ạ" },
            "ă": { "s": "ắ", "f": "ằ", "r": "ẳ", "x": "ẵ", "j": "ặ" },
            "â": { "s": "ấ", "f": "ầ", "r": "ẩ", "x": "ẫ", "j": "ậ" },
            "e": { "s": "é", "f": "è", "r": "ẻ", "x": "ẽ", "j": "ẹ" },
            "ê": { "s": "ế", "f": "ề", "r": "ể", "x": "ễ", "j": "ệ" },
            "i": { "s": "í", "f": "ì", "r": "ỉ", "x": "ĩ", "j": "ị" },
            "o": { "s": "ó", "f": "ò", "r": "ỏ", "x": "õ", "j": "ọ" },
            "ô": { "s": "ố", "f": "ồ", "r": "ổ", "x": "ỗ", "j": "ộ" },
            "ơ": { "s": "ớ", "f": "ờ", "r": "ở", "x": "ỡ", "j": "ợ" },
            "u": { "s": "ú", "f": "ù", "r": "ủ", "x": "ũ", "j": "ụ" },
            "ư": { "s": "ứ", "f": "ừ", "r": "ử", "x": "ữ", "j": "ự" },
            "y": { "s": "ý", "f": "ỳ", "r": "ỷ", "x": "ỹ", "j": "ỵ" }
        };

        const upperComposed = {};
        for (const base in composed) {
            upperComposed[base.toUpperCase()] = {};
            for (const tone in composed[base]) {
                upperComposed[base.toUpperCase()][tone] = composed[base][tone].toUpperCase();
            }
        }
        const upperTelexMap = {};
        for (const base in telexMap) {
            upperTelexMap[base.toUpperCase()] = {};
            for (const mod in telexMap[base]) {
                upperTelexMap[base.toUpperCase()][mod] = telexMap[base][mod].toUpperCase();
            }
        }

        const lastChar = this.buffer.slice(-1);
        const isUpper = lastChar === lastChar.toUpperCase() && lastChar !== lastChar.toLowerCase();
        const lowerCh = ch.toLowerCase();

        // Handle tone keys (s, f, r, x, j)
        if (toneKeys[lowerCh] && lastChar) {
            const lastLower = lastChar.toLowerCase();
            const cm = isUpper ? upperComposed : composed;
            if (cm[lastLower] && cm[lastLower][lowerCh]) {
                this.buffer = this.buffer.slice(0, -1) + cm[lastLower][lowerCh];
                return;
            }
            this.flushBuffer();
            this.query += ch;
            return;
        }

        // Handle Vietnamese character composition (Telex)
        if (this.vnMode) {
            const prev = this.buffer.slice(-1).toLowerCase();
            if (telexMap[prev] && telexMap[prev][lowerCh]) {
                this.buffer = this.buffer.slice(0, -1) + telexMap[prev][lowerCh];
                return;
            }
        }

        this.buffer += ch;
    },

    submit() {
        this.flushBuffer();
        if (this.query.trim()) {
            const payload = { recipe: this.query.trim() };
            // Send to own backend (for echo/self-reference)
            this.sendSocketNotification("RECIPE_SEARCH", payload);
            // Broadcast to all other modules via MagicMirror's inter-module system
            this.sendNotification("RECIPE_SEARCH", payload);
        }
    },
    setQuery(text) {
        this.query = text;
        this.buffer = "";
        const input = document.getElementById("fss-vk-input");
        if (input) input.value = text;
    }
});
