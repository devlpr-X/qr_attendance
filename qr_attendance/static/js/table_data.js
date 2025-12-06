/** 
 * Reusable Table Component 
 * Version 1.0
 * Works on any page that contains:
 *
 * <div class="table-root" 
 *      data-table="lesson_type"
 *      data-items="JSON DATA"
 *      data-columns="COLUMN DEFINITIONS">
 * </div>
 */

document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll(".table-root").forEach(initDynamicTable);
});

function initDynamicTable(root) {
    /* ------------------------------- LOAD CONFIG ------------------------------- */
    const tableName = root.dataset.table; 
    const allItems = JSON.parse(root.dataset.items || "[]");
    const columns = JSON.parse(root.dataset.columns || "[]");

    let filtered = [...allItems];
    let currentPage = 1;
    let itemsPerPage = 10;
    let sortColumn = columns[0]?.key || "id";
    let sortDirection = "asc";
    let currentActionId = null;

    /* ------------------------------- RENDER BASE HTML ------------------------------- */
    root.innerHTML = `
        <div class="table-actions">
            <input class="table-search" placeholder="Хайх..." />
            <span class="table-count">Нийт: <b class="count-total"></b> | Үзүүлж буй: <b class="count-showing"></b></span>
        </div>

        <div class="table-container">
            <table class="data-table">
                <thead><tr></tr></thead>
                <tbody></tbody>
            </table>
        </div>

        <div class="pagination"></div>

        <div class="action-menu" id="${tableName}-action-menu">
            <button class="action-item edit-row">✏️ Засах</button>
            <button class="action-item action-delete delete-row">🗑️ Устгах</button>
        </div>
    `;

    const searchInput = root.querySelector(".table-search");
    const tbody = root.querySelector("tbody");
    const theadRow = root.querySelector("thead tr");
    const pagination = root.querySelector(".pagination");
    const actionMenu = root.querySelector(`#${tableName}-action-menu`);

    /* -------------------------- BUILD TABLE HEAD -------------------------- */
    columns.forEach(col => {
        let th = document.createElement("th");
        th.textContent = col.label;
        if (col.width) th.style.width = col.width;

        if (col.sortable) {
            th.dataset.sort = col.key;
            th.innerHTML = `${col.label} <span class="sort-icon">⇅</span>`;
            th.style.cursor = "pointer";
            th.onclick = () => {
                if (sortColumn === col.key)
                    sortDirection = sortDirection === "asc" ? "desc" : "asc";
                else { sortColumn = col.key; sortDirection = "asc"; }

                sortData();
                renderTable();
                updateSortIcons();
            };
        }

        theadRow.appendChild(th);
    });

    // Add action column
    let thAction = document.createElement("th");
    thAction.style.textAlign = "center";
    thAction.textContent = "Үйлдэл";
    theadRow.appendChild(thAction);

    /* -------------------------- SEARCH -------------------------- */
    searchInput.addEventListener("input", () => {
        const q = searchInput.value.toLowerCase().trim();
        filtered = allItems.filter(item => {
            return columns.some(c => String(item[c.key]).toLowerCase().includes(q));
        });
        currentPage = 1;
        renderTable();
    });

    /* -------------------------- SORTING -------------------------- */
    function sortData() {
        filtered.sort((a, b) => {
            let A = String(a[sortColumn]).toLowerCase();
            let B = String(b[sortColumn]).toLowerCase();
            return sortDirection === "asc" ? A.localeCompare(B) : B.localeCompare(A);
        });
    }

    function updateSortIcons() {
        root.querySelectorAll(".sort-icon").forEach(icon => {
            icon.textContent = "⇅";
            icon.style.opacity = 0.3;
        });
        let active = root.querySelector(`th[data-sort="${sortColumn}"] .sort-icon`);
        if (active) {
            active.textContent = sortDirection === "asc" ? "▲" : "▼";
            active.style.opacity = 1;
        }
    }

    /* -------------------------- ACTION MENU -------------------------- */
    let menuHover = false;

    actionMenu.addEventListener("mouseenter", () => (menuHover = true));
    actionMenu.addEventListener("mouseleave", () => {
        menuHover = false;
        setTimeout(() => {
            if (!menuHover) actionMenu.style.display = "none";
        }, 80);
    });

    document.addEventListener("click", e => {
        if (!e.target.closest(".action-menu") && !e.target.closest(".action-dots")) {
            actionMenu.style.display = "none";
        }
    });

    /* -------------------------- MAIN RENDER -------------------------- */
    function renderTable() {
        const start = (currentPage - 1) * itemsPerPage;
        const pageData = filtered.slice(start, start + itemsPerPage);

        // counts
        root.querySelector(".count-total").textContent = allItems.length;
        root.querySelector(".count-showing").textContent = filtered.length;

        if (!pageData.length) {
            tbody.innerHTML = `<tr><td colspan="${columns.length + 1}" style="text-align:center; padding:1.5rem;">Өгөгдөл алга</td></tr>`;
            return;
        }

        tbody.innerHTML = pageData
            .map((row, idx) => {
                let cols = columns.map(c => `<td>${escapeHtml(row[c.key])}</td>`).join("");

                return `
                    <tr>
                        ${cols}
                        <td style="text-align:center;">
                            <button class="action-dots" onclick="openTableMenu(event, '${tableName}', ${row.id})">⋮</button>
                        </td>
                    </tr>
                `;
            })
            .join("");

        renderPagination();
        updateSortIcons();
    }

    /* -------------------------- PAGINATION -------------------------- */
    function renderPagination() {
        const totalPages = Math.ceil(filtered.length / itemsPerPage);
        pagination.innerHTML = "";

        if (totalPages <= 1) return;

        for (let i = 1; i <= totalPages; i++) {
            const btn = document.createElement("button");
            btn.textContent = i;
            if (i === currentPage) btn.classList.add("active");

            btn.onclick = () => {
                currentPage = i;
                renderTable();
            };

            pagination.appendChild(btn);
        }
    }

    /* -------------------------- GLOBAL MENU FUNCTION -------------------------- */
    window.openTableMenu = function (event, table, id) {
        currentActionId = id;

        const rect = event.target.getBoundingClientRect();
        actionMenu.style.display = "block";
        actionMenu.style.top = rect.bottom + 5 + "px";
        actionMenu.style.left = rect.left - 120 + "px";

        actionMenu.querySelector(".edit-row").onclick = () => {
            document.dispatchEvent(
                new CustomEvent(`table_edit_${table}`, { detail: { id } })
            );
            actionMenu.style.display = "none";
        };

        actionMenu.querySelector(".delete-row").onclick = () => {
            document.dispatchEvent(
                new CustomEvent(`table_delete_${table}`, { detail: { id } })
            );
            actionMenu.style.display = "none";
        };
    };

    /* -------------------------- UTIL -------------------------- */
    function escapeHtml(t) {
        const div = document.createElement("div");
        div.textContent = t;
        return div.innerHTML;
    }

    /* -------------------------- INITIAL RENDER -------------------------- */
    sortData();
    renderTable();
}
