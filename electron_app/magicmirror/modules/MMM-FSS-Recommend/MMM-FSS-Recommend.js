Module.register("MMM-FSS-Recommend", {
    defaults: {
        updateInterval: 5000
    },
    start() {
        this.result = null;
        this.loading = false;
        this.accumulatedResults = [];
        this.pendingCount = 0;
    },
    getDom() {
        const wrapper = document.createElement("div");
        wrapper.id = "fss-recommend-container";

        const headerRow = document.createElement("div");
        headerRow.className = "fss-recommend-header-row";

        const title = document.createElement("span");
        title.className = "fss-recommend-title";
        title.textContent = "🍳 Tìm món ăn";
        headerRow.appendChild(title);

        const searchBtn = document.createElement("button");
        searchBtn.className = "fss-recommend-search-btn";
        searchBtn.textContent = "🔍 Tìm kiếm";
        searchBtn.addEventListener("click", () => {
            this.sendNotification("KEYBOARD", {
                key: "recommendSearch",
                style: "default",
                data: {}
            });
        });
        headerRow.appendChild(searchBtn);
        wrapper.appendChild(headerRow);

        if (this.loading) {
            const loadingDiv = document.createElement("div");
            loadingDiv.className = "fss-recommend-loading";
            loadingDiv.textContent = "Đang phân tích...";
            wrapper.appendChild(loadingDiv);
            return wrapper;
        }

        if (!this.result) {
            const emptyDiv = document.createElement("div");
            emptyDiv.className = "fss-recommend-empty";
            emptyDiv.textContent = "Nhập tên món ăn để tìm kiếm";
            wrapper.appendChild(emptyDiv);
            return wrapper;
        }

        const recipeHeader = document.createElement("div");
        recipeHeader.className = "fss-recommend-header";
        recipeHeader.textContent = `📋 ${this.result.recipe_name}`;
        wrapper.appendChild(recipeHeader);

        const table = document.createElement("table");
        table.className = "fss-recommend-table";
        let tableHtml = '<tr><th>Nguyên liệu</th><th>Cần</th><th>Có</th><th></th></tr>';
        if (this.result.ingredients) {
            tableHtml += this.result.ingredients.map(ing => `
                <tr class="fss-recommend-${ing.status}">
                    <td>${ing.name}</td>
                    <td>${ing.required}</td>
                    <td>${ing.available}</td>
                    <td>${ing.status === 'available' ? '✅' : ing.status === 'needed' ? '⚠️' : '❌'}</td>
                </tr>
            `).join('');
        }
        table.innerHTML = tableHtml;
        wrapper.appendChild(table);

        const summary = document.createElement("div");
        summary.className = "fss-recommend-summary";
        const missing = this.result.ingredients
            ? this.result.ingredients.filter(i => i.status === 'missing').length
            : 0;
        summary.textContent = missing > 0
            ? `❌ Còn thiếu ${missing} nguyên liệu`
            : '✅ Đã có đủ nguyên liệu!';
        wrapper.appendChild(summary);

        return wrapper;
    },
    notificationReceived(notification, payload, sender) {
        if (notification === "RECIPE_SEARCH") {
            this.loading = true;
            this.result = null;
            this.updateDom();
            this.sendSocketNotification("RECIPE_SEARCH", payload);
        }
        if (notification === "KEYBOARD_INPUT" && payload.key === "recommendSearch") {
            const recipes = payload.message.split(",").map(s => s.trim()).filter(s => s);
            if (recipes.length === 0) return;
            this.loading = true;
            this.result = null;
            this.accumulatedResults = [];
            this.pendingCount = recipes.length;
            this.updateDom();
            recipes.forEach(r => this.sendSocketNotification("RECIPE_SEARCH", {recipe: r}));
        }
    },
    socketNotificationReceived(notification, payload) {
        if (notification === "RECOMMEND_RESULT") {
            this.accumulatedResults.push(payload);
            this.pendingCount--;
            if (this.pendingCount <= 0) {
                this.result = this.mergeResults(this.accumulatedResults);
                this.loading = false;
                this.updateDom();
                this.playNotificationSound("recommend_done");
            }
        } else if (notification === "RECOMMEND_LOADING") {
            this.loading = true;
            this.result = null;
            this.updateDom();
        }
    },
    mergeResults(results) {
        if (!results || results.length === 0) return null;
        if (results.length === 1) return results[0];

        const allIngredients = [];
        const recipeNames = [];

        for (const r of results) {
            if (r.recipe_name) recipeNames.push(r.recipe_name);
            if (r.ingredients) {
                allIngredients.push(...r.ingredients);
            }
        }

        const mergedName = recipeNames.length > 0
            ? recipeNames.join(", ")
            : "Nhiều món ăn";

        const availableCount = allIngredients.filter(i => i.status === 'available').length;
        const neededCount = allIngredients.filter(i => i.status === 'needed').length;
        const missingCount = allIngredients.filter(i => i.status === 'missing').length;

        return {
            recipe_name: mergedName,
            ingredients: allIngredients,
            total_items: allIngredients.length,
            available_count: availableCount,
            needed_count: neededCount,
            missing_count: missingCount,
            summary: missingCount > 0
                ? `❌ Còn thiếu ${missingCount} nguyên liệu`
                : '✅ Đã có đủ nguyên liệu!'
        };
    },
    playNotificationSound(type) {
        try {
            const ctx = new (window.AudioContext || window.webkitAudioContext)();
            const soundMap = {
                "recommend_done": { freq: 550, dur: 150, count: 2, gap: 100, freq2: 770 }
            };
            const s = soundMap[type] || { freq: 500, dur: 100, count: 1, gap: 0 };
            let startTime = ctx.currentTime;
            for (let i = 0; i < s.count; i++) {
                const osc = ctx.createOscillator();
                const gain = ctx.createGain();
                osc.connect(gain);
                gain.connect(ctx.destination);
                osc.frequency.value = s.freq2 && i === 1 ? s.freq2 : s.freq;
                osc.type = "sine";
                gain.gain.setValueAtTime(0.3, startTime);
                gain.gain.exponentialRampToValueAtTime(0.001, startTime + s.dur / 1000);
                osc.start(startTime);
                osc.stop(startTime + s.dur / 1000);
                startTime += (s.dur + s.gap) / 1000;
            }
        } catch (e) {
            // Audio not available
        }
    }
});
