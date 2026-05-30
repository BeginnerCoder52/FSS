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

        const rows = [
            ["q","w","e","r","t","y","u","i","o","p"],
            ["a","s","d","f","g","h","j","k","l"],
            ["⇧","z","x","c","v","b","n","m","⌫"],
            ["123","🇻🇳","␣","␣","␣","␣","␣","↵"]
        ];

        rows.forEach((row) => {
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
            this.query = this.query.slice(0, -1);
        } else if (key === "↵") {
            this.submit();
        } else if (key === "⇧" || key === "123") {
            // Placeholder for shift/numpad toggle
        } else {
            this.query += key;
        }
        input.value = this.query;
    },
    submit() {
        if (this.query.trim()) {
            this.sendSocketNotification("RECIPE_SEARCH", { recipe: this.query.trim() });
        }
    },
    setQuery(text) {
        this.query = text;
        const input = document.getElementById("fss-vk-input");
        if (input) input.value = text;
    }
});
