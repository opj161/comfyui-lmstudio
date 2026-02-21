import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

app.registerExtension({
    name: "LMStudio.UnifiedChat",
    
    async setup() {
        api.addEventListener("lmstudio.stream.update", (event) => {
            const detail = event.detail;
            const node = app.graph.getNodeById(Number(detail.node_id)) || app.graph.getNodeById(detail.node_id);
            
            if (node && node.displayWidget) {
                if (detail.chunk_type === "clear") {
                    node.displayWidget.value = "";
                } else if (detail.chunk_type === "reasoning") {
                    node.displayWidget.value += "💭 " + detail.content;
                } else {
                    node.displayWidget.value += detail.content;
                }
                app.graph.setDirtyCanvas(true, false);
            }
        });
    },

    async nodeCreated(node) {
        if (node.comfyClass === "LMStudio_Unified_Chat") {
            
            // 1. Setup Stream Output Display
            const targetWidget = node.widgets?.find(w => w.name === "stream_output");
            if (targetWidget) {
                node.displayWidget = targetWidget;
                if (targetWidget.inputEl) {
                    targetWidget.inputEl.readOnly = true;
                }
            }
            
            // 2. Safely Fetch Models 
            const modelWidget = node.widgets?.find(w => w.name === "model_id");
            
            const fetchModels = async () => {
                if (!modelWidget) return;
                
                // Check if user is using a custom REST API URL
                const urlWidget = node.widgets?.find(w => w.name === "server_url");
                const targetUrl = urlWidget ? urlWidget.value : "http://127.0.0.1:1234";

                const previousValue = modelWidget.value;
                modelWidget.value = "Fetching...";
                app.graph.setDirtyCanvas(true, false);

                try {
                    // Send URL as query parameter to the python backend
                    const response = await api.fetchApi(`/lmstudio/models?url=${encodeURIComponent(targetUrl)}`);
                    if (!response.ok) throw new Error("Network error");
                    const data = await response.json();
                    
                    if (data.models && data.models.length > 0) {
                        modelWidget.options.values = data.models;
                        
                        // Restore previous selection if it exists, otherwise pick first
                        if (data.models.includes(previousValue) && previousValue !== "Fetching...") {
                            modelWidget.value = previousValue; 
                        } else {
                            modelWidget.value = data.models[0];
                        }
                    }
                } catch (e) {
                    console.warn("[LM Studio] Failed to fetch models. Ensure LM Studio is running.", e);
                    modelWidget.options.values = ["LM Studio offline"];
                    modelWidget.value = "LM Studio offline";
                }
                app.graph.setDirtyCanvas(true, false);
            };
            
            // 3. Add Refresh Button to Node UI
            node.addWidget("button", "🔄 Refresh Models", "refresh", () => {
                fetchModels();
            });
            
            // Fetch immediately on creation
            fetchModels();
            
            // 4. Update on completion
            const onExecuted = node.onExecuted;
            node.onExecuted = function(message) {
                if (onExecuted) onExecuted.apply(this, arguments);
                if (message && message.text) {
                    this.displayWidget.value = message.text.join("");
                }
            };
        }
    }
});
