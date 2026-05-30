Module.register("MMM-FSS-Recommend", {
    defaults: {
        updateInterval: 5000
    },
    start() {
        this.result = null;
        this.loading = false;
    },
    getDom() {
        const wrapper = document.createElement("div");
        wrapper.id = "fss-recommend-container";

        if (this.loading) {
            wrapper.innerHTML = '<div class="fss-recommend-loading">Đang phân tích...</div>';
            return wrapper;
        }

        if (!this.result) {
            wrapper.innerHTML = '<div class="fss-recommend-empty">Nhập tên món ăn để tìm kiếm</div>';
            return wrapper;
        }

        const header = document.createElement("div");
        header.className = "fss-recommend-header";
        header.textContent = `📋 ${this.result.recipe_name}`;
        wrapper.appendChild(header);

        const table = document.createElement("table");
        table.className = "fss-recommend-table";
        table.innerHTML = `
            <tr><th>Nguyên liệu</th><th>Cần</th><th>Có</th><th></th></tr>
            ${this.result.ingredients.map(ing => `
                <tr class="fss-recommend-${ing.status}">
                    <td>${ing.name}</td>
                    <td>${ing.required}</td>
                    <td>${ing.available}</td>
                    <td>${ing.status === 'available' ? '✅' : ing.status === 'needed' ? '⚠️' : '❌'}</td>
                </tr>
            `).join('')}
        `;
        wrapper.appendChild(table);

        const summary = document.createElement("div");
        summary.className = "fss-recommend-summary";
        const missing = this.result.ingredients ? this.result.ingredients.filter(i => i.status === 'missing').length : 0;
        summary.textContent = missing > 0
            ? `❌ Còn thiếu ${missing} nguyên liệu`
            : '✅ Đã có đủ nguyên liệu!';
        wrapper.appendChild(summary);

        return wrapper;
    },
    socketNotificationReceived(notification, payload) {
        if (notification === "RECOMMEND_RESULT") {
            this.result = payload;
            this.loading = false;
            this.updateDom();
        } else if (notification === "RECOMMEND_LOADING") {
            this.loading = true;
            this.result = null;
            this.updateDom();
        }
    }
});
