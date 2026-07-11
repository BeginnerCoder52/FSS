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
        this.suggestedRecipes = [];
        this.showRecipeList = false;
        this.chipOffset = 0;
        this.CHIPS_PER_PAGE = 5;
        // Fuzzy suggestions from wrong input
        this.fuzzySuggestions = [];
        this.lastRawInput = "";

        // Xoá dữ liệu giả
        this.mockShoppingList = [];
        this.mockMenu = [];

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

        // Nút cuộn lên
        const upBtn = document.createElement("div");
        upBtn.innerHTML = '<i class="fas fa-chevron-up"></i>';
        upBtn.className = "fss-scroll-btn fss-scroll-up";
        const scrollUp = (e) => { e.preventDefault(); shoppingScroll.scrollTop -= 150; };
        upBtn.addEventListener("click", scrollUp);
        upBtn.addEventListener("touchend", scrollUp);
        shoppingPanel.appendChild(upBtn);

        // Scroll container for shopping list
        const shoppingScroll = document.createElement("div");
        shoppingScroll.className = "fss-shopping-scroll";

        // Nút cuộn xuống
        const downBtn = document.createElement("div");
        downBtn.innerHTML = '<i class="fas fa-chevron-down"></i>';
        downBtn.className = "fss-scroll-btn fss-scroll-down";
        const scrollDown = (e) => { e.preventDefault(); shoppingScroll.scrollTop += 150; };
        downBtn.addEventListener("click", scrollDown);
        downBtn.addEventListener("touchend", scrollDown);
        let ingredientsToBuy = this.hasSearched ? [] : this.mockShoppingList;
        if (this.result && this.result.ingredients) {
            ingredientsToBuy = this.result.ingredients
                .filter(i => i.status === 'missing' || i.status === 'needed')
                .map(i => ({
                    // Original name from NLP (proper case preserved by backend)
                    name: i.name
                        ? i.name.charAt(0).toUpperCase() + i.name.slice(1)
                        : "(không rõ)",
                    // Use full quantity string (e.g. "1 trái", "300g") if available,
                    // otherwise fall back to shortage number (with optional unit)
                    qty: (typeof i.required === 'string' && i.required.trim())
                        ? i.required
                        : (i.shortage != null && i.shortage !== 0)
                            ? (i.unit ? i.shortage + " " + i.unit : i.shortage)
                            : (i.required || "")
                }));
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
        shoppingPanel.appendChild(downBtn);

        // Pipeline time display for Recommend (Filter-Sort)
        if (this.result && this.result.pipeline_time_ms) {
            const timeDisplay = document.createElement("div");
            timeDisplay.className = "fss-pipeline-time";
            timeDisplay.textContent = "⏱ Filter-Sort pipeline: " + this.result.pipeline_time_ms + "ms";
            shoppingPanel.appendChild(timeDisplay);
        } else if (this.pipelineTimeMs !== null) {
            const timeDisplay = document.createElement("div");
            timeDisplay.className = "fss-pipeline-time";
            timeDisplay.textContent = "⏱ Round-trip: " + this.pipelineTimeMs + "ms";
            shoppingPanel.appendChild(timeDisplay);
        }
        /*
        // QR Code Download Section
        if (this.hasSearched && this.result) {
            const dlRow = document.createElement("div");
            dlRow.style.marginTop = "1em";
            dlRow.style.textAlign = "center";
            
            if (this.qrData) {
                const qrBox = document.createElement("div");
                qrBox.className = "fss-qr-box";
                const img = document.createElement("img");
                img.src = "data:image/png;base64," + this.qrData.qr_base64;
                img.style.width = "120px";
                img.style.borderRadius = "8px";
                img.style.border = "4px solid white";
                img.style.marginBottom = "0.5em";
                qrBox.appendChild(img);
                
                const helpText = document.createElement("div");
                helpText.textContent = "Quét mã bằng camera";
                helpText.style.fontSize = "0.8em";
                helpText.style.color = "var(--color-text-dimmed)";
                qrBox.appendChild(helpText);
                
                dlRow.appendChild(qrBox);
            } else {
                const dlBtn = document.createElement("div");
                dlBtn.className = "fss-chip";
                dlBtn.style.display = "inline-flex";
                dlBtn.style.backgroundColor = "var(--color-primary, #4facfe)";
                dlBtn.style.color = "#ffffff";
                dlBtn.style.border = "none";
                dlBtn.innerHTML = '<i class="fas fa-qrcode" style="margin-right:0.5em;"></i> Tải danh sách về ĐT';
                dlBtn.addEventListener("click", () => {
                    this.sendSocketNotification("GENERATE_QR", this.result);
                });
                dlBtn.addEventListener("touchend", (e) => {
                    e.preventDefault();
                    this.sendSocketNotification("GENERATE_QR", this.result);
                });
                dlRow.appendChild(dlBtn);
            }
            shoppingPanel.appendChild(dlRow);
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
        inputRow.style.zIndex = "100";

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

        // Suggested recipes chips — shown before search (normal) OR as fuzzy suggestions after wrong input
        const chipsToShow = (!this.hasSearched && this.suggestedRecipes.length > 0)
            ? { title: "Gợi ý nhanh:", recipes: this.suggestedRecipes, showMore: true }
            : (this.fuzzySuggestions.length > 0)
                ? { title: `Không tìm thấy "${this.lastRawInput}", có phải ý bạn là:`, recipes: this.fuzzySuggestions, showMore: false }
                : null;

        if (chipsToShow) {
            const chipContainer = document.createElement("div");
            chipContainer.className = "fss-chip-container";
            chipContainer.style.pointerEvents = "auto";
            chipContainer.style.zIndex = "200";
            chipContainer.style.position = "relative";

            const chipTitle = document.createElement("div");
            chipTitle.className = "fss-chip-title";
            chipTitle.textContent = chipsToShow.title;
            chipContainer.appendChild(chipTitle);

            const chipGrid = document.createElement("div");
            chipGrid.className = "fss-chip-grid";
            chipGrid.style.pointerEvents = "auto";

            chipsToShow.recipes.forEach(recipe => {
                const chip = document.createElement("div");
                chip.className = "fss-chip";
                chip.textContent = recipe;
                chip.style.pointerEvents = "auto";
                chip.style.cursor = "pointer";

                chip.addEventListener("click", () => {
                    this.fuzzySuggestions = [];
                    this.triggerSearch(recipe);
                });
                chip.addEventListener("touchend", (e) => {
                    e.preventDefault();
                    this.fuzzySuggestions = [];
                    this.triggerSearch(recipe);
                });

                chipGrid.appendChild(chip);
            });

            if (chipsToShow.showMore) {
                // "Xem thêm" button
                const moreChip = document.createElement("div");
                moreChip.className = "fss-chip fss-chip-more";
                moreChip.innerHTML = "Xem thêm ▾";
                moreChip.style.pointerEvents = "auto";
                moreChip.style.cursor = "pointer";
                moreChip.addEventListener("click", () => {
                    this.shuffleSuggestions();
                    this.updateDom(0);
                });
                moreChip.addEventListener("touchend", (e) => {
                    e.preventDefault();
                    this.shuffleSuggestions();
                    this.updateDom(0);
                });
                chipGrid.appendChild(moreChip);
            }

            chipContainer.appendChild(chipGrid);
            menuPanel.appendChild(chipContainer);
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
            trashBtn.style.pointerEvents = "auto";
            trashBtn.style.cursor = "pointer";
            trashBtn.style.zIndex = "200";
            trashBtn.style.position = "relative";
            // Capture `index` at time of DOM creation (avoids closure-over-loop issue)
            const capturedIndex = index;
            trashBtn.addEventListener("click", (e) => {
                e.stopPropagation();
                this.deleteRecipe(capturedIndex);
            });
            trashBtn.addEventListener("touchend", (e) => {
                e.preventDefault();
                e.stopPropagation();
                this.deleteRecipe(capturedIndex);
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
        this.updateDom(0);
    },

    deleteRecipe(index) {
        this.playNotificationSound("trash_delete");
        if (!this.hasSearched) {
            this.mockMenu.splice(index, 1);
            this.updateDom(0);
            return;
        }

        this.searchedRecipes.splice(index, 1);
        if (this.searchedRecipes.length === 0) {
            this.hasSearched = false;
            this.result = null;
            this.accumulatedResults = [];
            this.updateDom(0);
        } else {
            // Cập nhật ngầm: không đặt loading = true
            this.accumulatedResults = [];
            this.pendingCount = this.searchedRecipes.length;
            this.updateDom(0);
            this.searchedRecipes.forEach(r => this.sendSocketNotification("RECIPE_SEARCH", { recipe: r }));
        }
    },

    notificationReceived(notification, payload, sender) {
        if (notification === "RECIPE_SEARCH") {
            this.hasSearched = true;
            this.searchStartTime = Date.now();
            this.pipelineTimeMs = null;
            this.qrData = null;
            this.updateDom(0);
            this.sendSocketNotification("RECIPE_SEARCH", payload);
        }
        if (notification === "KEYBOARD_INPUT" && payload.key === "recommendSearch") {
            const recipes = payload.message.split(",").map(s => s.trim()).filter(s => s);
            if (recipes.length === 0) return;

            this.lastRawInput = recipes[recipes.length - 1]; // Track last for fuzzy
            this.fuzzySuggestions = [];
            this.hasSearched = true;
            this.searchStartTime = Date.now();
            this.pipelineTimeMs = null;
            this.qrData = null;
            this.searchedRecipes = this.searchedRecipes.concat(recipes);
            this.accumulatedResults = [];
            this.pendingCount = this.searchedRecipes.length;
            this.updateDom(0);
            this.searchedRecipes.forEach(r => this.sendSocketNotification("RECIPE_SEARCH", { recipe: r }));
        }
        
        if (notification === "KEYBOARD_TYPING" && payload.key === "recommendSearch") {
            const raw = payload.message || "";
            const parts = raw.split(",").map(s => s.trim());
            const currentPart = parts[parts.length - 1];
            let suggestions = [];
            
            const stripAccents = (str) => {
                return str.normalize("NFD")
                          .replace(/[\u0300-\u036f]/g, "")
                          .replace(/đ/g, "d").replace(/Đ/g, "D");
            };
            
            if (currentPart.length >= 2) {
                const lower = stripAccents(currentPart.toLowerCase());
                
                // Tiêu chí 1: Bắt đầu chính xác bằng từ khóa
                const startsWith = this.availableRecipes.filter(r => 
                    stripAccents(r.toLowerCase()).startsWith(lower)
                );
                
                // Tiêu chí 2: Có chứa từ khóa ở đầu một từ (vd: "thịt" trong "bánh mì kẹp thịt")
                const wordStarts = this.availableRecipes.filter(r => {
                    const rLower = stripAccents(r.toLowerCase());
                    return rLower.includes(" " + lower) && !rLower.startsWith(lower);
                });
                
                // Tiêu chí 3: Chứa từ khóa ở bất kỳ đâu
                const includes = this.availableRecipes.filter(r => {
                    const rLower = stripAccents(r.toLowerCase());
                    return rLower.includes(lower) && 
                           !rLower.startsWith(lower) && 
                           !rLower.includes(" " + lower);
                });

                // Ưu tiên độ dài ngắn hơn cho các kết quả cùng cấp để tránh lock vào tên quá dài
                startsWith.sort((a, b) => a.length - b.length);
                wordStarts.sort((a, b) => a.length - b.length);
                includes.sort((a, b) => a.length - b.length);

                suggestions = [...startsWith, ...wordStarts, ...includes].slice(0, 4);
            }
            this.sendNotification("KEYBOARD_SUGGESTIONS", { key: payload.key, suggestions: suggestions });
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
                // --- DEBUG: log full pipeline result to console ---
                console.log("[MMM-FSS-Recommend] Pipeline result:", JSON.stringify(this.result, null, 2));
                // Check if result is NOT_FOUND — show fuzzy suggestions
                const firstResult = this.accumulatedResults[0];
                const status = firstResult && firstResult.status;
                if (status === "NOT_FOUND" || (this.result && this.result.ingredients && this.result.ingredients.length === 0)) {
                    // Use server-supplied suggestions (Python backend handles difflib fuzzy matching)
                    const serverSuggestions = firstResult && firstResult.suggestions;
                    this.fuzzySuggestions = (serverSuggestions && serverSuggestions.length > 0)
                        ? serverSuggestions
                        : [];
                    // Reset search state so UI shows fuzzy chips (not an empty recipe history)
                    this.hasSearched = false;
                    this.searchedRecipes = this.searchedRecipes.filter(r => r !== this.lastRawInput);
                    
                    let msg = `Chưa tìm thấy món "${firstResult.recipe_name || this.lastRawInput}"`;
                    if (this.fuzzySuggestions.length > 0) {
                        const suggStr = this.fuzzySuggestions.slice(0, 3).join(", ");
                        msg += ` (Gợi ý: ${suggStr})`;
                    }
                    
                    this.sendNotification("FSS_NOTIFICATION", {
                        type: "recommend_done",
                        message: msg
                    });
                } else {
                    this.fuzzySuggestions = [];
                    this.sendNotification("FSS_NOTIFICATION", {
                        type: "recommend_done",
                        message: `Đã tìm thấy món "${firstResult.recipe_name || this.lastRawInput}"`
                    });
                }
                this.updateDom(0);
                this.playNotificationSound("recommend_done");
            }
        } else if (notification === "RECOMMEND_LOADING") {
            this.loading = true;
            this.result = null;
            this.updateDom(0);
        } else if (notification === "RECOMMEND_ERROR") {
            console.warn("[MMM-FSS-Recommend] Search error:", payload);
            this.pendingCount = Math.max(0, this.pendingCount - 1);
            if (this.pendingCount <= 0) {
                this.loading = false;
                this.updateDom(0);
            }
        } else if (notification === "RECIPES") {
            this.availableRecipes = payload.data || [];
            this.pickSuggestedRecipes();
            this.updateDom(0);
        }
    },
    triggerSearch(recipe) {
        if (!recipe) return;
        this.lastRawInput = recipe;
        this.fuzzySuggestions = [];
        this.hasSearched = true;
        this.searchStartTime = Date.now();
        this.pipelineTimeMs = null;
        this.qrData = null;

        if (!this.searchedRecipes.includes(recipe)) {
            this.searchedRecipes.push(recipe);
        }

        this.accumulatedResults = [];
        this.pendingCount = this.searchedRecipes.length;
        this.updateDom(0);
        this.searchedRecipes.forEach(r => this.sendSocketNotification("RECIPE_SEARCH", { recipe: r }));
    },
    shuffleSuggestions() {
        if (!this.availableRecipes || this.availableRecipes.length === 0) return;
        const shuffled = [...this.availableRecipes].sort(() => 0.5 - Math.random());
        this.suggestedRecipes = shuffled.slice(0, 4);
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
                "recommend_done": { freq: 550, dur: 150, count: 2, gap: 100, freq2: 770 },
                "trash_delete": { freq: 330, dur: 200, count: 2, gap: 150 }
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
        this.updateDom(0);
    }
});
