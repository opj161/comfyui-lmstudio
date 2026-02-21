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
            
            // FIX 1: Use ?. to prevent silent crashes if widgets aren't mounted yet
            const targetWidget = node.widgets?.find(w => w.name === "stream_output");
            if (targetWidget) {
                node.displayWidget = targetWidget;
                if (targetWidget.inputEl) {
                    targetWidget.inputEl.readOnly = true;
                }
            }
            
            // FIX 2: Safely fetch models and preserve user state
            const modelWidget = node.widgets?.find(w => w.name === "model_id");
            if (modelWidget) {
                const fetchModels = async () => {
                    try {
                        const response = await api.fetchApi("/lmstudio/models");
                        if (!response.ok) throw new Error("Network error");
                        const data = await response.json();
                        
                        if (data.models && data.models.length > 0) {
                            modelWidget.options.values = data.models;
                            
                            // Only override the value if it's the placeholder or an invalid model.
                            // This ensures we don't destroy the user's saved workflow settings on reload!
                            if (modelWidget.value === "Loading models from LM Studio..." || !data.models.includes(modelWidget.value)) {
                                modelWidget.value = data.models[0]; 
                            }
                            app.graph.setDirtyCanvas(true, false);
                        }
                    } catch (e) {
                        console.warn("[LM Studio] Failed to fetch models. Ensure LM Studio is running.", e);
                        modelWidget.options.values = ["LM Studio offline"];
                        if (modelWidget.value === "Loading models from LM Studio...") {
                            modelWidget.value = "LM Studio offline";
                        }
                        app.graph.setDirtyCanvas(true, false);
                    }
                };
                
                // Fetch immediately
                fetchModels();
            }
            
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
