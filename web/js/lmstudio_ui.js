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
            // Add a custom text widget to display the stream output
            node.displayWidget = node.addWidget("text", "Output Stream", "", "output");
            
            // Ensure it is read-only
            if (node.displayWidget.inputEl) {
                node.displayWidget.inputEl.readOnly = true;
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
