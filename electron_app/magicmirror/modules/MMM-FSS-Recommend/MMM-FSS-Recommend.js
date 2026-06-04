Module.register("MMM-FSS-Recommend", {
    defaults: {
        updateInterval: 5000
    },
    start() {
        this.result = null;
        this.loading = false;
        this.accumulatedResults = [];
        this.pendingCount = 0;
        this.hasSearched = false;
        
        // Mock data để hiển thị giống mockup tạm thời, cho đến khi có dữ liệu thật
        this.mockShoppingList = [
            { name: "Thịt heo", qty: "500g" },
            { name: "Thịt bò", qty: "500g" },
            { name: "Táo tàu", qty: "100g" },
            { name: "Hành tây", qty: "2 cây" }
        ];
        this.mockMenu = [
            "Thịt kho măng",
            "Cơm cuộn"
        ];
    },
    getDom() {
        const wrapper = document.createElement("div");
        wrapper.className = "fss-recommend-wrapper";

        // Khung 1: Danh sách nguyên liệu cần chuẩn bị thêm
        const shoppingPanel = document.createElement("div");
        shoppingPanel.className = "fss-panel fss-shopping-panel";
        
        const shoppingTitle = document.createElement("div");
        shoppingTitle.className = "fss-panel-title";
        shoppingTitle.innerHTML = "Danh sách<br>nguyên liệu cần<br>chuẩn bị thêm";
        shoppingPanel.appendChild(shoppingTitle);

        // Hiển thị dữ liệu thực hoặc mock data
        let ingredientsToBuy = this.hasSearched ? [] : this.mockShoppingList;
        if (this.result && this.result.ingredients) {
            ingredientsToBuy = this.result.ingredients
                .filter(i => i.status === 'missing')
                .map(i => ({ name: i.name, qty: i.required - i.available }));
        }

        ingredientsToBuy.forEach(item => {
            const row = document.createElement("div");
            row.className = "fss-list-row";
            
            const leftPart = document.createElement("div");
            leftPart.className = "fss-list-left";
            const circle = document.createElement("div");
            circle.className = "fss-circle-check";
            leftPart.appendChild(circle);
            
            const nameSpan = document.createElement("span");
            nameSpan.textContent = item.name;
            leftPart.appendChild(nameSpan);
            
            const qtySpan = document.createElement("span");
            qtySpan.className = "fss-list-qty";
            qtySpan.textContent = item.qty;
            
            row.appendChild(leftPart);
            row.appendChild(qtySpan);
            shoppingPanel.appendChild(row);
        });

        wrapper.appendChild(shoppingPanel);

        // Khung 2: THỰC ĐƠN HÔM NAY
        const menuPanel = document.createElement("div");
        menuPanel.className = "fss-panel fss-menu-panel";
        
        const menuTitle = document.createElement("div");
        menuTitle.className = "fss-panel-title-center";
        menuTitle.textContent = "THỰC ĐƠN HÔM NAY";
        menuPanel.appendChild(menuTitle);

        // Danh sách các món ăn
        let currentMenu = this.hasSearched ? [] : this.mockMenu;
        if (this.result && this.result.recipe_name) {
            currentMenu = this.result.recipe_name.split(',').map(s => s.trim());
        }

        currentMenu.forEach(meal => {
            const row = document.createElement("div");
            row.className = "fss-list-row-full";
            
            const circle = document.createElement("div");
            circle.className = "fss-circle-check";
            row.appendChild(circle);
            
            const nameSpan = document.createElement("span");
            nameSpan.textContent = meal;
            row.appendChild(nameSpan);
            
            menuPanel.appendChild(row);
        });

        // Nút / Input Nhập thực đơn hôm nay
        const inputRow = document.createElement("div");
        inputRow.className = "fss-list-row-full fss-input-row";
        
        const inputCircle = document.createElement("div");
        inputCircle.className = "fss-circle-check";
        inputRow.appendChild(inputCircle);
        
        const inputSpan = document.createElement("span");
        inputSpan.textContent = this.loading ? "Đang phân tích..." : "Nhập thực đơn hôm nay";
        inputSpan.className = "fss-input-text";
        inputRow.appendChild(inputSpan);

        // Gắn sự kiện click để mở bàn phím tìm kiếm
        inputRow.addEventListener("click", () => {
            this.sendNotification("KEYBOARD", {
                key: "recommendSearch",
                style: "default",
                data: {}
            });
        });
        menuPanel.appendChild(inputRow);

        wrapper.appendChild(menuPanel);

        return wrapper;
    },
    notificationReceived(notification, payload, sender) {
        if (notification === "RECIPE_SEARCH") {
            this.loading = true;
            this.hasSearched = true;
            this.result = null;
            this.updateDom();
            this.sendSocketNotification("RECIPE_SEARCH", payload);
        }
        if (notification === "KEYBOARD_INPUT" && payload.key === "recommendSearch") {
            const recipes = payload.message.split(",").map(s => s.trim()).filter(s => s);
            if (recipes.length === 0) return;
            this.loading = true;
            this.hasSearched = true;
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
