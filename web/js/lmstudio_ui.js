import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

app.registerExtension({
    name: "LMStudio.UnifiedChat",
    
    async setup() {
        api.addEventListener("lmstudio.stream.update", (event) => {
            const detail = event.detail;
            const node = app.graph.getNodeById(Number(detail.node_id)) || app.graph.getNodeById(detail.node_id);
            
            if (node) {
                // Dynamically look up display widget to avoid stale references
                const displayWidget = node.widgets?.find(w => w.name === "stream_output");
                if (displayWidget) {
                    if (detail.chunk_type === "clear") {
                        displayWidget.value = "";
                    } else if (detail.chunk_type === "reasoning") {
                        displayWidget.value += "💭 " + detail.content;
                    } else {
                        displayWidget.value += detail.content;
                    }
                    app.graph.setDirtyCanvas(true, false);
                }
            }
        });
    },

    async nodeCreated(node) {
        if (node.comfyClass === "LMStudio_Unified_Chat") {
            
            // Define the fetch function. It looks up widgets dynamically when called.
            const fetchModels = async () => {
                const modelWidget = node.widgets?.find(w => w.name === "model_id");
                if (!modelWidget) return false; // Return false if widget not ready
                
                const urlWidget = node.widgets?.find(w => w.name === "server_url");
                const targetUrl = urlWidget ? urlWidget.value : "http://localhost:1234";

                const previousValue = modelWidget.value;
                
                // Force the combo box to accept our temporary value by pushing it to the options array
                if (modelWidget.options && !modelWidget.options.values.includes("Fetching...")) {
                    modelWidget.options.values.push("Fetching...");
                }
                modelWidget.value = "Fetching...";
                app.graph.setDirtyCanvas(true, false);

                try {
                    const response = await api.fetchApi(`/lmstudio/models?url=${encodeURIComponent(targetUrl)}`);
                    if (!response.ok) throw new Error("Network error");
                    const data = await response.json();
                    
                    if (data.models && data.models.length > 0) {
                        modelWidget.options.values = data.models;
                        if (data.models.includes(previousValue) && previousValue !== "Fetching...") {
                            modelWidget.value = previousValue; 
                        } else {
                            modelWidget.value = data.models[0];
                        }
                    } else {
                        throw new Error("No models returned");
                    }
                } catch (e) {
                    console.warn("[LM Studio] Failed to fetch models. Ensure LM Studio is running.", e);
                    modelWidget.options.values = ["LM Studio offline"];
                    modelWidget.value = "LM Studio offline";
                }
                app.graph.setDirtyCanvas(true, false);
                return true;
            };
            
            // Add the button immediately (buttons don't depend on the schema)
            node.addWidget("button", "🔄 Refresh Models", "refresh", () => {
                fetchModels();
            });
            
            // V3 Widget Initialization Race Condition Fix:
            // Try fetching immediately. If widgets aren't there, poll a few times.
            let attempts = 0;
            const tryInit = async () => {
                const success = await fetchModels();
                if (!success && attempts < 15) {
                    attempts++;
                    setTimeout(tryInit, 200); // Try again in 200ms
                } else if (success) {
                    // Setup read-only for stream_output once widgets are finally found
                    const targetWidget = node.widgets?.find(w => w.name === "stream_output");
                    if (targetWidget && targetWidget.inputEl) {
                        targetWidget.inputEl.readOnly = true;
                    }
                }
            };
            tryInit();
            
            // Override onExecuted
            const onExecuted = node.onExecuted;
            node.onExecuted = function(message) {
                if (onExecuted) onExecuted.apply(this, arguments);
                if (message && message.text) {
                    const displayWidget = node.widgets?.find(w => w.name === "stream_output");
                    if (displayWidget) {
                        displayWidget.value = message.text.join("");
                    }
                }
            };
        }
    }
});
