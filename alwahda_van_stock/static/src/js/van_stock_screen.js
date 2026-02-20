/** @odoo-module */

console.log("[VanStockScreen] ========== MODULE LOADING ==========");
console.log("[VanStockScreen] Module file loaded at:", new Date().toISOString());

import { Component, useState, onMounted } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { usePos } from "@point_of_sale/app/hooks/pos_hook";

export class VanStockScreen extends Component {
    static template = "alwahda_van_stock.VanStockScreen";
    static storeOnOrder = false;
    static props = [];

    setup() {
        console.log("[VanStockScreen] ========== SETUP START ==========");
        this.pos = usePos();
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.state = useState({
            products: [], // Products added to request
            requests: [],
            loading: false,
            activeTab: 'new',
            requestType: 'load',
            searchWord: '',
            selectedCategory: null,
            warehouseProducts: [], // Products from warehouse with qty > 0
        });
        onMounted(() => {
            console.log("[VanStockScreen] ========== ON MOUNTED ==========");
            this.loadRequests();
            this.loadWarehouseProducts();
        });
        console.log("[VanStockScreen] ========== SETUP END ==========");
    }

    getSessionId() {
        return odoo.pos_session_id;
    }

    async loadWarehouseProducts() {
        console.log("[VanStockScreen] ========== LOAD WAREHOUSE PRODUCTS ==========");
        try {
            const sessionId = this.getSessionId();
            const products = await this.orm.call(
                "pos.session",
                "get_warehouse_stock_products",
                [[sessionId]]
            );
            this.state.warehouseProducts = products;
            console.log("[VanStockScreen] Warehouse products loaded:", products.length);
        } catch (error) {
            console.error("[VanStockScreen] Error loading warehouse products:", error);
            this.notification.add("Error loading warehouse products", { type: "danger" });
        }
    }

    // Get products to display from warehouse (only products with qty > 0)
    get productsToDisplay() {
        console.log("[VanStockScreen] ========== PRODUCTS TO DISPLAY ==========");
        console.log("[VanStockScreen] productsToDisplay - searchWord:", this.state.searchWord);
        console.log("[VanStockScreen] warehouseProducts count:", this.state.warehouseProducts.length);

        let products = this.state.warehouseProducts;

        if (this.state.searchWord.trim() !== "") {
            const searchLower = this.state.searchWord.toLowerCase();
            products = products.filter(p =>
                (p.display_name || p.name || '').toLowerCase().includes(searchLower) ||
                (p.default_code || '').toLowerCase().includes(searchLower) ||
                (p.barcode || '').toLowerCase().includes(searchLower)
            );
        }

        const result = products
            .slice(0, 100)
            .sort((a, b) => (a.display_name || a.name).localeCompare(b.display_name || b.name));

        console.log("[VanStockScreen] productsToDisplay result count:", result.length);
        return result;
    }

    updateSearchWord(event) {
        this.state.searchWord = event.target.value;
        console.log("[VanStockScreen] updateSearchWord:", this.state.searchWord);
    }

    clearSearch() {
        console.log("[VanStockScreen] clearSearch");
        this.state.searchWord = '';
    }

    // Add product to request list
    addProductToRequest(product) {
        console.log("[VanStockScreen] addProductToRequest:", product.display_name || product.name, "id:", product.id);
        const existingProduct = this.state.products.find(p => p.id === product.id);
        if (existingProduct) {
            existingProduct.transferQty += 1;
            console.log("[VanStockScreen] Product exists, new qty:", existingProduct.transferQty);
        } else {
            this.state.products.push({
                id: product.id,
                name: product.display_name || product.name,
                quantity: product.quantity, // warehouse available quantity
                uom: product.uom || 'Units',
                selected: true,
                transferQty: 1,
            });
            console.log("[VanStockScreen] Product added, total products:", this.state.products.length);
        }
        this.notification.add(`${product.display_name || product.name} added to request`, { type: "info" });
    }

    removeProduct(product) {
        console.log("[VanStockScreen] removeProduct:", product.name);
        const index = this.state.products.findIndex(p => p.id === product.id);
        if (index > -1) {
            this.state.products.splice(index, 1);
            console.log("[VanStockScreen] Product removed, remaining:", this.state.products.length);
        }
    }

    getProductImage(product) {
        return `/web/image?model=product.product&field=image_128&id=${product.id}`;
    }

    async loadRequests() {
        console.log("[VanStockScreen] ========== LOAD REQUESTS START ==========");
        try {
            const sessionId = this.getSessionId();
            const data = await this.orm.call(
                "pos.session",
                "get_van_requests",
                [[sessionId], this.state.requestType]
            );
            console.log("[VanStockScreen] loadRequests response:", JSON.stringify(data));
            this.state.requests = data;
            console.log("[VanStockScreen] loadRequests loaded:", data.length, "requests");
        } catch (error) {
            console.error("[VanStockScreen] ========== LOAD REQUESTS ERROR ==========");
            console.error("[VanStockScreen] Error loading requests:", error);
            console.error("[VanStockScreen] Error message:", error?.message);
            console.error("[VanStockScreen] Error data:", error?.data);
        }
        console.log("[VanStockScreen] ========== LOAD REQUESTS END ==========");
    }

    updateQuantity(product, event) {
        const qty = parseFloat(event.target.value) || 0;
        product.transferQty = Math.max(0.01, qty);
        console.log("[VanStockScreen] updateQuantity:", product.name, "->", product.transferQty);
    }

    toggleSelect(product) {
        product.selected = !product.selected;
        console.log("[VanStockScreen] toggleSelect:", product.name, "->", product.selected);
    }

    setActiveTab(tab) {
        this.state.activeTab = tab;
        if (tab === 'history') {
            console.log("[VanStockScreen] Loading requests for history tab");
            this.loadRequests();
        }
    }

    async submitRequest() {
        const sessionId = this.getSessionId();
        console.log("[VanStockScreen] POS Session ID:", sessionId);
        console.log("[VanStockScreen] Request Type:", this.state.requestType);
        console.log("[VanStockScreen] Products in request:", this.state.products);

        const lines = this.state.products
            .filter(p => p.selected && p.transferQty > 0)
            .map(p => ({
                product_id: p.id,
                quantity: p.transferQty,
                source_quantity: p.quantity,
            }));

        console.log("[VanStockScreen] Lines to submit:", lines);

        if (lines.length === 0) {
            this.notification.add("Please select products to request", { type: "warning" });
            return;
        }

        this.state.loading = true;
        try {
            console.log("[VanStockScreen] Calling create_van_request_from_pos...");

            const result = await this.orm.call(
                "pos.session",
                "create_van_request_from_pos",
                [[sessionId], this.state.requestType, lines]
            );

            console.log("[VanStockScreen] Result:", result);
            this.notification.add(
                `Request ${result.name} created successfully!`,
                { type: "success" }
            );

            // Refresh requests list and switch to history
            await this.loadRequests();
            this.state.activeTab = 'history';
            this.state.products = [];

        } catch (error) {
            console.error("=== [VanStockScreen] ERROR in submitRequest ===");
            console.error("[VanStockScreen] Error object:", error);
            console.error("[VanStockScreen] Error data:", error.data);
            console.error("[VanStockScreen] Error message:", error.message);

            let errorMessage = "Failed to create request";
            if (error.data && error.data.message) {
                errorMessage = error.data.message;
            } else if (error.message) {
                errorMessage = error.message;
            }
            this.notification.add(errorMessage, { type: "danger" });
        }
        this.state.loading = false;
        console.log("=== [VanStockScreen] submitRequest END ===");
    }

    back() {
        this.pos.navigate("ProductScreen");
    }

    get screenTitle() {
        console.log("[VanStockScreen] screenTitle getter called");
        return 'Van Item Request';
    }

    getStateLabel(state) {
        return state === 'confirmed' ? 'Requested' : 'Draft';
    }

    getStateClass(state) {
        return state === 'confirmed' ? 'badge bg-success' : 'badge bg-warning';
    }
}

registry.category("pos_pages").add("VanStockScreen", {
    name: "VanStockScreen",
    component: VanStockScreen,
    route: `/pos/ui/${odoo.pos_config_id}/van-stock`,
    params: {},
});

