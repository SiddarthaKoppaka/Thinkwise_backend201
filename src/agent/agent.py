import os
import re
import json
from typing import Dict, Sequence, TypedDict, Annotated
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from langchain.schema import HumanMessage, SystemMessage  # Ensure these imports are available

# ----------------------------
# Environment Variables & LLM Setup
# ----------------------------
load_dotenv()  # Load variables from .env file

# Uncomment one of the LLM setups below as needed.
from langchain_google_vertexai import ChatVertexAI
llm = ChatVertexAI(model="gemini-2.0-flash-001", temperature=0.7)
# from langchain_ollama import ChatOllama
# llm = ChatOllama(model="llama3.1:8b", temperature=0.3)

# ----------------------------
# Utility Function
# ----------------------------
def extract_json_from_llm_response(text: str) -> str:
    print("Extracting JSON from LLM response...")
    match = re.search(r"```json(.*?)```", text, re.DOTALL)
    if match:
        extracted = match.group(1).strip()
        print(f"Extracted JSON block: {extracted}")
        return extracted
    else:
        match = re.search(r"json\s*(\{.*\})\s*$", text.strip(), re.DOTALL)
        if match:
            extracted = match.group(1)
            print(f"Extracted JSON using fallback regex: {extracted}")
            return extracted
        print("No JSON formatting detected. Returning raw text.")
        return text.strip()

# ----------------------------
# Inner Agent State Definition & Helper Functions
# ----------------------------
class AgentState(TypedDict):
    messages: Annotated[Sequence, lambda x, y: x + y]
    ideas: Dict[str, Dict]
    feedback: Dict[str, float]
    weights: Dict[str, float]
    iteration_count: int

# ----------------------------
# Tool Input Schemas & Functions (ReAct Tools)
# ----------------------------
class IdeaInput(BaseModel):
    idea_id: str = Field(..., description="Unique identifier for the idea")
    description: str = Field(..., description="Detailed description of the idea")

class FinalSummaryInput(BaseModel):
    idea_id: str = Field(..., description="Unique identifier for the idea")
    title: str = Field(..., description="Title of the idea")
    description: str = Field(..., description="Description of the idea")
    roi_score: float = Field(..., description="ROI score for the idea")
    eie_score: float = Field(..., description="EIE score for the idea")

class TavilySearchInput(BaseModel):
    query: str = Field(..., description="Search query to gather external context")
    max_results: int = Field(default=2, description="Maximum number of search results to return")

from langchain_tavily import TavilySearch
tavily_search_instance = TavilySearch(max_results=2, topic="general")

from langchain_core.tools import tool

@tool(args_schema=IdeaInput)
def tavily_search_tool_func(idea_id: str, description: str) -> Dict[str, dict]:
    """Searches for external context relevant to the given idea using Tavily."""
    print(f"Tool Call: Executing 'tavily_search_tool_func' for idea_id: {idea_id} with description: {description}")
    query = f"Search external context for the idea: {description}"
    try:
        results = tavily_search_instance.run(query)
        print(f"'tavily_search_tool_func' result: {results}")
        return {idea_id: {"results": results}}
    except Exception as e:
        print(f"Error in 'tavily_search_tool_func': {e}")
        return {idea_id: {"error": str(e)}}

@tool(args_schema=IdeaInput)
def eie_calc_tool(idea_id: str, description: str) -> Dict[str, Dict]:
    """Evaluates the Estimated Implementation Effort (EIE) for an idea."""
    print(f"Tool Call: Executing 'eie_calc_tool' for idea_id: {idea_id} with description: {description}")
    prompt = f"""
You are an experienced project manager. Evaluate the implementation effort for the following idea, strictly returning only JSON:
"{description}"
Consider time (in weeks), required resources, external dependencies, and overall complexity (low/medium/high).
Return a JSON object with:
- "eie_score": a float Strictly between 0 and 1,
- "reasoning": a brief explanation,
- "details": a dictionary with "time_needed", "resources", "dependencies", "complexity".
    """
    res = llm.invoke(prompt)
    print(f"'eie_calc_tool' LLM response: {res.content}")
    try:
        parsed = json.loads(extract_json_from_llm_response(res.content))
        print(f"'eie_calc_tool' parsed result: {parsed}")
        return {idea_id: {"score": parsed["eie_score"], "details": parsed}}
    except Exception as e:
        print(f"Error parsing response in 'eie_calc_tool': {e}")
        return {idea_id: {"score": 1.0, "details": {"error": str(e), "raw": res.content}}}

@tool(args_schema=IdeaInput)
def roi_calc_tool(idea_id: str, description: str) -> Dict[str, Dict]:
    """Evaluates the potential Return on Investment (ROI) for an idea."""
    print(f"Tool Call: Executing 'roi_calc_tool' for idea_id: {idea_id} with description: {description}")
    prompt = f"""
You are a seasoned business strategist. Evaluate the potential ROI of the following idea, strictly returning only JSON:
"{description}"
Consider value creation, user demand, and strategic business impact.
Return a JSON object with:
- "roi_score": a float STRICTLY between 0 and 1,
- "reasoning": a brief explanation,
- "details": a dictionary with "value_created", "user_demand", "business_impact".
    """
    res = llm.invoke(prompt)
    print(f"'roi_calc_tool' LLM response: {res.content}")
    try:
        parsed = json.loads(extract_json_from_llm_response(res.content))
        print(f"'roi_calc_tool' parsed result: {parsed}")
        return {idea_id: {"score": parsed["roi_score"], "details": parsed}}
    except Exception as e:
        print(f"Error parsing response in 'roi_calc_tool': {e}")
        return {idea_id: {"score": 1.0, "details": {"error": str(e), "raw": res.content}}}

@tool(args_schema=FinalSummaryInput)
def final_summary_tool(idea_id: str, title: str, description: str, roi_score: float, eie_score: float) -> Dict[str, dict]:
    """Generates a final summary for an idea in a strict JSON format."""
    print(f"Tool Call: Executing 'final_summary_tool' for idea_id: {idea_id}")
    prompt = f"""
You are an expert summarizer. Given the following details:
- Idea ID: {idea_id}
- Title: {title}
- Description: {description}
- ROI Score: {roi_score}
- EIE Score: {eie_score}

Generate a final summary strictly in the following JSON format (do not output any additional text):

{{
  "final": true,
  "idea_id": "{idea_id}",
  "title": "{title}",
  "description": "{description}",
  "roi_score": {roi_score},
  "eie_score": {eie_score},
  "aggregated_reasoning": "<your brief aggregated reasoning here>"
}}

Make sure the output is valid JSON.
    """
    res = llm.invoke(prompt)
    print(f"'final_summary_tool' LLM response: {res.content}")
    try:
        parsed = json.loads(extract_json_from_llm_response(res.content))
        print(f"'final_summary_tool' parsed result: {parsed}")
        return {idea_id: {"final_summary": parsed}}
    except Exception as e:
        print(f"Error parsing response in 'final_summary_tool': {e}")
        return {idea_id: {"final_summary": {"error": str(e), "raw": res.content}}}

# ----------------------------
# Inner Graph: ReAct Workflow for One Idea
# ----------------------------
tools = [tavily_search_tool_func, eie_calc_tool, roi_calc_tool, final_summary_tool]
model = llm.bind_tools(tools)
tools_by_name = {tool.name: tool for tool in tools}

def tool_node(state: AgentState) -> Dict:
    print("=== Tool Node: Processing tool calls ===")
    outputs = []
    updated_ideas = state.get("ideas", {})
    last_message = state["messages"][-1]
    last_content = (last_message.content if hasattr(last_message, "content")
                    else last_message.get("content", "N/A"))
    print(f"Last message content: {last_content}")
    for tool_call in last_message.tool_calls:
        tool_name = tool_call["name"]
        print(f"Tool Node: Selected tool '{tool_name}' with args: {tool_call['args']}")
        tool_args = tool_call["args"]
        # Ensure idea_id is a string
        tool_args["idea_id"] = str(tool_args["idea_id"])
        idea_id = tool_args["idea_id"]
        try:
            result = tools_by_name[tool_name].invoke(tool_args)
            print(f"Tool '{tool_name}' executed successfully with result: {result}")
        except Exception as e:
            result = {idea_id: {"error": str(e)}}
            print(f"Tool '{tool_name}' execution failed with error: {e}")
        # Ensure we preserve the original idea details (e.g., title) from the input state.
        if idea_id not in updated_ideas:
            updated_ideas[idea_id] = state["ideas"][idea_id]
        # Save outputs from each tool.
        if tool_name == "tavily_search_tool_func":
            updated_ideas[idea_id]["tavily"] = result[idea_id]
        elif tool_name == "eie_calc_tool":
            updated_ideas[idea_id]["eie"] = result[idea_id]
        elif tool_name == "roi_calc_tool":
            updated_ideas[idea_id]["roi"] = result[idea_id]
        elif tool_name == "final_summary_tool":
            updated_ideas[idea_id]["final_summary"] = result[idea_id]
        outputs.append(SystemMessage(content=json.dumps(result), additional_kwargs={
            "type": "tool",
            "name": tool_name,
            "tool_call_id": tool_call["id"]
        }))
    # For every idea that has tavily, eie, and roi but no final_summary, call final_summary_tool.
    for idea_id, idea_data in updated_ideas.items():
        if ("tavily" in idea_data and "eie" in idea_data and "roi" in idea_data 
            and "final_summary" not in idea_data):
            title = idea_data.get("title", "No Title")
            description = idea_data.get("description", "No Description")
            roi_score = idea_data["roi"].get("score", 0.0)
            eie_score = idea_data["eie"].get("score", 1.0)
            print(f"Finalizing idea {idea_id} using final_summary_tool...")
            final_result = tools_by_name["final_summary_tool"].invoke({
                "idea_id": idea_id,
                "title": title,
                "description": description,
                "roi_score": roi_score,
                "eie_score": eie_score
            })
            print(f"Final summary tool result for idea {idea_id}: {final_result}")
            idea_data["final_summary"] = final_result[idea_id]
            outputs.append(SystemMessage(content=json.dumps(final_result), additional_kwargs={
                "type": "tool",
                "name": "final_summary_tool",
                "tool_call_id": "final_" + idea_id
            }))
    state["iteration_count"] = state.get("iteration_count", 0) + 1
    print(f"Tool Node: Updated iteration_count to {state['iteration_count']}")
    print(f"Tool Node: Updated idea state: {updated_ideas}")
    return {"messages": outputs, "ideas": updated_ideas}

def call_model(state: AgentState, config) -> Dict:
    print("=== Agent Node: Calling the AI model ===")
    messages = state.get("messages", [])
    print("Current messages:")
    for m in messages:
        if isinstance(m, dict):
            content = m.get("content", "N/A")
            m_type = m.get("type", "dict")
        else:
            content = getattr(m, "content", "N/A")
            m_type = m.__class__.__name__
        print(f"  - {m_type}: {content}")
    if not messages or all((m.get("content", "") if isinstance(m, dict) else getattr(m, "content", "")).strip() == "" for m in messages if isinstance(m, HumanMessage) or isinstance(m, dict)):
        print("Error: No valid HumanMessage with content provided.")
        return {"messages": [SystemMessage(content="Error: No valid HumanMessage with content provided.")]}
    system_prompt = SystemMessage(
        content=f"""
You are an AI Agent using the ReAct framework to evaluate and prioritize an innovation idea.
Follow these instructions exactly:
1. If external context ("tavily") is missing, call "tavily_search_tool_func".
2. If "tavily" exists but Estimated Implementation Effort ("eie") is missing, call "eie_calc_tool".
3. If "eie" exists but ROI ("roi") is missing, call "roi_calc_tool".
4. If "tavily", "eie", and "roi" are present and no final summary exists, call "final_summary_tool" using the idea's title, description, ROI score, and EIE score.
5. If the final summary exists, do not call any further tools.
Do not include any chain-of-thought; only output the final summary when complete.
Current idea state:
{json.dumps(state.get('ideas', {}), indent=2)}
        """
    )
    final_messages = [system_prompt] + messages
    print("Agent Node: Final messages sent to model:")
    for msg in final_messages:
        if isinstance(msg, dict):
            content = msg.get("content", "N/A")
            m_type = msg.get("type", "dict")
        else:
            content = getattr(msg, "content", "N/A")
            m_type = msg.__class__.__name__
        print(f"  - {m_type}: {content}")
    response = model.invoke(final_messages, config)
    if not hasattr(response, "content"):
        response = SystemMessage(content=str(response))
    print(f"Agent Node: Received AI model response: {response.content}")
    return {"messages": [response]}

def should_continue(state: AgentState) -> str:
    print("=== Checking if workflow should continue ===")
    if state.get("iteration_count", 0) >= 5:
        print("Iteration count reached 5. Ending workflow.")
        return "end"
    ideas = state.get("ideas", {})
    for idea_id, data in ideas.items():
        if "final_summary" in data:
            continue
        if not ("tavily" in data and "eie" in data and "roi" in data):
            print(f"Idea {idea_id} is not complete. Continuing workflow.")
            return "continue"
    print("All ideas are complete. Ending workflow.")
    return "end"

from langgraph.graph import StateGraph, END
inner_graph = StateGraph(AgentState)
inner_graph.add_node("agent", call_model)
inner_graph.add_node("tools", tool_node)
inner_graph.set_entry_point("agent")
inner_graph.add_conditional_edges("agent", should_continue, {"continue": "tools", "end": END})
inner_graph.add_edge("tools", "agent")
workflow = inner_graph.compile()

# ----------------------------
# Outer Graph: Manage Multiple Idea Agents
# ----------------------------
class OuterState(TypedDict):
    ideas: Dict[str, Dict]
    processed_ideas: Dict[str, Dict]
    feedback: Dict[str, float]
    weights: Dict[str, float]
    summary: Dict

def process_ideas_node(outer_state: dict) -> dict:
    print("=== Outer Graph: Processing ideas ===")
    processed = {}
    for idea_id, idea in outer_state["ideas"].items():
        print(f"Processing idea '{idea_id}': {idea.get('description', 'No description provided')}")
        description = idea.get("description", "").strip()
        if not description:
            print(f"⚠️ Skipping idea '{idea_id}' — no description provided.")
            continue
        inner_state = {
            "messages": [
                HumanMessage(content=f"Evaluate the following idea: {description}")
            ],
            "ideas": {idea_id: idea},
            "feedback": outer_state.get("feedback", {}),
            "weights": outer_state.get("weights", {"roi": 0.6, "eie": 0.4}),
            "iteration_count": 0
        }
        print(f"Initial inner state for idea '{idea_id}': {inner_state}")
        try:
            inner_result = workflow.invoke(inner_state, {"recursion_limit": 100})
            print(f"Completed processing idea '{idea_id}'. Inner result: {inner_result['ideas'][idea_id]}")
            processed[idea_id] = inner_result["ideas"][idea_id]
        except Exception as e:
            print(f"❌ Failed to process idea '{idea_id}': {str(e)}")
            processed[idea_id] = {
                "error": str(e),
                "description": description
            }
    outer_state["processed_ideas"] = processed
    print("Outer Graph: Completed processing all ideas.")
    return outer_state

def aggregate_results_node(outer_state: OuterState) -> OuterState:
    print("=== Outer Graph: Aggregating results ===")
    processed = outer_state["processed_ideas"]
    final_summaries = []
    for idea_id, result in processed.items():
        if "final_summary" in result:
            final = result["final_summary"]
            try:
                if isinstance(final, str):
                    final = json.loads(final)
                if final.get("final") is True:
                    final_summaries.append(final)
            except Exception as e:
                print(f"Error parsing final summary for idea {idea_id}: {e}")
        else:
            print(f"Idea {idea_id} is missing final summary; skipping in aggregation.")
    # Sort by ROI/EIE ratio (ensuring denominator is nonzero)
    ranked = sorted(final_summaries, key=lambda x: (x.get("roi_score", 0) / (x.get("eie_score", 1) if x.get("eie_score", 1) != 0 else 1)), reverse=True)
    top_3 = ranked[:3]
    # Extract top idea ids
    top_idea_ids = [idea["idea_id"] for idea in top_3]
    summary = {
        "top_3": top_3,
        "top_idea_ids": top_idea_ids,
        "all_ideas": processed
    }
    outer_state["summary"] = summary
    print("Outer Graph: Aggregation complete. Summary created.")
    return outer_state

from langgraph.graph import StateGraph, END
outer_graph = StateGraph(OuterState)
outer_graph.add_node("process_ideas", process_ideas_node)
outer_graph.add_node("aggregate_results", aggregate_results_node)
outer_graph.set_entry_point("process_ideas")
outer_graph.add_edge("process_ideas", "aggregate_results")
outer_graph.add_edge("aggregate_results", END)
outer_workflow = outer_graph.compile()

# ----------------------------
# Test Execution (Main Function)
# ----------------------------
# if __name__ == "__main__":
#     import json
#     from langchain_core.messages import HumanMessage

#     idea_dict = {
#         "idea1": {"title": "Idea 1", "description": "Develop a Chrome extension that provides real-time summaries for YouTube videos.", "author": "Alice", "category": "Tech", "timestamp": "2023-04-01T12:00:00"},
#         "idea2": {"title": "Idea 2", "description": "Create a SaaS platform for freelancers to automatically generate and manage invoices.", "author": "Bob", "category": "Business", "timestamp": "2023-04-02T13:00:00"},
#         "idea3": {"title": "Idea 3", "description": "Build a mobile app that aggregates user feedback for product improvement.", "author": "Carol", "category": "Mobile", "timestamp": "2023-04-03T14:00:00"},
#         "idea4": {"title": "Idea 4", "description": "Design an AI-driven chatbot for internal IT support to triage service requests.", "author": "Dave", "category": "AI", "timestamp": "2023-04-04T15:00:00"},
#         "idea5": {"title": "Idea 5", "description": "Implement a recommendation engine for an e-commerce platform.", "author": "Eve", "category": "E-commerce", "timestamp": "2023-04-05T16:00:00"}
#     }

#     print("=== Starting Outer Workflow with Ideas ===")
#     print("Input Ideas:")
#     print(json.dumps(idea_dict, indent=2))

#     initial_outer_state: OuterState = {
#         "ideas": idea_dict,
#         "processed_ideas": {},
#         "feedback": {},
#         "weights": {"roi": 0.6, "eie": 0.4},
#         "summary": {}
#     }

#     final_state = outer_workflow.invoke(initial_outer_state)
#     final_summary = final_state.get("summary", {})
#     print("\n🎉 Final Output Summary:")
#     print(json.dumps(final_summary, indent=2))
