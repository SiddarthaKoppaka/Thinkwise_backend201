import os
import json
from typing import Dict, Any, List
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from langchain_google_vertexai import ChatVertexAI
from langchain_core.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate
from langchain_core.tools import tool
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.runnables import RunnablePassthrough, RunnableParallel, RunnableSequence
from langchain_tavily import TavilySearch

# ----------------------------
# Environment Setup
# ----------------------------
load_dotenv()
llm = ChatVertexAI(model="gemini-2.0-flash-001", temperature=0.7)  # Adjustable LLM

# ----------------------------
# Tool Definitions
# ----------------------------
class IdeaInput(BaseModel):
    idea_id: str = Field(..., description="Unique identifier for the idea")
    description: str = Field(..., description="Detailed description of the idea")

# Tavily Search Tool
tavily_search_instance = TavilySearch(max_results=5, topic="general")

@tool(args_schema=IdeaInput)
def tavily_search_tool(idea_id: str, description: str) -> Dict[str, Any]:
    """Searches external context for an idea using Tavily."""
    query = f"External context for: {description}"
    try:
        results = tavily_search_instance.run(query)
        return {"tavily": {"results": results}}
    except Exception as e:
        return {"tavily": {"error": str(e)}}

@tool(args_schema=IdeaInput)
def eie_calc_tool(idea_id: str, description: str) -> Dict[str, Any]:
    """Calculates Estimated Implementation Effort (EIE)."""
    prompt = ChatPromptTemplate.from_template("""
    As a project manager, evaluate the implementation effort for this idea:
    "{description}"
    Consider time, resources, dependencies, and complexity.
    Return a JSON with:
    - "eie_score": float (0-1, 1 is hardest)
    - "reasoning": str
    - "details": dict (time_needed, resources, dependencies, complexity)
    """)
    chain = prompt | llm | JsonOutputParser()
    try:
        result = chain.invoke({"description": description})
        return {"eie": {"score": result["eie_score"], "details": result}}
    except Exception as e:
        return {"eie": {"score": 1.0, "details": {"error": str(e)}}}

@tool(args_schema=IdeaInput)
def roi_calc_tool(idea_id: str, description: str) -> Dict[str, Any]:
    """Calculates Return on Investment (ROI)."""
    prompt = ChatPromptTemplate.from_template("""
    As a business strategist, evaluate the ROI for this idea:
    "{description}"
    Consider value creation, demand, and business impact.
    Return a JSON with:
    - "roi_score": float (0-1, 1 is highest)
    - "reasoning": str
    - "details": dict (value_created, user_demand, business_impact)
    """)
    chain = prompt | llm | JsonOutputParser()
    try:
        result = chain.invoke({"description": description})
        return {"roi": {"score": result["roi_score"], "details": result}}
    except Exception as e:
        return {"roi": {"score": 0.0, "details": {"error": str(e)}}}

tools = [tavily_search_tool, eie_calc_tool, roi_calc_tool]
model = llm.bind_tools(tools)

# ----------------------------
# Inner Chain: Evaluate One Idea (ReAct Style)
# ----------------------------
react_prompt = ChatPromptTemplate.from_messages([
    SystemMessagePromptTemplate.from_template("""
    You are an AI using the ReAct framework to evaluate an idea.
    For the idea: "{description}" (ID: {idea_id}):
    1. If no external context, call "tavily_search_tool".
    2. If no EIE, call "eie_calc_tool".
    3. If no ROI, call "roi_calc_tool".
    Current state: {state}
    """),
    HumanMessagePromptTemplate.from_template("Evaluate this idea: {description}")
])

def process_tool_calls(response: Any, idea_id: str, description: str) -> Dict[str, Any]:
    """Processes tool calls and aggregates results."""
    result = {}
    if hasattr(response, "tool_calls") and response.tool_calls:
        for tool_call in response.tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call["args"]
            tool_result = tools_by_name[tool_name].invoke(tool_args)
            result.update(tool_result)
    return result

tools_by_name = {tool.name: tool for tool in tools}

inner_chain = (
    RunnablePassthrough.assign(
        state=lambda x: json.dumps(x.get("result", {}))
    )
    | react_prompt
    | model
    | (lambda x: process_tool_calls(x, x.input["idea_id"], x.input["description"]))
)

def evaluate_idea(idea_id: str, description: str) -> Dict[str, Any]:
    """Evaluates a single idea iteratively until all metrics are collected."""
    result = {}
    for _ in range(3):  # Max 3 iterations to avoid infinite loops
        output = inner_chain.invoke({"idea_id": idea_id, "description": description, "result": result})
        result.update(output)
        if "tavily" in result and "eie" in result and "roi" in result:
            break
    return {idea_id: result}

# ----------------------------
# Outer Chain: Process Multiple Ideas and Aggregate
# ----------------------------
def process_ideas(ideas: Dict[str, Dict[str, str]]) -> Dict[str, Any]:
    """Processes up to 4 ideas in parallel."""
    processed = {}
    for i, (idea_id, idea) in enumerate(ideas.items()):
        if i >= 4:
            break
        description = idea.get("description", "").strip()
        if not description:
            processed[idea_id] = {"error": "No description provided"}
            continue
        processed.update(evaluate_idea(idea_id, description))
    return processed

def aggregate_results(processed_ideas: Dict[str, Any], original_ideas: Dict[str, Dict[str, str]], weights: Dict[str, float]) -> Dict[str, Any]:
    """Aggregates results and ranks top 3 ideas."""
    ratios = {}
    title_map = {
        "idea1": "Chrome Extension for YouTube Summaries",
        "idea2": "SaaS Platform for Freelancer Invoicing",
        "idea3": "Mobile App for User Feedback Aggregation",
        "idea4": "AI-driven IT Support Chatbot",
        "idea5": "E-commerce Recommendation Engine"
    }
    
    for idea_id, result in processed_ideas.items():
        eie_score = result.get("eie", {}).get("score", 1.0)
        roi_score = result.get("roi", {}).get("score", 0.0)
        w_roi = weights.get("roi", 0.6)
        w_eie = weights.get("eie", 0.4)
        ratio = (roi_score * w_roi) / (eie_score * w_eie) if eie_score != 0 else 0.0
        ratios[idea_id] = round(ratio, 2)

    ranked_ideas = sorted(ratios.items(), key=lambda x: x[1], reverse=True)[:3]
    summary = {
        "top_3": [
            {
                "idea_id": idea_id,
                "title": title_map.get(idea_id, original_ideas[idea_id].get("title", original_ideas[idea_id]["description"])),
                "description": original_ideas[idea_id]["description"],
                "final_score": score,
                "evaluation": processed_ideas[idea_id]
            }
            for idea_id, score in ranked_ideas
        ],
        "all_ideas": processed_ideas
    }
    return summary

outer_chain = (
    RunnablePassthrough.assign(
        processed_ideas=lambda x: process_ideas(x["ideas"])
    )
    | RunnablePassthrough.assign(
        summary=lambda x: aggregate_results(x["processed_ideas"], x["ideas"], x["weights"])
    )
)

# ----------------------------
# Test Execution
# ----------------------------
if __name__ == "__main__":
    idea_dict = {
        "idea1": {"title": "Idea 1", "description": "Develop a Chrome extension that provides real-time summaries for YouTube videos."},
        "idea2": {"title": "Idea 2", "description": "Create a SaaS platform for freelancers to automatically generate and manage invoices."},
        "idea3": {"title": "Idea 3", "description": "Build a mobile app that aggregates user feedback for product improvement."},
        "idea4": {"title": "Idea 4", "description": "Design an AI-driven chatbot for internal IT support to triage service requests."},
        "idea5": {"title": "Idea 5", "description": "Implement a recommendation engine for an e-commerce platform."}
    }

    initial_state = {
        "ideas": idea_dict,
        "weights": {"roi": 0.6, "eie": 0.4}
    }

    result = outer_chain.invoke(initial_state)
    print("\n🎉 Final Output Summary:")
    print(json.dumps(result["summary"], indent=2))