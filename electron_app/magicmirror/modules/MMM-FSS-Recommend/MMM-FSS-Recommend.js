Module.register("MMM-FSS-Recommend", {
    defaults: {
        updateInterval: 5000
    },
    getStyles() {
        return ["MMM-FSS-Recommend.css"];
    },
    start() {
        this.result = null;
        this.loading = false;
        this.hasSearched = false;
        this.searchedRecipes = [];
        this.accumulatedResults = [];
        this.pendingCount = 0;

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
        shoppingTitle.innerHTML = "DANH SÁCH ĐỀ XUẤT";
        shoppingTitle.style.fontWeight = "bold";
        shoppingTitle.style.textAlign = "center";
        shoppingTitle.style.fontSize = "1.2vw";
        shoppingTitle.style.marginBottom = "1.2em";
        shoppingPanel.appendChild(shoppingTitle);

        // Hiển thị dữ liệu thực hoặc mock data
        let ingredientsToBuy = this.hasSearched ? [] : this.mockShoppingList;
        if (this.result && this.result.ingredients) {
            ingredientsToBuy = this.result.ingredients
                .filter(i => i.status === 'missing')
                .map(i => ({ name: i.name, qty: i.required - i.available }));
        }

        ingredientsToBuy.forEach((item, index) => {
            const row = document.createElement("div");
            row.className = "fss-list-row";
            
            // Xóa viền cũ và thêm màu xen kẽ
            row.style.border = "none";
            row.style.backgroundColor = index % 2 === 0 ? "transparent" : "rgba(0,0,0,0.05)";
            row.style.whiteSpace = "nowrap";
            row.style.overflow = "hidden";
            row.style.fontSize = "0.95em";

            const leftPart = document.createElement("div");
            leftPart.className = "fss-list-left";
            leftPart.style.overflow = "hidden";
            leftPart.style.textOverflow = "ellipsis";
            leftPart.style.whiteSpace = "nowrap";
            leftPart.style.flex = "1"; // Để ép chữ dài bị cắt
            
            const circle = document.createElement("div");
            circle.className = "fss-circle-check";
            circle.style.cursor = "pointer";
            circle.style.flexShrink = "0"; // Giữ vòng tròn không bị móp
            circle.addEventListener("click", () => {
                this.removeIngredient(item.name);
            });
            leftPart.appendChild(circle);

            const nameSpan = document.createElement("span");
            nameSpan.textContent = item.name;
            leftPart.appendChild(nameSpan);

            const qtySpan = document.createElement("span");
            qtySpan.className = "fss-list-qty";
            qtySpan.textContent = item.qty;
            qtySpan.style.marginLeft = "1em"; // Tạo khoảng cách với tên món ăn

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
        menuTitle.style.fontWeight = "bold";
        menuTitle.style.textAlign = "center";
        menuTitle.style.fontSize = "1.2vw";
        menuTitle.style.marginBottom = "1.2em";
        menuPanel.appendChild(menuTitle);

        // Nút / Input Nhập thực đơn hôm nay đặt ở ĐẦU danh sách
        const inputRow = document.createElement("div");
        inputRow.className = "fss-list-row-full fss-input-row";
        inputRow.style.cursor = "pointer";
        inputRow.style.backgroundColor = "var(--color-panel-bg)";
        inputRow.style.borderRadius = "2em"; // Bo góc tròn theo em
        inputRow.style.border = "0.15vw solid var(--color-border)"; // Khung viền
        inputRow.style.padding = "0.8em 1.5em"; // Tránh chữ bị lẹm vào góc bo tròn
        inputRow.style.pointerEvents = "auto";
        inputRow.style.position = "relative";
        inputRow.style.zIndex = "10";

        const searchIcon = document.createElement("i");
        searchIcon.className = "fas fa-search";
        searchIcon.style.width = "1.2em"; // Bằng đúng kích thước vòng tròn
        searchIcon.style.textAlign = "center";
        searchIcon.style.marginRight = "0.5em";
        searchIcon.style.color = "var(--color-text-dimmed)";
        inputRow.appendChild(searchIcon);
        
        const inputSpan = document.createElement("span");
        inputSpan.textContent = this.loading ? "Đang phân tích..." : "Nhập tên món ăn...";
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

        // Danh sách các món ăn
        let currentMenu = this.hasSearched ? this.searchedRecipes : this.mockMenu;

        currentMenu.forEach((meal, index) => {
            const row = document.createElement("div");
            row.className = "fss-list-row-full";
            row.style.justifyContent = "space-between";
            row.style.border = "none"; // Xóa viền thừa của các dòng
            row.style.padding = "0.6em 1.5em"; // Bằng đúng padding của thanh input để căn lề đều tắp
            
            const leftDiv = document.createElement("div");
            leftDiv.style.display = "flex";
            leftDiv.style.alignItems = "center";

            const circle = document.createElement("div");
            circle.className = "fss-circle-check";
            leftDiv.appendChild(circle);
            
            const nameSpan = document.createElement("span");
            nameSpan.textContent = meal;
            leftDiv.appendChild(nameSpan);
            
            row.appendChild(leftDiv);

            // Thêm nút xóa nếu đây là danh sách thật của người dùng
            if (this.hasSearched) {
                const trashIcon = document.createElement("i");
                trashIcon.className = "fas fa-trash";
                trashIcon.style.color = "#ff4444";
                trashIcon.style.cursor = "pointer";
                trashIcon.style.padding = "0.3em";
                trashIcon.addEventListener("click", () => {
                    this.deleteRecipe(index);
                });
                row.appendChild(trashIcon);
            }

            menuPanel.appendChild(row);
        });

        wrapper.appendChild(menuPanel);

        return wrapper;
    },
    
    removeIngredient(name) {
        if (this.hasSearched && this.result && this.result.ingredients) {
            const target = this.result.ingredients.find(i => i.name === name);
            if (target) {
                target.status = 'available'; // Giả lập đã mua/chuẩn bị xong
            }
        } else {
            const idx = this.mockShoppingList.findIndex(i => i.name === name);
            if (idx > -1) {
                this.mockShoppingList.splice(idx, 1);
            }
        }
        this.updateDom();
    },

    deleteRecipe(index) {
        this.searchedRecipes.splice(index, 1);
        if (this.searchedRecipes.length === 0) {
            this.hasSearched = false;
            this.result = null;
            this.accumulatedResults = [];
            this.updateDom();
        } else {
            this.loading = true;
            this.accumulatedResults = [];
            this.pendingCount = this.searchedRecipes.length;
            this.updateDom();
            this.searchedRecipes.forEach(r => this.sendSocketNotification("RECIPE_SEARCH", { recipe: r }));
        }
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
            this.searchedRecipes = this.searchedRecipes.concat(recipes);
            this.accumulatedResults = [];
            this.pendingCount = this.searchedRecipes.length;
            this.updateDom();
            this.searchedRecipes.forEach(r => this.sendSocketNotification("RECIPE_SEARCH", { recipe: r }));
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
