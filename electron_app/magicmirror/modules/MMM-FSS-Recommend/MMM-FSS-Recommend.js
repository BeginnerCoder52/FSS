Module.register("MMM-FSS-Recommend", {
    defaults: {
        updateInterval: 5000
    },
    start() {
        this.result = null;
        this.loading = false;
        this.hasSearched = false;
        this.searchedRecipes = [];
        this.accumulatedResults = [];
        this.pendingCount = 0;
        this.searchStartTime = null;
        this.pipelineTimeMs = null;
        this.availableRecipes = [];
        this.showRecipeList = false;
        this.suggestedRecipes = [];
        this.chipOffset = 0;
        this.CHIPS_PER_PAGE = 5;
        // this.qrBase64 = null;
        // this.qrUrl = null;
        // this.showQrOverlay = false;
        // this.qrError = null;

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

        this.sendSocketNotification("GET_RECIPES", {});
    },
    getStyles() {
        return ["MMM-FSS-Recommend.css"];
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

        // Scroll container for shopping list
        const shoppingScroll = document.createElement("div");
        shoppingScroll.className = "fss-shopping-scroll";

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
            shoppingScroll.appendChild(row);
        });

        shoppingPanel.appendChild(shoppingScroll);

        // Pipeline time display for Recommend (NLP)
        if (this.result && this.result.pipeline_time_ms) {
            const timeDisplay = document.createElement("div");
            timeDisplay.className = "fss-pipeline-time";
            timeDisplay.textContent = "⏱ NLP pipeline: " + this.result.pipeline_time_ms + "ms";
            shoppingPanel.appendChild(timeDisplay);
        } else if (this.pipelineTimeMs !== null) {
            const timeDisplay = document.createElement("div");
            timeDisplay.className = "fss-pipeline-time";
            timeDisplay.textContent = "⏱ Round-trip: " + this.pipelineTimeMs + "ms";
            shoppingPanel.appendChild(timeDisplay);
        }

        /*
        // QR download button (shown after search result)
        if (this.result && this.result.recipe_name) {
            const qrBtn = document.createElement("div");
            qrBtn.className = "fss-qr-btn";
            qrBtn.textContent = "📱 Tải về";
            qrBtn.addEventListener("click", () => {
                this.qrError = null;
                this.qrBase64 = null;
                this.qrUrl = null;
                this.showQrOverlay = false;
                this.updateDom();
                this.sendSocketNotification("GENERATE_QR", this.result);
            });
            qrBtn.addEventListener("touchend", (e) => {
                e.preventDefault();
                this.qrError = null;
                this.qrBase64 = null;
                this.qrUrl = null;
                this.showQrOverlay = false;
                this.updateDom();
                this.sendSocketNotification("GENERATE_QR", this.result);
            });
            shoppingPanel.appendChild(qrBtn);
        }

        // QR code overlay
        if (this.showQrOverlay) {
            const overlay = document.createElement("div");
            overlay.className = "fss-qr-overlay";

            const qrContent = document.createElement("div");
            qrContent.className = "fss-qr-content";

            const qrTitle = document.createElement("div");
            qrTitle.className = "fss-qr-title";
            qrTitle.textContent = "Quét mã để xem công thức";
            qrContent.appendChild(qrTitle);

            if (this.qrError) {
                const errMsg = document.createElement("div");
                errMsg.className = "fss-qr-error";
                errMsg.textContent = "❌ " + this.qrError;
                qrContent.appendChild(errMsg);
            } else if (this.qrBase64) {
                const qrImg = document.createElement("img");
                qrImg.className = "fss-qr-img";
                qrImg.src = "data:image/png;base64," + this.qrBase64;
                qrImg.alt = "QR Code";
                qrContent.appendChild(qrImg);

                const qrUrlDisplay = document.createElement("div");
                qrUrlDisplay.className = "fss-qr-url";
                qrUrlDisplay.textContent = this.qrUrl;
                qrContent.appendChild(qrUrlDisplay);
            } else {
                const spinner = document.createElement("div");
                spinner.className = "fss-qr-spinner";
                spinner.textContent = "Đang tạo mã QR...";
                qrContent.appendChild(spinner);
            }

            const closeBtn = document.createElement("div");
            closeBtn.className = "fss-qr-close";
            closeBtn.textContent = "✕ Đóng";
            closeBtn.addEventListener("click", () => {
                this.showQrOverlay = false;
                this.updateDom();
            });
            closeBtn.addEventListener("touchend", (e) => {
                e.preventDefault();
                this.showQrOverlay = false;
                this.updateDom();
            });
            qrContent.appendChild(closeBtn);

            overlay.appendChild(qrContent);
            wrapper.appendChild(overlay);
        }
        */

        wrapper.appendChild(shoppingPanel);

        // Khung 2: THỰC ĐƠN HÔM NAY
        const menuPanel = document.createElement("div");
        menuPanel.className = "fss-panel fss-menu-panel";

        const menuTitle = document.createElement("div");
        menuTitle.className = "fss-panel-title-center";
        menuTitle.textContent = "THỰC ĐƠN HÔM NAY";
        menuTitle.style.fontWeight = "bold";
        menuTitle.style.textAlign = "center";
        menuTitle.style.fontSize = "1.3vw";
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
        searchIcon.style.width = "1.2em";
        searchIcon.style.textAlign = "center";
        searchIcon.style.marginRight = "0.5em";
        searchIcon.style.color = "var(--color-text-dimmed)";
        searchIcon.style.pointerEvents = "none";
        inputRow.appendChild(searchIcon);

        const inputSpan = document.createElement("span");
        inputSpan.textContent = "Nhập tên món ăn...";
        inputSpan.className = "fss-input-text";
        inputSpan.style.pointerEvents = "none";
        inputRow.appendChild(inputSpan);

        const self = this;
        const openKeyboard = function () {
            self.sendNotification("KEYBOARD", {
                key: "recommendSearch",
                style: "default",
                data: {}
            });
        };

        inputRow.addEventListener("click", openKeyboard);
        inputRow.addEventListener("touchend", function (e) {
            e.preventDefault();
            openKeyboard();
        });

        inputRow.style.touchAction = "manipulation";
        menuPanel.appendChild(inputRow);

        // Suggested recipe chips (shown when no search has been done)
        if (!this.hasSearched && this.suggestedRecipes.length > 0) {
            const chipSection = document.createElement("div");
            chipSection.className = "fss-chip-section";

            const chipLabel = document.createElement("div");
            chipLabel.className = "fss-chip-label";
            chipLabel.textContent = "Gợi ý nhanh:";
            chipSection.appendChild(chipLabel);

            const chipGrid = document.createElement("div");
            chipGrid.className = "fss-chip-grid";

            this.suggestedRecipes.forEach((recipe) => {
                const chip = document.createElement("div");
                chip.className = "fss-chip";
                chip.textContent = recipe;
                chip.setAttribute("data-recipe", recipe);

                const doSearch = () => {
                    if (this.hasSearched) return;
                    this.hasSearched = true;
                    this.searchStartTime = Date.now();
                    this.pipelineTimeMs = null;
                    this.searchedRecipes = [recipe];
                    this.accumulatedResults = [];
                    this.pendingCount = 1;
                    this.updateDom();
                    this.sendSocketNotification("RECIPE_SEARCH", { recipe: recipe });
                };

                chip.addEventListener("click", doSearch);
                chip.addEventListener("touchend", (e) => {
                    e.preventDefault();
                    doSearch();
                });

                chipGrid.appendChild(chip);
            });

            // Xem thêm button
            const moreChip = document.createElement("div");
            moreChip.className = "fss-chip fss-chip-more";
            moreChip.textContent = "Xem thêm ▾";

            moreChip.addEventListener("click", () => this.advanceChips());
            moreChip.addEventListener("touchend", (e) => {
                e.preventDefault();
                this.advanceChips();
            });

            chipGrid.appendChild(moreChip);
            chipSection.appendChild(chipGrid);
            menuPanel.appendChild(chipSection);
        }

        // Scroll container for recipe history
        const menuScroll = document.createElement("div");
        menuScroll.className = "fss-menu-scroll";

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

            // Nút Xoá món khỏi thực đơn
            const trashBtn = document.createElement("div");
            trashBtn.className = "fss-trash-btn";
            trashBtn.innerHTML = '<i class="fas fa-trash"></i>';
            trashBtn.addEventListener("click", (e) => {
                e.stopPropagation();
                this.deleteRecipe(index);
            });
            trashBtn.addEventListener("touchend", (e) => {
                e.preventDefault();
                e.stopPropagation();
                this.deleteRecipe(index);
            });
            leftDiv.appendChild(trashBtn);

            const nameSpan = document.createElement("span");
            nameSpan.textContent = meal;
            leftDiv.appendChild(nameSpan);

            row.appendChild(leftDiv);

            menuScroll.appendChild(row);
        });

        menuPanel.appendChild(menuScroll);
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
        if (!this.hasSearched) {
            this.mockMenu.splice(index, 1);
            this.updateDom();
            return;
        }

        this.searchedRecipes.splice(index, 1);
        if (this.searchedRecipes.length === 0) {
            this.hasSearched = false;
            this.result = null;
            this.accumulatedResults = [];
            this.updateDom();
        } else {
            // Cập nhật ngầm: không đặt loading = true
            this.accumulatedResults = [];
            this.pendingCount = this.searchedRecipes.length;
            this.updateDom();
            this.searchedRecipes.forEach(r => this.sendSocketNotification("RECIPE_SEARCH", { recipe: r }));
        }
    },

    notificationReceived(notification, payload, sender) {
        if (notification === "RECIPE_SEARCH") {
            this.hasSearched = true;
            this.searchStartTime = Date.now();
            this.pipelineTimeMs = null;
            this.updateDom();
            this.sendSocketNotification("RECIPE_SEARCH", payload);
        }
        if (notification === "KEYBOARD_INPUT" && payload.key === "recommendSearch") {
            const recipes = payload.message.split(",").map(s => s.trim()).filter(s => s);
            if (recipes.length === 0) return;

            this.hasSearched = true;
            this.searchStartTime = Date.now();
            this.pipelineTimeMs = null;
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
                if (this.searchStartTime) {
                    this.pipelineTimeMs = Date.now() - this.searchStartTime;
                    this.searchStartTime = null;
                }
                this.updateDom();
                this.playNotificationSound("recommend_done");
            }
        } else if (notification === "RECOMMEND_LOADING") {
            this.loading = true;
            this.result = null;
            this.updateDom();
        } else if (notification === "RECOMMEND_ERROR") {
            console.warn("[MMM-FSS-Recommend] Search error:", payload);
            this.pendingCount = Math.max(0, this.pendingCount - 1);
            if (this.pendingCount <= 0) {
                this.loading = false;
                this.updateDom();
            }
        } else if (notification === "RECIPES") {
            this.availableRecipes = payload.data || [];
            this.pickSuggestedRecipes();
            this.updateDom();
        // } else if (notification === "QR_CODE_READY") {
        //     this.qrBase64 = payload.base64;
        //     this.qrUrl = payload.url;
        //     this.showQrOverlay = true;
        //     this.updateDom();
        // } else if (notification === "QR_ERROR") {
        //     this.qrError = payload.error || "Unknown error";
        //     this.showQrOverlay = true;
        //     this.updateDom();
        }
    },
    mergeResults(results) {
        if (!results || results.length === 0) return null;
        if (results.length === 1) return results[0];

        const allIngredients = [];
        const recipeNames = [];
        let maxPipelineTime = 0;

        for (const r of results) {
            if (r.recipe_name) recipeNames.push(r.recipe_name);
            if (r.pipeline_time_ms && r.pipeline_time_ms > maxPipelineTime) {
                maxPipelineTime = r.pipeline_time_ms;
            }
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
            pipeline_time_ms: maxPipelineTime > 0 ? maxPipelineTime : null,
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
    },

    pickSuggestedRecipes() {
        if (!this.availableRecipes || this.availableRecipes.length === 0) {
            this.suggestedRecipes = [];
            return;
        }
        const shuffled = [...this.availableRecipes];
        for (let i = shuffled.length - 1; i > 0; i--) {
            const j = Math.floor(Math.random() * (i + 1));
            [shuffled[i], shuffled[j]] = [shuffled[j], shuffled[i]];
        }
        const count = Math.min(this.CHIPS_PER_PAGE, shuffled.length);
        this.suggestedRecipes = shuffled.slice(0, count);
        this.chipOffset = count;
    },

    advanceChips() {
        if (!this.availableRecipes || this.availableRecipes.length === 0) return;
        const remaining = this.availableRecipes.length - this.chipOffset;
        if (remaining <= 0) {
            this.chipOffset = 0;
        }
        const count = Math.min(this.CHIPS_PER_PAGE, this.availableRecipes.length);
        this.suggestedRecipes = [];
        for (let i = 0; i < count; i++) {
            const idx = (this.chipOffset + i) % this.availableRecipes.length;
            this.suggestedRecipes.push(this.availableRecipes[idx]);
        }
        this.chipOffset = (this.chipOffset + count) % this.availableRecipes.length;
        this.updateDom();
    }
});
