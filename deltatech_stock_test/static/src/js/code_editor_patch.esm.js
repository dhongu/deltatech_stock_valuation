import {CodeEditor} from "@web/core/code_editor/code_editor";

// Add "json" to the list of supported modes
if (!CodeEditor.MODES.includes("json")) {
    CodeEditor.MODES.push("json");
}
