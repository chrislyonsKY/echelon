/**
 * Tests for echelonStore — covers new feature state management:
 * - FIRMS thermal layer visibility
 * - Copilot message streaming (updateCopilotMessage)
 * - Conversation persistence state (currentConversationId, clearCopilotMessages)
 * - Map action dispatch (applyMapAction)
 */
import { describe, it, expect, beforeEach } from "vitest";
import { useEchelonStore } from "./echelonStore";

// Reset store between tests
beforeEach(() => {
  useEchelonStore.setState({
    copilotMessages: [],
    copilotOpen: false,
    byokKey: null,
    currentConversationId: null,
    layerVisibility: {
      convergenceHeatmap: true,
      gdeltEvents: false,
      gfwVessels: false,
      sentinel2: false,
      osmInfrastructure: false,
      landscanPopulation: false,
      firmsThermal: false,
    },
    viewState: { longitude: 0, latitude: 20, zoom: 2, pitch: 0, bearing: 0 },
    selectedCell: null,
    sidebarOpen: false,
  });
});

describe("Feature 6: FIRMS thermal layer", () => {
  it("firmsThermal defaults to false", () => {
    const state = useEchelonStore.getState();
    expect(state.layerVisibility.firmsThermal).toBe(false);
  });

  it("toggleLayer toggles firmsThermal on", () => {
    useEchelonStore.getState().toggleLayer("firmsThermal");
    expect(useEchelonStore.getState().layerVisibility.firmsThermal).toBe(true);
  });

  it("toggleLayer toggles firmsThermal off again", () => {
    useEchelonStore.getState().toggleLayer("firmsThermal");
    useEchelonStore.getState().toggleLayer("firmsThermal");
    expect(useEchelonStore.getState().layerVisibility.firmsThermal).toBe(false);
  });

  it("toggling firmsThermal does not affect other layers", () => {
    useEchelonStore.getState().toggleLayer("firmsThermal");
    const vis = useEchelonStore.getState().layerVisibility;
    expect(vis.convergenceHeatmap).toBe(true);
    expect(vis.gdeltEvents).toBe(false);
    expect(vis.firmsThermal).toBe(true);
  });
});

describe("Feature 1: Streaming — updateCopilotMessage", () => {
  it("updates an existing message by id", () => {
    const store = useEchelonStore.getState();
    const msg = {
      id: "msg-1",
      role: "assistant" as const,
      content: "",
      timestamp: new Date(),
    };
    store.addCopilotMessage(msg);
    expect(useEchelonStore.getState().copilotMessages[0].content).toBe("");

    store.updateCopilotMessage("msg-1", { content: "Hello" });
    expect(useEchelonStore.getState().copilotMessages[0].content).toBe("Hello");
  });

  it("appends content incrementally (simulating streaming)", () => {
    const store = useEchelonStore.getState();
    store.addCopilotMessage({
      id: "stream-1",
      role: "assistant",
      content: "",
      timestamp: new Date(),
    });

    const chunks = ["The ", "situation ", "near ", "Crimea..."];
    let accumulated = "";
    for (const chunk of chunks) {
      accumulated += chunk;
      store.updateCopilotMessage("stream-1", { content: accumulated });
    }

    expect(useEchelonStore.getState().copilotMessages[0].content).toBe(
      "The situation near Crimea..."
    );
  });

  it("updates tool calls on a message", () => {
    const store = useEchelonStore.getState();
    store.addCopilotMessage({
      id: "tool-msg",
      role: "assistant",
      content: "",
      toolCalls: [],
      timestamp: new Date(),
    });

    store.updateCopilotMessage("tool-msg", {
      toolCalls: [{ toolName: "get_convergence_scores", status: "pending" }],
    });
    expect(useEchelonStore.getState().copilotMessages[0].toolCalls).toHaveLength(1);
    expect(useEchelonStore.getState().copilotMessages[0].toolCalls![0].status).toBe("pending");

    store.updateCopilotMessage("tool-msg", {
      toolCalls: [{ toolName: "get_convergence_scores", status: "complete" }],
    });
    expect(useEchelonStore.getState().copilotMessages[0].toolCalls![0].status).toBe("complete");
  });

  it("does not affect other messages when updating by id", () => {
    const store = useEchelonStore.getState();
    store.addCopilotMessage({ id: "a", role: "user", content: "Question", timestamp: new Date() });
    store.addCopilotMessage({ id: "b", role: "assistant", content: "", timestamp: new Date() });

    store.updateCopilotMessage("b", { content: "Answer" });

    expect(useEchelonStore.getState().copilotMessages[0].content).toBe("Question");
    expect(useEchelonStore.getState().copilotMessages[1].content).toBe("Answer");
  });
});

describe("Feature 2: Conversation persistence state", () => {
  it("currentConversationId defaults to null", () => {
    expect(useEchelonStore.getState().currentConversationId).toBeNull();
  });

  it("setCurrentConversationId stores the id", () => {
    useEchelonStore.getState().setCurrentConversationId("conv-123");
    expect(useEchelonStore.getState().currentConversationId).toBe("conv-123");
  });

  it("clearCopilotMessages clears messages and conversation id", () => {
    const store = useEchelonStore.getState();
    store.addCopilotMessage({ id: "m1", role: "user", content: "Hi", timestamp: new Date() });
    store.addCopilotMessage({ id: "m2", role: "assistant", content: "Hello", timestamp: new Date() });
    store.setCurrentConversationId("conv-456");

    expect(useEchelonStore.getState().copilotMessages).toHaveLength(2);
    expect(useEchelonStore.getState().currentConversationId).toBe("conv-456");

    store.clearCopilotMessages();

    expect(useEchelonStore.getState().copilotMessages).toHaveLength(0);
    expect(useEchelonStore.getState().currentConversationId).toBeNull();
  });
});

describe("Feature 4: Share permalink — applyMapAction", () => {
  it("fly_to updates viewport", () => {
    useEchelonStore.getState().applyMapAction({
      type: "fly_to",
      center: [36.6, 45.3],
      zoom: 8,
    });
    const vs = useEchelonStore.getState().viewState;
    expect(vs.longitude).toBe(36.6);
    expect(vs.latitude).toBe(45.3);
    expect(vs.zoom).toBe(8);
  });

  it("set_layers updates layer visibility", () => {
    useEchelonStore.getState().applyMapAction({
      type: "set_layers",
      activeLayers: { gfwVessels: true, firmsThermal: true },
    });
    const vis = useEchelonStore.getState().layerVisibility;
    expect(vis.gfwVessels).toBe(true);
    expect(vis.firmsThermal).toBe(true);
    expect(vis.convergenceHeatmap).toBe(true); // unchanged
  });

  it("highlight_cells selects first cell and opens sidebar", () => {
    useEchelonStore.getState().applyMapAction({
      type: "highlight_cells",
      highlightCells: ["851f91bfffffff", "851f91c7fffffff"],
      center: [36.6, 45.3],
    });
    const state = useEchelonStore.getState();
    expect(state.selectedCell).not.toBeNull();
    expect(state.selectedCell!.h3Index).toBe("851f91bfffffff");
    expect(state.sidebarOpen).toBe(true);
  });
});

describe("H3 resolution derivation", () => {
  it("zoom < 5 gives resolution 5", () => {
    useEchelonStore.getState().setViewState({
      longitude: 0, latitude: 0, zoom: 3, pitch: 0, bearing: 0,
    });
    expect(useEchelonStore.getState().activeResolution).toBe(5);
  });

  it("zoom 7 gives resolution 7", () => {
    useEchelonStore.getState().setViewState({
      longitude: 0, latitude: 0, zoom: 7, pitch: 0, bearing: 0,
    });
    expect(useEchelonStore.getState().activeResolution).toBe(7);
  });

  it("zoom 11 gives resolution 9", () => {
    useEchelonStore.getState().setViewState({
      longitude: 0, latitude: 0, zoom: 11, pitch: 0, bearing: 0,
    });
    expect(useEchelonStore.getState().activeResolution).toBe(9);
  });
});
