import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

app.registerExtension({
    name: "LMStudio.UnifiedChat",
    
    async setup() {
        // Listen for standard LM Studio stream updates from the backend
        api.addEventListener("lmstudio.stream.update", (event) => {
            const detail = event.detail;
            const node = app.graph.getNodeById(Number(detail.node_id)) || app.graph.getNodeById(detail.node_id);
            
            if (node && node.displayWidget) {
                // Determine if it's a clear command, reasoning, or normal text
                if (detail.chunk_type === "clear") {
                    node.displayWidget.value = "";
                } else if (detail.chunk_type === "reasoning") {
                    node.displayWidget.value += "💭 " + detail.content;
                } else {
                    node.displayWidget.value += detail.content;
                }
                
                // Force UI repaint without blocking execution
                app.graph.setDirtyCanvas(true, false);
            }
        });
    },

    async nodeCreated(node) {
        if (node.comfyClass === "LMStudio_Unified_Chat") {
            // Find the pre-registered node Schema widget dynamically to natively support Vue 2.0 streaming
            const targetWidget = node.widgets.find(w => w.name === "stream_output");
            if (targetWidget) {
                node.displayWidget = targetWidget;
                if (targetWidget.inputEl) {
                    targetWidget.inputEl.readOnly = true;
                }
            }
            
            // 2. NEW: Fetch and populate the model_id dropdown
            const modelWidget = node.widgets.find(w => w.name === "model_id");
            if (modelWidget) {
                try {
                    // Call our custom python route
                    api.fetchApi("/lmstudio/models").then(response => response.json()).then(data => {
                        if (data.models && data.models.length > 0) {
                            // Replace the widget's options with the live LM Studio models
                            modelWidget.options.values = data.models;
                            modelWidget.value = data.models[0]; // Auto-select the first one
                            app.graph.setDirtyCanvas(true, false);
                        }
                    }).catch(e => {
                        console.error("[LM Studio] Failed to fetch models from backend", e);
                        modelWidget.options.values = ["LM Studio offline"];
                        modelWidget.value = "LM Studio offline";
                        app.graph.setDirtyCanvas(true, false);
                    });
                } catch (e) {
                    console.error("[LM Studio] Failed to fetch models from backend", e);
                    modelWidget.options.values = ["LM Studio offline"];
                    modelWidget.value = "LM Studio offline";
                }
            }
            
            // Override the onExecuted callback directly on this instance
            const onExecuted = node.onExecuted;
            node.onExecuted = function(message) {
                if (onExecuted) onExecuted.apply(this, arguments);
                
                // Reset or update on execution finish using the returned strings if needed
                if (message && message.text) {
                    this.displayWidget.value = message.text.join("");
                }
            };
        }
    }
});
